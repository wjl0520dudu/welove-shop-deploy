"""Smoke-test script for knowledge_recursive_v1 chunking + retrieval quality.

验证分块质量和检索效果，覆盖以下场景：
- Markdown 标题段落
- 普通段落
- 超长单段落（触发递归切割）
- 中文标点密集文本
- 无空格长文本（英文/代码类）

用法:
    cd ai-service
    export MILVUS_COLLECTION=knowledge_recursive_v1
    export RAG_PARENT_CHILD_ENABLED=false
    python scripts/smoke_test_recursive_v1.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.knowledge.recursive_chunk import build_recursive_chunks_from_text, split_recursive_text
from app.infrastructure.vectorstores.knowledge.vector_store import MilvusVectorStore
from app.domain.knowledge.models import RetrievalPlan

# 5 个冻结知识问题的 doc_id 参考（来自 v2.1/v2.3 retrieval_grades）
# 用于验证检索召回是否命中正确文档
SMOKE_CASES = [
    {
        "case_id": "rag-001",
        "query": "烟酰胺有什么作用",
        "doc_ids": [100018, 100008, 100009],  # expected top doc_ids (from v2.1/v2.3)
        "scenario": "ingredient term — short paragraph split",
    },
    {
        "case_id": "rag-007",
        "query": "视黄醇能和维C一起用吗",
        "doc_ids": [100016, 100005, 900003],
        "scenario": "compatibility — medium paragraph, Chinese punctuation",
    },
    {
        "case_id": "rag-008",
        "query": "果酸能和视黄醇一起用吗",
        "doc_ids": [900003, 100005, 100012],
        "scenario": "compatibility — long paragraph, mixed punctuation",
    },
    {
        "case_id": "rag-013",
        "query": "精华应该在哪一步用",
        "doc_ids": [100016, 100001],
        "scenario": "usage — short general question",
    },
    {
        "case_id": "rag-015",
        "query": "防晒霜多久涂一次",
        "doc_ids": [100023],
        "scenario": "usage frequency — short answer question",
    },
]

# 分块质量测试文本
CHUNK_QUALITY_TESTS = [
    {
        "name": "Markdown 标题 + 段落",
        "text": "## 保湿成分\n\n透明质酸是护肤品中常见的锁水保湿成分，能吸附自身重量数百倍的水分。\n\n神经酰胺则帮助修复皮肤屏障。",
        "expected_min_chunks": 2,
    },
    {
        "name": "超长单段落（触发递归切割）",
        "text": "视黄醇是维生素A衍生物，用于抗初老、淡纹、加速角质更新。建议晚间使用，配合防晒；初次使用应从低浓度开始建立耐受，避免同时叠加高浓度酸类。视黄醇孕期不建议使用，可能对胎儿存在潜在风险。视黄醇与维C不建议同时使用，尤其早晚同用会互相削弱效果或增加刺激。推荐早上用维C（抗氧化+防晒配合），晚上用视黄醇（抗初老+修护）。果酸和视黄醇都是活性成分，同时使用会显著增加刺激。建议错开时间（比如隔天）或错开早晚，且必须做好防晒。敏感肌应避免叠加。".encode("utf-8").decode("utf-8"),
        "expected_max_chunk_len": 550,  # should not exceed chunk_size by much
    },
    {
        "name": "中文标点密集",
        "text": "烟酰胺的主要作用包括：调节皮脂分泌、控油缩毛孔；抑制黑色素向表皮转移，起到美白提亮；辅助修护屏障。推荐日常浓度2%-5%，10%可能引起刺激，敏感肌建议先耳后测试。",
        "expected_min_chunks": 1,
    },
    {
        "name": "无空格英文长词",
        "text": "Recursivelysplitcharactertextsplitterisdesignedtohighlevelsemanticunitsfirstbeforesplittingintosmallercharacterlevelunits.Thisapproachproducesthesemanticallycoherentchunksbetterthanfixedsizechunking.",
        "expected_min_chunks": 2,
    },
]


def test_chunking_quality():
    print("=" * 60)
    print("分块质量冒烟测试")
    print("=" * 60)
    all_passed = True
    for t in CHUNK_QUALITY_TESTS:
        chunks = split_recursive_text(t["text"], chunk_size=500, chunk_overlap=50)
        chunk_lens = [len(c) for c in chunks]
        print(f"\n[{t['name']}]")
        print(f"  原始长度 : {len(t['text'])} chars")
        print(f"  分块数   : {len(chunks)}")
        if chunk_lens:
            print(f"  Chunk 长度: min={min(chunk_lens)}, max={max(chunk_lens)}, avg={sum(chunk_lens)/len(chunk_lens):.0f}")
        for i, c in enumerate(chunks):
            print(f"  Chunk {i}: [{len(c)}] {c[:80]!r}...")
        # Check constraints
        if "expected_min_chunks" in t and len(chunks) < t["expected_min_chunks"]:
            print(f"  FAIL: expected >= {t['expected_min_chunks']} chunks, got {len(chunks)}")
            all_passed = False
        if "expected_max_chunk_len" in t:
            max_len = max(chunk_lens) if chunk_lens else 0
            if max_len > t["expected_max_chunk_len"]:
                print(f"  FAIL: max chunk len {max_len} exceeds {t['expected_max_chunk_len']}")
                all_passed = False
            else:
                print(f"  PASS: max chunk len {max_len} <= {t['expected_max_chunk_len']}")
    print()
    return all_passed


def test_retrieval(collection_name: str):
    print("=" * 60)
    print(f"检索冒烟测试 (collection={collection_name})")
    print("=" * 60)

    # Use Retriever which implements the actual two-stage (hybrid → rerank) pipeline
    from app.infrastructure.retrieval.retriever import Retriever
    vs = MilvusVectorStore(collection_name=collection_name)
    retriever = Retriever(vector_store=vs)
    print(f"[OK] 向量库就绪: {vs.stats()}\n")

    all_passed = True
    for case in SMOKE_CASES:
        print(f"\nCase [{case['case_id']}]: {case['scenario']}")
        print(f"  Query: {case['query']}")
        print(f"  Expected doc_ids: {case['doc_ids']}")

        # Two-stage retrieval matching experiment config
        plan = RetrievalPlan(
            query=case["query"],
            top_k=5,
            search_mode="hybrid",
            use_rerank=True,
            initial_top_k=20,
        )
        output = retriever.retrieve(plan)

        top5_doc_ids = [s.doc_id for s in output.sources[:5]]
        top5_scores = [s.score for s in output.sources[:5]]
        print(f"  Hybrid+Rerank Top5 doc_ids: {top5_doc_ids}")
        print(f"  Scores                    : {[round(s, 3) for s in top5_scores]}")

        # Also show top20 raw (before rerank) doc_ids
        top20_doc_ids = [s.doc_id for s in output.sources]
        print(f"  Top20 raw doc_ids         : {top20_doc_ids[:10]}...")

        # Check if expected doc_ids appear in top5
        hits = [did for did in case["doc_ids"] if did in top5_doc_ids]
        if hits:
            print(f"  HIT: doc_ids {hits} found in top5")
        else:
            print(f"  MISS: none of {case['doc_ids']} in top5")
            # Also check top20 for diagnostic
            hits20 = [did for did in case["doc_ids"] if did in top20_doc_ids]
            if hits20:
                print(f"  NOTE: {hits20} found in top20 (rerank pushed them out)")
            else:
                print(f"  NOTE: none of {case['doc_ids']} found in top20 either")
            all_passed = False

    print()
    return all_passed


def main():
    import os
    collection = os.getenv("MILVUS_COLLECTION", "knowledge_recursive_v1")
    print(f"Using collection: {collection}\n")

    chunking_ok = test_chunking_quality()
    retrieval_ok = test_retrieval(collection)

    print("=" * 60)
    print("冒烟测试结果")
    print("=" * 60)
    print(f"  分块质量: {'PASS' if chunking_ok else 'FAIL'}")
    print(f"  检索召回: {'PASS' if retrieval_ok else 'FAIL'}")
    if chunking_ok and retrieval_ok:
        print("\n✅ 冒烟测试通过，可以继续正式评测")
    else:
        print("\n❌ 冒烟测试失败，请检查分块或检索配置")

    return 0 if (chunking_ok and retrieval_ok) else 1


if __name__ == "__main__":
    sys.exit(main())
