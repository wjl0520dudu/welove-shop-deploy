from app.domain.knowledge.agent import KnowledgeAgent


def test_evaluation_contexts_keep_blank_lines_inside_one_chunk():
    context = (
        "[资料1] 来源：商品 A\n"
        "[商品] 商品 A\n\n"
        "[营销描述]\n营销内容\n\n"
        "[资料2] 来源：商品 B\n"
        "[官方FAQ]\nQ：问题？\nA：答案。"
    )

    contexts = KnowledgeAgent._split_evaluation_contexts(context)

    assert len(contexts) == 2
    assert "[营销描述]" in contexts[0]
    assert "\n\n" in contexts[0]
    assert contexts[1].startswith("[资料2] 来源：商品 B")


def test_evaluation_contexts_support_web_headers_without_preamble_context():
    context = (
        "## 网络搜索结果\n"
        "[网络资料1] 来源：站点 A\n内容 A\n\n"
        "[网络资料2] 来源：站点 B\n内容 B"
    )

    contexts = KnowledgeAgent._split_evaluation_contexts(context)

    assert contexts == [
        "[网络资料1] 来源：站点 A\n内容 A",
        "[网络资料2] 来源：站点 B\n内容 B",
    ]
