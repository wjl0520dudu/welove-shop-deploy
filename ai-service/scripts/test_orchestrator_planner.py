"""独立测试 Orchestrator Planner（不启 FastAPI，只调 LLM）。

只验证一件事：给定 docs/orchestrator-test-data-and-results.md 里的 8 个测试用例，
真实 LLM 拆解结果是否符合预期？

用法：
    conda activate d:\\dev\\env\\conda_envs\\wlagt
    cd d:\\dev\\project\\py\\welove-shop-agt\\ai-service
    python scripts/test_orchestrator_planner.py
"""

from __future__ import annotations

import asyncio
import io
import json
import sys
from pathlib import Path

# Windows UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from langchain_core.messages import HumanMessage, SystemMessage

from agents.prompts import ORCHESTRATOR_PROMPT
from agents.schemas import OrchestratorDecision
from core.llm import get_llm


TEST_CASES = [
    {
        "name": "1. 单意图简单推荐",
        "question": "给我推荐一款适合油皮的防晒",
        "expected_mode": "simple",
        "expected_task_count": 0,
    },
    {
        "name": "2. 单意图多细节，不应拆解",
        "question": "烟酰胺是什么、怎么用、有什么注意事项？",
        "expected_mode": "simple",
        "expected_task_count": 0,
        "note": "单意图（都是 knowledge），KnowledgeAgent 应一次分点回答",
    },
    {
        "name": "3. 跨意图复合问题",
        "question": "给我推荐适合油皮的防晒，然后我还想知道烟酰胺是什么成分，还有你推荐的这些价格对比如何？",
        "expected_mode": "complex",
        "expected_task_count": 3,
        "expected_intents": ["shopping", "knowledge", "shopping"],
        "expected_deps_last": ["t1"],
    },
    {
        "name": "4. 依赖型商品追问",
        "question": "推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？",
        "expected_mode": "complex",
        "expected_task_count": 3,
        "note": "t2/t3 应有 depends_on=['t1']",
    },
    {
        "name": "5. 多个独立知识问题",
        "question": "烟酰胺和VC能一起用吗？视黄醇晚上怎么用？",
        "expected_mode": "complex",
        "expected_task_count": 2,
        "expected_intents": ["knowledge", "knowledge"],
        "note": "两个独立 knowledge 子任务，无依赖",
    },
    {
        "name": "6. 闲聊或元问题",
        "question": "你还记得我刚才问了什么吗？",
        "expected_mode": "simple",
        "expected_task_count": 0,
    },
    {
        "name": "7. 用户补充澄清信息",
        "question": "油皮，预算 200 以内",
        "expected_mode": "simple",
        "expected_task_count": 0,
        "note": "只是补充信息，不该拆",
    },
    {
        "name": "8. 明显但 planner 需产多任务",
        "question": "推荐一款防晒，然后说说烟酰胺的功效，还有这些商品哪个便宜",
        "expected_mode": "complex",
        "expected_task_count": 3,
        "note": "含'这些商品哪个便宜'应依赖 t1",
    },
]


def _fmt_task(task) -> str:
    if hasattr(task, "model_dump"):
        d = task.model_dump()
    else:
        d = dict(task)
    return (
        f"    id={d.get('id')}  intent={d.get('intent_hint')}  "
        f"deps={d.get('depends_on') or []}\n"
        f"      q: {d.get('question')}"
    )


def _check(case: dict, decision) -> tuple[bool, list[str]]:
    """校验 decision 是否符合预期，返回 (通过?, 问题列表)。"""
    problems: list[str] = []
    mode = str(getattr(decision, "mode", "simple") or "simple").lower()
    tasks = getattr(decision, "tasks", []) or []

    exp_mode = case["expected_mode"]
    if mode != exp_mode:
        problems.append(f"mode 预期 {exp_mode}，实际 {mode}")

    exp_count = case.get("expected_task_count", 0)
    if exp_mode == "simple":
        # simple 时任务数应为 0 或 1（<2 都会被 _normalize 打回 simple）
        if len(tasks) >= 2:
            problems.append(f"预期不拆解，但产出 {len(tasks)} 个任务")
    else:
        if len(tasks) != exp_count:
            problems.append(f"任务数预期 {exp_count}，实际 {len(tasks)}")

    exp_intents = case.get("expected_intents")
    if exp_intents and len(tasks) == len(exp_intents):
        for i, (task, want) in enumerate(zip(tasks, exp_intents), 1):
            got = getattr(task, "intent_hint", None)
            if got != want:
                problems.append(f"t{i} intent 预期 {want}，实际 {got}")

    exp_deps_last = case.get("expected_deps_last")
    if exp_deps_last is not None and tasks:
        last = tasks[-1]
        got_deps = getattr(last, "depends_on", []) or []
        if list(got_deps) != list(exp_deps_last):
            problems.append(f"末任务 depends_on 预期 {exp_deps_last}，实际 {got_deps}")

    return (len(problems) == 0, problems)


async def run_one(llm, case: dict) -> dict:
    print()
    print("=" * 75)
    print(f" {case['name']}")
    print("=" * 75)
    print(f"输入: {case['question']}")
    if case.get("note"):
        print(f"备注: {case['note']}")

    messages = [
        SystemMessage(content=ORCHESTRATOR_PROMPT),
        HumanMessage(content=case["question"]),
    ]

    try:
        decision = await llm.ainvoke(messages)
    except Exception as e:  # noqa: BLE001
        print(f"❌ 调用失败: {e}")
        return {"case": case["name"], "passed": False, "error": str(e)}

    mode = getattr(decision, "mode", "simple")
    reason = getattr(decision, "reason", "")
    tasks = getattr(decision, "tasks", []) or []

    print(f"\n实际输出:")
    print(f"  mode:   {mode}")
    print(f"  reason: {reason}")
    print(f"  tasks:  {len(tasks)} 个")
    for t in tasks:
        print(_fmt_task(t))

    passed, problems = _check(case, decision)
    if passed:
        print(f"\n✅ 通过 - 预期 {case['expected_mode']} / {case.get('expected_task_count', 0)} 任务")
    else:
        print(f"\n❌ 未通过:")
        for p in problems:
            print(f"   - {p}")

    return {
        "case": case["name"],
        "passed": passed,
        "problems": problems,
        "mode": mode,
        "task_count": len(tasks),
        "tasks": [
            (t.model_dump() if hasattr(t, "model_dump") else dict(t)) for t in tasks
        ],
    }


async def main() -> None:
    print("🔧 初始化 LLM ...")
    llm = get_llm()
    if llm is None:
        print("❌ LLM 未配置，退出")
        return
    orchestrator_llm = llm.with_structured_output(
        OrchestratorDecision, method="json_schema"
    )

    results = []
    for case in TEST_CASES:
        r = await run_one(orchestrator_llm, case)
        results.append(r)

    print()
    print("=" * 75)
    print(" 汇总")
    print("=" * 75)
    passed = sum(1 for r in results if r["passed"])
    print(f"通过: {passed}/{len(results)}")
    for r in results:
        status = "✅" if r["passed"] else "❌"
        extra = ""
        if not r["passed"]:
            extra = "  |  " + "; ".join(r.get("problems") or [])
        print(f"  {status} {r['case']}{extra}")

    out_path = Path(__file__).resolve().parent / "orchestrator_planner_results.json"
    out_path.write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n📄 详细结果: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
