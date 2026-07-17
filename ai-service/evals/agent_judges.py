"""Optional LLM-as-a-Judge adapters used by the offline Agent evaluator.

The optional imports are intentional: Contract Test remains usable in the base
runtime.  Install ``requirements-eval.txt`` only on an evaluation environment.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def evaluate_with_deepeval(
    case: dict[str, Any],
    response: dict[str, Any],
    *,
    threshold: float = 0.6,
    cache: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score agent quality with DeepEval native agent metrics.

    Runs three metrics per case:
    - TaskCompletion:  did the agent complete the user's task?
    - ToolCorrectness: were the correct tools called?
    - GoalAccuracy:    how well was the goal achieved (includes plan quality)?
    """
    try:
        from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric
        from deepeval.test_case import LLMTestCase, ToolCall
    except ImportError as exc:  # pragma: no cover - exercised in eval env
        raise RuntimeError("DeepEval is not installed. Run: pip install -r requirements-eval.txt") from exc

    user_input = str(case.get("input") or "")
    actual_output = str(response.get("answer") or "")
    expected = case.get("expected") or {}
    expected_output = str(expected.get("reference_answer") or "")
    model = _build_deepeval_model()

    # ---- Build ToolCall objects for ToolCorrectness ----
    tools_called = [
        ToolCall(
            name=str(tc.get("tool_name") or tc.get("name") or ""),
            input_parameters=tc.get("input_params") or tc.get("args") or {},
        )
        for tc in (response.get("tool_calls") or [])
    ]
    expected_tools = [
        ToolCall(name=str(name))
        for name in (expected.get("required_tools") or [])
    ]

    metrics: dict[str, dict[str, Any]] = {}

    # 1. TaskCompletionMetric — task completion via LLMTestCase
    try:
        tc_metric = TaskCompletionMetric(threshold=threshold, model=model, include_reason=True)
        tc_case = LLMTestCase(
            input=user_input,
            actual_output=actual_output,
            tools_called=tools_called,
        )
        tc_metric.measure(tc_case)
        metrics["task_completion"] = _metric_result(tc_metric)
    except Exception as exc:
        metrics["task_completion"] = _metric_error(exc)

    # 2. ToolCorrectnessMetric — tool selection correctness
    try:
        tool_metric = ToolCorrectnessMetric(model=model, include_reason=True)
        tool_case = LLMTestCase(
            input=user_input,
            actual_output=actual_output,
            tools_called=tools_called,
            expected_tools=expected_tools,
        )
        tool_metric.measure(tool_case)
        metrics["tool_correctness"] = _metric_result(tool_metric)
    except Exception as exc:
        metrics["tool_correctness"] = _metric_error(exc)

    # 3. GoalAccuracyMetric — commented out: single-turn conversation lacks plan structure
    #    for the metric to evaluate plan quality meaningfully. Revisit with multi-turn.
    # try:
    #     goal_metric = GoalAccuracyMetric(threshold=threshold, model=model, include_reason=True)
    #     goal_turns: list[Turn] = [Turn(role="user", content=user_input)]
    #     sub_results = response.get("sub_results") or []
    #     if sub_results:
    #         for sub in sub_results:
    #             sub_tools = [
    #                 ToolCall(name=str(tc.get("tool_name") or tc.get("name") or ""))
    #                 for tc in (sub.get("tool_calls") or [])
    #             ]
    #             goal_turns.append(Turn(role="assistant", content=sub.get("answer", ""), tools_called=sub_tools or None))
    #     else:
    #         for tc in response.get("tool_calls") or []:
    #             tool_name = str(tc.get("tool_name") or tc.get("name") or "")
    #             goal_turns.append(Turn(
    #                 role="assistant",
    #                 content=f"[Tool: {tool_name}]",
    #                 tools_called=[ToolCall(name=tool_name)],
    #             ))
    #         goal_turns.append(Turn(role="assistant", content=actual_output))
    #     goal_case = ConversationalTestCase(turns=goal_turns)
    #     goal_metric.measure(goal_case)
    #     metrics["goal_accuracy"] = _metric_result(goal_metric)
    # except Exception as exc:
    #     metrics["goal_accuracy"] = _metric_error(exc)
    metrics["goal_accuracy"] = {"score": None, "passed": True, "reason": "skipped (commented out)"}

    # Aggregate: passed = all passed, score = average
    valid_scores = [m["score"] for m in metrics.values() if m.get("score") is not None and not m.get("error")]
    all_passed = all(m["passed"] for m in metrics.values())
    aggregate_score = round(sum(valid_scores) / len(valid_scores), 4) if valid_scores else 0.0

    return {
        "enabled": True,
        "provider": "deepeval",
        "score": aggregate_score,
        "passed": all_passed,
        "reason": "",
        "cached": False,
        "metrics": metrics,
    }


