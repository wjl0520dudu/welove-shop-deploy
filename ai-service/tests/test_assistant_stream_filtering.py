import pytest
from langchain_core.messages import AIMessageChunk

from app.application.assistant import AssistantGraph


async def _collect_events(chunk, meta=None, namespace=()):
    graph = AssistantGraph.__new__(AssistantGraph)
    events = []
    async for event in graph._translate_message_event(chunk, meta or {}, namespace):
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_stream_allows_model_token_chunks():
    events = await _collect_events(
        AIMessageChunk(content="你好"),
        {"langgraph_node": "model"},
        ("shopping", "agent"),
    )

    assert events == [{"type": "token", "data": {"content": "你好"}}]


@pytest.mark.asyncio
async def test_stream_suppresses_internal_structured_output():
    events = await _collect_events(
        AIMessageChunk(content='{"category": "鞋子"}'),
        {"metadata": {"tags": ["ai_internal"]}, "langgraph_node": "model"},
        ("shopping", "tools"),
    )

    assert events == []


@pytest.mark.asyncio
async def test_stream_suppresses_tool_node_output_without_tags():
    events = await _collect_events(
        AIMessageChunk(content='{"category": "鞋子"}'),
        {"langgraph_node": "tools"},
        ("shopping", "tools"),
    )

    assert events == []


@pytest.mark.asyncio
async def test_stream_suppresses_main_graph_message_writeback():
    events = await _collect_events(
        AIMessageChunk(content="为你精选了3款热门运动鞋"),
        {"langgraph_node": "shopping"},
        (),
    )

    assert events == []
