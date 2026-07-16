# Phase 1：多 Agent DAG 编排测试指南

本文档用于把本次 Phase 1 交给其他 Agent 测试。测试目标是验证：

> 复杂请求能够被拆成任务 DAG；无依赖任务并发执行，有依赖任务等待前置结果；图片只进入允许使用图片的任务；单个任务失败、超时不会拖垮无关任务。

对应实现主要位于：

- `ai-service/assistant/orchestration.py`：任务计划校验、拓扑分层、依赖上下文；
- `ai-service/assistant/graph.py`：DAG 执行、任务级路由、超时与失败隔离；
- `ai-service/assistant/nodes.py`：任务级图片消费；
- `ai-service/shopping/context.py`：前置商品结果注入 Shopping Capability；
- `ai-service/tests/test_assistant_graph.py`：Phase 1 主要测试；
- `ai-service/tests/test_api_contract.py`：响应契约测试。

## 一、交给测试 Agent 的启动话术

可以直接复制下面这段话：

```text
请测试当前项目的 Phase 1：修复任务级路由并实现 DAG 编排。

请先阅读：
1. 根目录 AGENTS.md；
2. ai-service/AGENTS.md；
3. docs/plan/phase1-dag-test-guide.md；
4. ai-service/assistant/orchestration.py；
5. ai-service/assistant/graph.py；
6. ai-service/tests/test_assistant_graph.py。

请从 ai-service 目录执行本文件中的测试命令，不要修改业务代码，不要为了让测试通过而修改断言。
如果测试失败，请记录完整命令、失败测试名、错误堆栈、失败原因判断和是否属于环境依赖问题。
最后按本文档“测试结果回传模板”返回结果。
```

如果测试 Agent 已经知道仓库上下文，也可以简化为：

```text
开始执行 docs/plan/phase1-dag-test-guide.md 中的 Phase 1 测试。
先跑静态检查，再跑 Phase 1 聚焦测试和相关回归测试；不要修改代码，最后按文档模板汇报。
```

## 二、测试前检查

测试 Agent 应在 `ai-service` 目录执行命令。推荐使用项目自己的虚拟环境，不要依赖全局 Python。

```powershell
cd D:\dev\project\py\welove-shop-agt\ai-service
python --version
python -m pytest --version
```

如果项目使用虚拟环境，应先激活：

```powershell
.\.venv\Scripts\Activate.ps1
```

测试前不要求启动 PostgreSQL、Redis、Milvus、Nacos、Java 服务或真实大模型，因为 Phase 1 的核心测试使用 Fake Agent 和 Mock Planner。

如果测试环境缺少依赖，可以先安装项目依赖。不要修改 `requirements.txt`：

```powershell
python -m pip install -r requirements.txt
```

如果完整依赖安装被 Bocha 的 Git 依赖阻塞，可以先安装测试和核心运行依赖，再报告 Bocha 未安装：

```powershell
python -m pip install pytest pytest-asyncio langchain langchain-core langgraph pydantic python-dotenv
```

## 三、第一阶段：静态检查

先确认代码可以被 Python 解析：

```powershell
python -m compileall assistant agents api shopping core tests
```

再检查 Git 补丁格式：

```powershell
cd ..
git diff --check
cd ai-service
```

通过标准：

- `compileall` 返回码为 0；
- 没有 `SyntaxError`、`IndentationError`；
- `git diff --check` 没有空白错误。

## 四、第二阶段：Phase 1 聚焦测试

先执行核心编排测试：

```powershell
python -m pytest tests/test_assistant_graph.py -q -ra --tb=short
```

重点覆盖以下能力：

