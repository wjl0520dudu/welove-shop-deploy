"""复杂请求的任务 DAG 契约、校验和依赖上下文构造。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class PlanValidationError(ValueError):
    """任务计划不满足可执行 DAG 约束。"""

    violations: tuple[str, ...]

    def __str__(self) -> str:
        return "；".join(self.violations)


def build_task_levels(
    tasks: list[dict[str, Any]],
    *,
    max_tasks: int = 5,
    max_depth: int = 4,
) -> list[list[str]]:
    """严格校验任务计划，并使用 Kahn 算法生成可并发执行的拓扑层。"""
    violations: list[str] = []
    if len(tasks) < 2:
        violations.append("复杂任务至少需要 2 个子任务")
    if len(tasks) > max_tasks:
        violations.append(f"子任务数量 {len(tasks)} 超过上限 {max_tasks}")

    ids: list[str] = []
    for index, task in enumerate(tasks, start=1):
        task_id = str(task.get("id") or "").strip()
        question = str(task.get("question") or "").strip()
        depends_on = task.get("depends_on")
        if not task_id:
            violations.append(f"第 {index} 个子任务缺少 id")
        if not question:
            violations.append(f"子任务 {task_id or index} 缺少 question")
        if not isinstance(depends_on, list):
            violations.append(f"子任务 {task_id or index} 的 depends_on 必须是数组")
        ids.append(task_id)

    duplicates = sorted({task_id for task_id in ids if task_id and ids.count(task_id) > 1})
    if duplicates:
        violations.append("存在重复任务 ID: " + ", ".join(duplicates))

    valid_ids = {task_id for task_id in ids if task_id}
    for task in tasks:
        task_id = str(task.get("id") or "").strip()
        depends_on = task.get("depends_on")
        if not isinstance(depends_on, list):
            continue
        dep_ids = [str(dep or "").strip() for dep in depends_on]
        if len(dep_ids) != len(set(dep_ids)):
            violations.append(f"子任务 {task_id} 存在重复依赖")
        for dep_id in dep_ids:
            if not dep_id:
                violations.append(f"子任务 {task_id} 存在空依赖 ID")
            elif dep_id == task_id:
                violations.append(f"子任务 {task_id} 不能依赖自身")
            elif dep_id not in valid_ids:
                violations.append(f"子任务 {task_id} 依赖不存在的任务 {dep_id}")

    if violations:
        raise PlanValidationError(tuple(dict.fromkeys(violations)))

    order = {task_id: index for index, task_id in enumerate(ids)}
    indegree = {task_id: 0 for task_id in ids}
    children = {task_id: [] for task_id in ids}
    for task in tasks:
        task_id = str(task["id"])
        for dep_id in task.get("depends_on") or []:
            dep_id = str(dep_id)
            indegree[task_id] += 1
            children[dep_id].append(task_id)

    ready = sorted((task_id for task_id, degree in indegree.items() if degree == 0), key=order.get)
    levels: list[list[str]] = []
    visited = 0
    while ready:
        level = ready
        levels.append(level)
        visited += len(level)
        next_ready: list[str] = []
        for task_id in level:
            for child_id in children[task_id]:
                indegree[child_id] -= 1
                if indegree[child_id] == 0:
                    next_ready.append(child_id)
        ready = sorted(next_ready, key=order.get)

    if visited != len(tasks):
        cyclic_ids = [task_id for task_id, degree in indegree.items() if degree > 0]
        raise PlanValidationError(("任务依赖存在循环: " + ", ".join(cyclic_ids),))
    if len(levels) > max_depth:
        raise PlanValidationError((f"任务依赖深度 {len(levels)} 超过上限 {max_depth}",))
    return levels


def scope_task_images(
    tasks: list[dict[str, Any]],
    *,
    has_image: bool,
) -> list[dict[str, Any]]:
    """把请求级图片收敛为任务级 use_image，非购物任务永远不能继承图片。"""
    scoped = [dict(task) for task in tasks]
    invalid_values = [
        str(task.get("id") or "")
        for task in scoped
        if task.get("use_image") is not None and not isinstance(task.get("use_image"), bool)
    ]
    if invalid_values:
        raise PlanValidationError((
            "use_image 必须是布尔值: " + ", ".join(invalid_values),
        ))
    invalid_tasks = [
        str(task.get("id") or "")
        for task in scoped
        if task.get("use_image") is True
        and str(task.get("intent_hint") or "unknown") not in {"shopping", "unknown"}
    ]
    if invalid_tasks:
        raise PlanValidationError((
            "非购物子任务不能使用图片: " + ", ".join(invalid_tasks),
        ))
    if not has_image:
        for task in scoped:
            task["use_image"] = False
        return scoped

    image_scope_provided = any(task.get("use_image") is not None for task in scoped)
    explicit_image_task = False
    for task in scoped:
        intent = str(task.get("intent_hint") or "unknown")
        use_image = bool(task.get("use_image")) and intent in {"shopping", "unknown"}
        task["use_image"] = use_image
        explicit_image_task = explicit_image_task or use_image

    # 兼容旧 Planner/启发式拆解：没有输出 use_image 时，只把图片交给第一个购物任务。
    if not explicit_image_task and not image_scope_provided:
        for task in scoped:
            if str(task.get("intent_hint") or "") == "shopping":
                task["use_image"] = True
                break
    return scoped


def dependency_payload(result: dict[str, Any]) -> dict[str, Any]:
    """生成可注入后置任务的稳定、精简、可序列化结果。"""
    return {
        "task_id": result.get("id"),
        "status": result.get("status"),
        "route": result.get("route"),
        "answer": str(result.get("answer") or "")[:2000],
        "product_cards": [_slim_product(card) for card in (result.get("product_cards") or [])[:10]],
        "sources": [_slim_source(source) for source in (result.get("sources") or [])[:10]],
        "error_code": result.get("error_code"),
    }


def format_dependency_message(payloads: list[dict[str, Any]]) -> str:
    """供 Agent 阅读的依赖上下文；内部仍以 payload dict 作为真实契约。"""
    return (
        "以下 JSON 是本子任务明确依赖的前置任务结果。"
        "只能使用其中提供的商品、来源和结论，不要改用会话里其他无关候选：\n"
        + json.dumps(payloads, ensure_ascii=False, indent=2)
    )


def dependency_business_memory(
    base_memory: dict[str, Any],
    payloads: list[dict[str, Any]],
) -> dict[str, Any]:
    """把前置商品实体注入 Shopping Capability 使用的任务级业务记忆。"""
    merged = dict(base_memory or {})
    cards = _dedupe_cards(
        card
        for payload in payloads
        if payload.get("status") == "success"
        for card in (payload.get("product_cards") or [])
    )
    if cards:
        merged["last_product_cards"] = cards
        if len(cards) == 1:
            merged["last_focused_product"] = cards[0]
    return merged


def _slim_product(card: Any) -> dict[str, Any]:
    if not isinstance(card, dict):
        return {}
    keys = (
        "product_id", "id", "title", "brand", "price", "base_price",
        "category", "sub_category", "rating", "sales_count", "reason",
    )
    return {key: card.get(key) for key in keys if card.get(key) is not None}


def _slim_source(source: Any) -> dict[str, Any]:
    if hasattr(source, "model_dump"):
        source = source.model_dump()
    elif hasattr(source, "dict"):
        source = source.dict()
    if not isinstance(source, dict):
        return {}
    keys = ("doc_id", "doc", "doc_name", "title", "url", "score")
    return {key: source.get(key) for key in keys if source.get(key) is not None}


def _dedupe_cards(cards: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        if not isinstance(card, dict) or not card:
            continue
        key = str(card.get("product_id") or card.get("id") or card.get("title") or len(out))
        if key in seen:
            continue
        seen.add(key)
        out.append(card)
    return out
