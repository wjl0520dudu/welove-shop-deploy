"""博查 MCP 客户端：KnowledgeAgent 的网络搜索能力。

## 双通道设计（方案 Z）

博查同时以两种方式暴露给 KnowledgeAgent：

### 1. search_knowledge 内部极端兜底（`bocha_search`）
Milvus **彻底找不到**结果时（sources 为空 / top_score < 0.1）自动兜底。
应对"Milvus 索引里根本没有相关文档"的场景。LLM 不感知。

### 2. search_web 独立工具（`search_web` @tool）
LLM 可见，LLM 自己决定何时调：
- 用户问题含时效词（"最新""2026""最近""新品"）
- Milvus 返回内容和问题不相关（LLM 自行判断）

## 为什么两条通路都要

Milvus 分数只反映向量空间相似度，**不能反映"文档能否回答问题"**。
0.35 分的文档 LLM 看了可能觉得没用，但阈值过滤会认为它够用。
让 LLM 自己判断相关性，主动调 search_web 兜底。

## 底层实现

`bocha_search()` 是核心函数，MCP 优先，HTTP 直连兜底，返回统一结构。
`search_web` 是薄壳，包装 bocha_search 成 LangChain @tool。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from langchain_core.tools import tool

from core.config import config

logger = logging.getLogger("ai-service.knowledge.mcp")

# ── MCP 客户端全局单例 ──────────────────────────────────────────────

_mcp_client: Any = None          # MultiServerMCPClient 实例
_bocha_tools: List[Any] = []     # 从 MCP 加载的博查工具列表
_mcp_available: bool = False     # MCP 是否初始化成功


async def init_mcp_client() -> bool:
    """初始化博查 MCP 客户端。

    服务启动时调用，连接失败不阻塞。

    Returns:
        True 表示 MCP 可用；False 表示降级到 HTTP 直连。
    """
    global _mcp_client, _bocha_tools, _mcp_available

    if not config.BOCHA_API_KEY:
        logger.info("BOCHA_API_KEY 未配置，博查兜底不启用")
        return False

    if not config.BOCHA_MCP_COMMAND:
        logger.info("BOCHA_MCP_COMMAND 未配置，跳过 MCP 走 HTTP 直连")
        return False

    if _mcp_available:
        return True

    try:
        from langchain_mcp_adapters.client import MultiServerMCPClient
    except ImportError:
        logger.warning("langchain-mcp-adapters 未安装，博查 MCP 不可用，降级到 HTTP 直连")
        return False

    try:
        # langchain-mcp-adapters 0.3.x：connections 作为位置参数（dict），不再用 servers= 关键字
        # 博查 MCP Server 官方仓库：https://github.com/Bocha-Labs/bocha-search-mcp
        # 根据 BOCHA_MCP_COMMAND 自动切换启动方式：
        #   - uvx（默认）：uvx --from git+... bocha-search-mcp，自动从 GitHub 拉包运行
        #   - python：预装模式，需先 pip install git+https://github.com/Bocha-Labs/bocha-search-mcp
        #             用 python -m bocha_search_mcp 启动
        #   - 其他自定义命令：args 保持为空，全由 command 自己决定
        cmd = config.BOCHA_MCP_COMMAND.lower()
        if cmd == "uvx":
            args = [
                "--from",
                "git+https://github.com/Bocha-Labs/bocha-search-mcp",
                "bocha-search-mcp",
            ]
        elif cmd == "python":
            args = ["-m", "bocha_search_mcp"]
        else:
            # 未知 command，args 留空由用户在 command 里自己拼全
            args = []

        _mcp_client = MultiServerMCPClient(
            {
                "bocha": {
                    "transport": "stdio",
                    "command": config.BOCHA_MCP_COMMAND,
                    "args": args,
                    "env": {"BOCHA_API_KEY": config.BOCHA_API_KEY},
                },
            }
        )
        # 0.3.x 用 get_tools() 或 session() 上下文管理器，不再手动 load_mcp_tools
        _bocha_tools = await _mcp_client.get_tools()
        _mcp_available = True
        logger.info("博查 MCP 客户端初始化成功，%d 个工具可用", len(_bocha_tools))
        return True
    except Exception as e:
        logger.warning("博查 MCP 初始化失败，降级到 HTTP 直连: %s", e)
        await _close_mcp_safe()
        return False


async def close_mcp_client() -> None:
    """关闭博查 MCP 客户端。"""
    global _mcp_available
    if not _mcp_available:
        return
    await _close_mcp_safe()
    _mcp_available = False
    logger.info("博查 MCP 客户端已关闭")


async def _close_mcp_safe() -> None:
    """安全清理 MCP 客户端引用，忽略异常。

    langchain-mcp-adapters 0.3.x 的 MultiServerMCPClient 无显式 close 方法，
    session 是通过 async context manager 管理的，get_tools() 内部自动开关。
    这里只清引用即可。
    """
    global _mcp_client
    if _mcp_client is None:
        return
    # 兼容旧版本可能有的 close() 方法
    close_fn = getattr(_mcp_client, "close", None)
    if close_fn is not None:
        try:
            await close_fn()
        except Exception:
            pass
    _mcp_client = None
    _bocha_tools.clear()


# ── 博查搜索（对外唯一接口）──────────────────────────────────────────


async def bocha_search(query: str, count: int = 5) -> Dict[str, Any]:
    """搜索博查，MCP 优先，HTTP 直连兜底。

    Args:
        query: 搜索关键词。
        count: 期望返回结果数。

    Returns:
        {
            "success": bool,
            "results": [{"title": str, "content": str, "url": str, "source": "bocha"}, ...],
            "error": str | None,
            "channel": "mcp" | "http" | "none",   # 实际走的通道，便于日志追踪
        }
    """
    if not config.BOCHA_API_KEY:
        logger.info("bocha_search: BOCHA_API_KEY 未配置，跳过兜底 query=%r", query)
        return {"success": False, "results": [], "error": "BOCHA_API_KEY 未配置", "channel": "none"}

    # 优先走 MCP
    if _mcp_available and _bocha_tools:
        logger.info("bocha_search: 走 MCP 通道 query=%r count=%d", query, count)
        result = await _bocha_search_via_mcp(query, count)
        result["channel"] = "mcp"
        if result["success"]:
            logger.info(
                "bocha_search: MCP 成功 query=%r 返回 %d 条",
                query, len(result["results"]),
            )
            return result
        logger.warning(
            "bocha_search: MCP 失败，降级 HTTP 直连 query=%r error=%s",
            query, result.get("error"),
        )
    else:
        logger.info(
            "bocha_search: MCP 不可用（available=%s tools=%d），走 HTTP 直连 query=%r",
            _mcp_available, len(_bocha_tools), query,
        )

    # 降级 HTTP 直连
    result = await _bocha_search_via_http(query, count)
    result["channel"] = "http"
    if result["success"]:
        logger.info(
            "bocha_search: HTTP 成功 query=%r 返回 %d 条",
            query, len(result["results"]),
        )
    else:
        logger.warning(
            "bocha_search: HTTP 失败 query=%r error=%s",
            query, result.get("error"),
        )
    return result


# ── MCP 方式 ────────────────────────────────────────────────────────


async def _bocha_search_via_mcp(query: str, count: int) -> Dict[str, Any]:
    """通过 MCP 工具调用博查搜索。"""
    try:
        # bocha_web_search 是 MCP Server 暴露的主要搜索工具
        tool = _bocha_tools[0] if _bocha_tools else None
        if tool is None:
            return {"success": False, "results": [], "error": "MCP 工具列表为空"}

        raw = await tool.ainvoke({
            "query": query,
            "count": count,
        })

        # 解析 MCP 工具返回（可能是 JSON 字符串或 dict）
        data = _parse_mcp_result(raw)
        if data is None:
            return {"success": False, "results": [], "error": "MCP 返回格式无法解析"}

        return _format_bocha_results(data, count)
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}


def _parse_mcp_result(raw: Any) -> Optional[Dict[str, Any]]:
    """解析 MCP 工具返回的各种可能格式。"""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # 可能是纯文本，直接当成一个结果
            return {"results": [{"title": "", "snippet": raw, "url": ""}]}
    return None


# ── HTTP 直连方式（MCP 不可用时的降级）──────────────────────────────

# 博查 Web Search API 官方端点。
# POST + JSON body，鉴权用 Bearer token。
# 官方文档：https://bocha-ai.feishu.cn/wiki/RXEOw02rFiwzGSkd9mUcqoeAnNK
_BOCHA_API_URL = "https://api.bochaai.com/v1/web-search"


async def _bocha_search_via_http(query: str, count: int) -> Dict[str, Any]:
    """直连博查 HTTP API 搜索。

    博查接口规范：POST + JSON body，参数 query/summary/freshness/count。
    summary=True 返回详细摘要，适配 RAG 场景。
    count 强制 1-50。
    """
    try:
        payload = {
            "query": query,
            "summary": True,        # 拿详细摘要，用于 RAG 兜底
            "freshness": "all",     # 不限时间
            "count": max(1, min(count, 50)),
        }
        async with httpx.AsyncClient(timeout=config.BOCHA_SEARCH_TIMEOUT) as client:
            resp = await client.post(
                _BOCHA_API_URL,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {config.BOCHA_API_KEY}",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return _format_bocha_results(data, count)
    except httpx.TimeoutException:
        return {"success": False, "results": [], "error": "博查 HTTP 请求超时"}
    except Exception as e:
        return {"success": False, "results": [], "error": str(e)}


# ── 结果格式化 ──────────────────────────────────────────────────────


def _format_bocha_results(data: Dict[str, Any], count: int) -> Dict[str, Any]:
    """把博查 API 返回格式化成统一结构。

    博查 API 返回格式（官方文档）：
    {
        "data": {
            "webPages": {
                "value": [
                    {
                        "id": "...",
                        "name": "网页标题",
                        "url": "https://...",
                        "snippet": "简短摘要",
                        "summary": "详细摘要（summary=true 时返回）",
                        "siteName": "网站名",
                        "datePublished": "2024-07-22T...",
                        ...
                    }
                ]
            }
        }
    }

    优先取 summary（详细摘要，RAG 场景更有用），其次 snippet。
    """
    web_pages_value: List[Dict[str, Any]] = []

    # 官方标准格式：data.webPages.value（value 是数组）
    if isinstance(data.get("data"), dict):
        web_pages = data["data"].get("webPages")
        if isinstance(web_pages, dict):
            web_pages_value = web_pages.get("value") or []
        elif isinstance(web_pages, list):
            # 兼容旧格式：webPages 直接是数组
            web_pages_value = web_pages

    # 兜底：results 或 webPages 直接在顶层
    if not web_pages_value:
        if isinstance(data.get("results"), list):
            web_pages_value = data["results"]
        elif isinstance(data.get("webPages"), list):
            web_pages_value = data["webPages"]

    results: List[Dict[str, Any]] = []
    for p in web_pages_value[:count]:
        if not isinstance(p, dict):
            continue
        # 优先取 summary（详细），退化到 snippet（简短）
        content = (
            p.get("summary")
            or p.get("snippet")
            or p.get("content")
            or ""
        )
        results.append({
            "title": str(p.get("name") or p.get("title") or ""),
            "content": str(content),
            "url": str(p.get("url") or p.get("displayUrl") or ""),
            "site_name": str(p.get("siteName") or ""),
            "date_published": str(p.get("datePublished") or ""),
            "source": "bocha",
        })

    if not results:
        return {"success": False, "results": [], "error": "博查返回空结果"}

    return {"success": True, "results": results, "error": None}


# ── 工具函数：将博查结果拼成 knowledge_context ──────────────────────


def build_bocha_context(bocha_results: List[Dict[str, Any]]) -> str:
    """把博查搜索结果拼接成 knowledge_context 文本块。

    格式：
        [网络资料1] 来源：网站名 - 标题（发布时间）
        URL：https://...
        详细摘要内容
    """
    blocks: List[str] = []
    for i, r in enumerate(bocha_results, start=1):
        title = r.get("title") or "未知来源"
        site_name = r.get("site_name") or ""
        url = r.get("url") or ""
        date = r.get("date_published") or ""
        content = r.get("content") or ""
        if not content:
            continue

        # 来源行：网站名 - 标题（发布时间）
        source_parts = []
        if site_name:
            source_parts.append(site_name)
        source_parts.append(title)
        source_line = " - ".join(source_parts)
        if date:
            # 只取日期部分 "2024-07-22T18:38:55Z" → "2024-07-22"
            source_line += f"（{date[:10]}）"

        block_lines = [f"[网络资料{i}] 来源：{source_line}"]
        if url:
            block_lines.append(f"URL：{url}")
        block_lines.append(content)
        blocks.append("\n".join(block_lines))
    return "\n\n".join(blocks) if blocks else ""


# ── LLM 可见工具：search_web ────────────────────────────────────────


@tool
async def search_web(query: str, count: int = 5) -> dict:
    """从互联网搜索最新/时效性/内部知识库覆盖不到的信息（博查 Web Search）。

    ## 何时调用（必须命中以下情况之一）

    1. **时效性问题**：query 含"最新""2026""2025""最近""近期""新品""刚发布"等时效词
       - 例：「2026 年最新的护肤成分」「最近有什么新出的防晒霜」
    2. **本店未收录的品牌/产品**：query 涉及内部知识库明显不会有的品牌
    3. **search_knowledge 返回内容和问题不相关**：你自己判断内部结果没能回答用户问题

    ## 何时禁止调用

    - 通用护肤知识（成分原理、搭配禁忌、使用方法）→ 用 search_knowledge
    - 每轮对话最多调用 2 次，避免过度依赖网络
    - **绝不能跳过 search_knowledge 直接调本工具**，除非命中上面第 1/2 条

    Args:
        query: 用于网络搜索的关键词，尽量精炼（去掉客套/指代/无关修饰）。
        count: 期望返回结果数，默认 5，最大 10。

    Returns:
        dict 结构：
        {
            "knowledge_context": str,  # 拼接好的网络资料文本，可直接引用
            "sources": [                # 来源列表，用于回答后附引用
                {"title": str, "url": str, "site_name": str, "date": str},
                ...
            ],
            "total_results": int,      # 实际返回条数
            "success": bool,           # 是否成功获取网络资料
            "channel": str,            # "mcp" | "http" | "none"，观测用
        }

        - success=False 时 sources 为空，回答用户"网络搜索暂时不可用"。
    """
    max_count = max(1, min(int(count or 5), 10))
    logger.info("search_web (LLM 主动调用): query=%r count=%d", query, max_count)

    result = await bocha_search(query, count=max_count)
    channel = result.get("channel", "unknown")

    if not (result["success"] and result["results"]):
        logger.warning(
            "search_web: 未拿到有效结果 channel=%s error=%s",
            channel, result.get("error"),
        )
        return {
            "knowledge_context": "",
            "sources": [],
            "total_results": 0,
            "success": False,
            "channel": channel,
        }

    web_context = build_bocha_context(result["results"])
    sources = [
        {
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "site_name": r.get("site_name", ""),
            "date": r.get("date_published", "")[:10],
        }
        for r in result["results"]
    ]

    logger.info(
        "search_web: 成功 channel=%s 返回 %d 条网络资料",
        channel, len(sources),
    )

    return {
        "knowledge_context": "## 网络搜索结果\n" + web_context,
        "sources": sources,
        "total_results": len(sources),
        "success": True,
        "channel": channel,
    }