| 测试内容 | 预期行为 |
|---|---|
| 重复任务 ID | 返回计划校验错误，不执行任务 |
| 非法依赖 ID | 返回稳定错误，不静默删除依赖 |
| 循环依赖 | 返回 `AI_ORCHESTRATOR_PLAN_INVALID` |
| 任务数量限制 | 超过最大任务数时拒绝执行 |
| 依赖深度限制 | 超过最大 DAG 深度时拒绝执行 |
| 无依赖任务并发 | `t1`、`t2` 同层同时启动 |
| 依赖任务等待 | `t3` 不会早于 `t1` 执行 |
| 结构化依赖注入 | `t3` 能读取 `t1` 的商品卡片，而不是只接收文本 |
| 独立任务失败隔离 | `t1` 失败不影响无依赖的 `t2` |
| 依赖失败阻断 | `t1` 失败后，依赖它的 `t3` 为 `blocked` |
| 单任务超时 | 返回 `AI_ORCHESTRATOR_TASK_TIMEOUT`，其他任务继续 |
| 任务级图片路由 | `use_image=true` 的 Shopping 任务使用图片 |
| 图片污染隔离 | Knowledge 任务不会因为全局有图片而进入 Shopping |
| Checkpointer 清理 | 新一轮不会继承上一轮图片和 active task |
| SSE 聚合顺序 | 并发完成顺序不影响最终用户问题顺序 |

聚焦执行某个测试时可以使用：

```powershell
python -m pytest tests/test_assistant_graph.py -q -k "task_levels or concurrently or failure_isolated or timeout or image_is_scoped"
```

如果测试名称因 pytest 版本或代码变动略有差异，以完整文件测试为准。

## 五、第三阶段：接口契约回归

执行 API 响应契约测试：

```powershell
python -m pytest tests/test_api_contract.py tests/test_assistant_stream_filtering.py -q -ra --tb=short
```

重点确认：

- `AIResponse` 仍包含原有字段；
- 新增 `task_levels` 不破坏旧字段；
- `orchestrator_mode`、`sub_questions`、`sub_results` 仍能正常序列化；
- SSE 事件仍使用 `event` 和 `data`；
- `orchestrator_plan`、`orchestrator_subtask`、`token`、`final`、`done` 事件格式没有破坏前端解析。

## 六、第四阶段：购物能力回归

因为 DAG 后置任务会把前置商品结果注入 Shopping Capability，还要执行：

```powershell
python -m pytest tests/test_shopping_capabilities.py tests/test_shopping_high_level_tools.py tests/test_shopping_ranking_and_cards.py -q -ra --tb=short
```

重点确认：

- 普通文本商品推荐链路没有变化；
- 商品比较仍能读取 `last_product_cards`；
- 前置任务传入的商品卡片不会被 Store 中旧商品覆盖；
- 商品卡片字段仍兼容前端：`product_id`、`title`、`price`、`image_url` 等。

## 七、第五阶段：完整 AI Service 回归

前面的测试通过后，再执行完整测试：

```powershell
python -m pytest -q -ra --tb=short
```

如果完整测试耗时较长，可以先执行不依赖外部服务的测试，再单独记录需要 PostgreSQL、Milvus、DashScope 或 Java 服务的测试。

完整回归不应因为外部服务未启动而直接判定代码失败。需要区分：

- 代码断言失败：需要修复代码；
- `ConnectionRefusedError`、Milvus 不可达、DashScope Key 缺失：环境未准备；
- 依赖安装失败：测试环境问题；
- 超时：需要判断是代码超时还是外部服务不可用。

## 八、可选手工接口验证

只有在 AI Service 已启动并配置好模型时执行。默认服务地址为 `http://127.0.0.1:8000`。

### 1. 普通文本复合问题

请求：

```http
POST http://127.0.0.1:8000/api/assistant/run
Content-Type: application/json
```

```json
{
  "question": "推荐适合油皮的防晒，然后说一下烟酰胺的功效，再比较推荐商品的价格",
  "conversation_id": "phase1-manual-001",
  "user_id": 1
}
```

检查响应：

```text
orchestrator_mode = complex
task_levels 应类似 [["t1", "t2"], ["t3"]]
sub_results 长度应等于拆解任务数
sub_results 中每个任务应有 status、duration_ms、depends_on
最终 answer 应按 t1、t2、t3 的原始顺序排列
```

### 2. 图片复合问题

请求：

```http
POST http://127.0.0.1:8000/api/assistant/multimodal/run
Content-Type: application/json
```

