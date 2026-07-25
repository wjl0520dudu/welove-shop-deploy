from scripts.resume_agent_eval import build_merged_report, select_case_ids


def _row(case_id, *, passed=True, response=None, ragas=None):
    return {
        "id": case_id,
        "scenario": "knowledge",
        "tags": [],
        "input": "question",
        "response": response or {"task_type": "knowledge", "answer": "answer"},
        "contract": {"passed": passed, "failure_reasons": [] if passed else ["final_answer"]},
        "judge": {"enabled": False},
        "ragas": ragas or {"enabled": False},
        "retrieval": {"ranked_ids": [], "relevance_grades": {}},
    }


def test_select_case_ids_finds_contract_and_response_failures():
    report = {
        "cases": [
            _row("ok"),
            _row("contract-failed", passed=False),
            _row("response-error", response={"error": True, "error_code": "EVAL_DIRECT_ERROR"}),
        ]
    }
    assert select_case_ids(report, "failed") == ["contract-failed", "response-error"]


def test_select_case_ids_finds_only_ragas_rows_that_can_be_retried():
    report = {
        "cases": [
            _row("done", response={"task_type": "knowledge", "retrieved_contexts": ["ctx"]}, ragas={"enabled": True, "scores": {"faithfulness": 0.8}}),
            _row("missing", response={"task_type": "knowledge", "retrieved_contexts": ["ctx"]}),
            _row("no-context", response={"task_type": "knowledge", "answer": "answer"}),
            _row("failed", passed=False, response={"error": True}),
        ]
    }
    assert select_case_ids(report, "ragas") == ["missing"]


def test_build_merged_report_recomputes_metrics_and_preserves_order(tmp_path):
    source = {"schema_version": "agent-eval-v1", "metadata": {}, "cases": [_row("a"), _row("b", passed=False)]}
    updated_b = _row("b", response={"task_type": "knowledge", "answer": "fixed"})
    result = build_merged_report(
        source,
        [source["cases"][0], updated_b],
        source_path=tmp_path / "source.json",
        dataset=tmp_path / "dataset.jsonl",
        mode="failed",
        selected_case_ids=["b"],
    )
    assert [row["id"] for row in result["cases"]] == ["a", "b"]
    assert result["metrics"]["case_count"] == 2
    assert result["metadata"]["resume"]["rerun_case_ids"] == ["b"]
