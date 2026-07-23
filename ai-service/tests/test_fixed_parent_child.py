from app.infrastructure.retrieval.fixed_parent_child import build_fixed_parent_child_records


def test_fixed_parent_child_records_keep_a_parent_child_mapping():
    text = "\n\n".join(f"section {index}: " + ("evidence " * 80) for index in range(1, 8))
    parents, children = build_fixed_parent_child_records(7, text, {"source": "test"})

    assert parents
    assert children
    parent_ids = {parent["parent_id"] for parent in parents}
    assert all(parent["parent_id"].startswith("doc-7:fpc1-p-") for parent in parents)
    assert all(child["parent_id"] in parent_ids for child in children)
    for parent_id in parent_ids:
        indexes = [child["child_index"] for child in children if child["parent_id"] == parent_id]
        assert indexes == list(range(len(indexes)))