```json
{
  "question": "根据这张图找相似商品，并说明这种食品是否适合减脂期",
  "image_url": "https://your-oss-domain/example.jpg",
  "conversation_id": "phase1-manual-image-001",
  "user_id": 1
}
```

检查：

- 找商品任务进入 Shopping 多模态链路；
- 知识任务不因全局图片直接进入 Shopping；
- 如果知识任务依赖商品检索结果，应看到对应 `depends_on`；
- 图片不可达时只影响图片任务，响应包含稳定错误码，不应导致整个服务进程崩溃。

### 3. SSE 流式验证

将上述请求发送到：

```text
POST /api/assistant/stream
POST /api/assistant/multimodal/stream
```

事件顺序至少应满足：

```text
start
→ orchestrator_plan（复杂请求）
→ orchestrator_subtask（任务状态）
→ token
→ final
→ done
```

并发任务的完成先后可以不同，但最终 `final` 中的 `sub_results` 必须保持计划顺序。

## 九、配置项检查

Phase 1 新增配置如下，均有默认值：

```env
ORCHESTRATOR_MAX_TASKS=5
ORCHESTRATOR_MAX_DEPTH=4
ORCHESTRATOR_MAX_CONCURRENCY=3
ORCHESTRATOR_TASK_TIMEOUT_SECONDS=30
```

测试 Agent 可以临时覆盖环境变量验证边界：

```powershell
$env:ORCHESTRATOR_MAX_CONCURRENCY="1"
$env:ORCHESTRATOR_TASK_TIMEOUT_SECONDS="0.05"
python -m pytest tests/test_assistant_graph.py -q -k "concurrently or timeout"
```

测试结束后，如果当前 PowerShell 会话还要继续使用默认配置，可以清除临时变量：

```powershell
Remove-Item Env:ORCHESTRATOR_MAX_CONCURRENCY -ErrorAction SilentlyContinue
Remove-Item Env:ORCHESTRATOR_TASK_TIMEOUT_SECONDS -ErrorAction SilentlyContinue
```

## 十、测试结果回传模板

测试 Agent 必须按下面格式汇报，不要只回复“测试通过”：

```text
## Phase 1 测试结果

测试环境：
- OS：
- Python：
- pytest：
- 是否使用虚拟环境：
- 是否启动外部服务：

执行命令：
1. `python -m compileall assistant agents api shopping core tests`
2. `python -m pytest tests/test_assistant_graph.py -q -ra --tb=short`
3. `python -m pytest tests/test_api_contract.py tests/test_assistant_stream_filtering.py -q -ra --tb=short`
4. 其他命令：

结果汇总：
- 通过：
- 失败：
- 跳过：
- 错误：

Phase 1 验收项：
- DAG 计划校验：通过/失败
- 同层并发：通过/失败
- 依赖等待与结构化注入：通过/失败
- 失败隔离：通过/失败
- 超时隔离：通过/失败
- 任务级图片路由：通过/失败
- SSE/响应契约：通过/失败

失败详情：
- 测试名：
- 完整错误：
- 初步判断：代码问题/环境问题/依赖问题/外部服务问题
- 是否可以稳定复现：

结论：
- Phase 1：通过/部分通过/未通过
- 建议下一步：
```

## 十一、判定标准

Phase 1 可以判定为“测试通过”的最低条件：

1. `test_assistant_graph.py` 全部通过；
2. DAG 校验、同层并发、依赖注入、失败隔离、超时隔离、任务级图片路由测试全部通过；
3. API 契约和 SSE 过滤测试通过；
4. 购物能力回归没有出现既有功能回归；
5. 如果完整测试中只有外部服务不可用导致失败，必须在报告中明确标记为环境阻塞，不能伪装成代码通过。

## 十二、测试后不要做的事情

- 不要为了通过测试删除依赖校验；
- 不要把 `use_image` 改回全局图片判断；
- 不要把并发测试改成固定串行测试；
- 不要把 `blocked` 任务伪装成 `success`；
- 不要直接修改生产配置文件中的密钥；
- 不要执行 `git reset --hard`、`git checkout --` 等破坏用户改动的命令；
- 不要在没有测试结果的情况下声称 Phase 1 已完全通过。