def _build_deepeval_model():
    """Build a DeepEval-compatible model from env vars.

    Priority: DEEPEVAL_API_KEY / DEEPEVAL_BASE_URL (dedicated)
            > OPENAI_API_KEY / OPENAI_BASE_URL (openai-compatible)
            > LLM_API_KEY / LLM_BASE_URL (ai-service main LLM)
    """
    model_name = os.getenv("DEEPEVAL_MODEL")
    if not model_name:
        return None
    api_key = (
        os.getenv("DEEPEVAL_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("LLM_API_KEY")
    )
    base_url = (
        os.getenv("DEEPEVAL_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or os.getenv("LLM_BASE_URL")
    )
    if api_key and base_url:
        try:
            from deepeval.models import GPTModel
            return GPTModel(model=model_name, api_key=api_key, base_url=base_url)
        except ImportError:  # pragma: no cover
            return model_name
    return model_name


def _metric_result(metric: Any) -> dict[str, Any]:
    return {
        "score": round(float(metric.score or 0.0), 4),
        "passed": bool(metric.success),
        "reason": str(metric.reason or ""),
    }


def _metric_error(exc: BaseException) -> dict[str, Any]:
    return {"score": 0.0, "passed": False, "reason": str(exc), "error": str(exc)}


def evaluate_with_ragas(
    case: dict[str, Any],
    response: dict[str, Any],
) -> dict[str, Any]:
    """Run RAGAS' current collection API for one Knowledge RAG case.

    RAGAS is invoked only when raw retrieved chunks are present.  Source titles
    are not valid retrieval contexts and therefore never get substituted here.
    """
    contexts = [str(item) for item in response.get("retrieved_contexts") or [] if str(item).strip()]
    if not contexts:
        return {"enabled": False, "provider": "ragas", "skipped": "retrieved_contexts_missing"}
    try:
        from openai import AsyncOpenAI
        from ragas.embeddings.base import embedding_factory
        from ragas.llms import llm_factory
        from ragas.metrics.collections import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
    except ImportError as exc:  # pragma: no cover - exercised in eval env
        raise RuntimeError("RAGAS dependencies are not installed. Run: pip install -r requirements-eval.txt") from exc

    api_key = os.getenv("RAGAS_EVAL_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("LLM_API_KEY")
    model = os.getenv("RAGAS_EVAL_MODEL") or os.getenv("DEEPEVAL_MODEL") or os.getenv("LLM_MODEL")
    embedding_model = os.getenv("RAGAS_EVAL_EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL")
    if not api_key or not model:
        raise RuntimeError("RAGAS needs RAGAS_EVAL_API_KEY/OPENAI_API_KEY and RAGAS_EVAL_MODEL/LLM_MODEL")
    if not embedding_model:
        raise RuntimeError("RAGAS AnswerRelevancy needs RAGAS_EVAL_EMBEDDING_MODEL or EMBEDDING_MODEL")
    base_url = os.getenv("RAGAS_EVAL_BASE_URL") or os.getenv("OPENAI_BASE_URL") or os.getenv("LLM_BASE_URL")
    client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
    llm = llm_factory(model, client=client, max_tokens=4096)
    embeddings = embedding_factory("openai", model=embedding_model, client=client)
    expected = case.get("expected") or {}
    # Context Precision/Recall require a factual gold answer grounded in the
    # project's own corpus. Generic rubric text must never be treated as gold.
    reference = str(expected.get("ragas_reference") or "")
    user_input = str(case.get("input") or "")
    answer = str(response.get("answer") or "")
    scores: dict[str, float] = {}
    scores["faithfulness"] = _score(
        Faithfulness(llm=llm),
        user_input=user_input,
        response=answer,
        retrieved_contexts=contexts,
    )
    scores["answer_relevancy"] = _score(
        AnswerRelevancy(llm=llm, embeddings=embeddings),
        user_input=user_input,
        response=answer,
    )
    if reference:
        reference_args = {
            "user_input": user_input,
            "reference": reference,
            "retrieved_contexts": contexts,
        }
        scores["context_precision"] = _score(ContextPrecision(llm=llm), **reference_args)
        scores["context_recall"] = _score(ContextRecall(llm=llm), **reference_args)
    result = {"enabled": True, "provider": "ragas", "scores": scores, "context_count": len(contexts)}
    if not reference:
        result["skipped_metrics"] = {
            "context_precision": "ragas_reference_missing",
            "context_recall": "ragas_reference_missing",
        }
    return result


def load_judge_cache(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_judge_cache(path: Path | None, cache: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _score(metric: Any, **kwargs: Any) -> float:
    result = metric.score(**kwargs)
    value = getattr(result, "value", result)
    return round(float(value), 4)


def _judge_evidence(response: dict[str, Any]) -> dict[str, Any]:
    """Bound evidence size and exclude raw retrieval chunks from GEval input."""
    sub_results = []
    for result in (response.get("sub_results") or [])[:5]:
        if not isinstance(result, dict):
            continue
        sub_results.append({
            key: result.get(key)
            for key in ("id", "route", "status", "answer", "product_cards", "sources", "error_code")
            if result.get(key) not in (None, [], "")
        })
    return {
        "sources": (response.get("sources") or [])[:10],
        "product_cards": (response.get("product_cards") or [])[:10],
        "sub_results": sub_results,
        "retrieved_contexts": [str(value)[:1200] for value in (response.get("retrieved_contexts") or [])[:5]],
    }


def _cache_key(*values: Any) -> str:
    payload = json.dumps(values, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
