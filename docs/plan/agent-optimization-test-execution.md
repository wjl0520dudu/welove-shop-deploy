# Agent 架构优化测试执行手册

> **用途**：按序执行，每步完成打勾，产出可复现的测试结果。
>
> **前置**：PostgreSQL、Milvus、Java chat-service 已启动，LLM/Embedding 密钥可用。
>
> **模型**：deepseek-v4-flash（或同环境任意可用模型）。
>
> **执行方式**：逐条复制命令到终端，观察输出，异常时停下来分析。

---

## 阶段 0：环境确认

```powershell
cd ai-service

# 确认 Python 环境
python --version

# 确认关键配置（不输出密钥）
python -c "from core.config import config; print('MILVUS_COLLECTION:', config.MILVUS_COLLECTION); print('RAG_PARENT_CHILD_ENABLED:', config.RAG_PARENT_CHILD_ENABLED); print('MILVUS_URL:', config.MILVUS_URL)"
```

- [ ] Python 3.11+ 正常
- [ ] `RAG_PARENT_CHILD_ENABLED=false`（默认，旧索引不受影响）
- [ ] Milvus 连接正常

---

## 阶段 1：静态检查 + 现有单元测试

> **目的**：确认所有改动没有语法错误，未破坏现有测试。

### 1.1 语法编译

```powershell
python -m compileall shopping assistant rag knowledge core -q
```

期望：**无输出 = 全部通过**。`exit code 0`。

### 1.2 新模块导入

```powershell
python -c "
from shopping.dispatcher import dispatch_shopping_capability, DispatchDecision
from rag.query_planner import plan_knowledge_query
from rag.parent_child import build_parent_child_records, aggregate_parent_hits, build_local_parent_windows
print('所有新模块导入成功')
"
```

### 1.3 现有单元测试

```powershell
python -m pytest tests/test_recommend_capability.py tests/test_shopping_high_level_tools.py tests/test_assistant_graph.py -v --tb=short 2>&1
```

期望：**全部 PASSED**，无 FAILED/ERROR。

- [ ] 1.1 语法编译通过
- [ ] 1.2 新模块导入成功
- [ ] 1.3 现有测试全绿

---

## 阶段 2：新模块单元测试

> **目的**：验证三个新增模块的纯逻辑正确性，不需要 Milvus/LLM。

### 2.1 Shopping Dispatcher 逻辑

```powershell
python -c "
from shopping.dispatcher import dispatch_shopping_capability

# 1. 交易拒绝
d = dispatch_shopping_capability('帮我加入购物车')
assert d and d.capability == 'transaction_unsupported', f'expected transaction_unsupported, got {d}'
print('[PASS] transaction_unsupported')

# 2. 对比
d = dispatch_shopping_capability('这两个哪个好')
assert d and d.capability == 'compare', f'expected compare, got {d}'
print('[PASS] compare')

# 3. 详情（有记忆时）
d = dispatch_shopping_capability('这个多少钱', {'last_product_cards': [{'product_id':1}]})
assert d and d.capability == 'detail', f'expected detail, got {d}'
print('[PASS] detail (with memory)')

# 4. 详情无记忆 → 不回 detail
d = dispatch_shopping_capability('这个多少钱', {})
assert d is None or d.capability != 'detail', f'expected no detail without memory, got {d}'
print('[PASS] no detail (without memory)')

# 5. 推荐
d = dispatch_shopping_capability('推荐一款防晒')
assert d and d.capability == 'recommend', f'expected recommend, got {d}'
print('[PASS] recommend')

# 6. 用户上下文
d = dispatch_shopping_capability('我的收藏有什么')
assert d and d.capability == 'user_context', f'expected user_context, got {d}'
print('[PASS] user_context')

# 7. 模糊请求 → None（走 LLM 兜底）
d = dispatch_shopping_capability('你好')
assert d is None, f'expected None for ambiguous, got {d}'
print('[PASS] ambiguous → None')

print('全部 Dispatcher 断言通过')
"
```

### 2.2 Query Planner 逻辑

```powershell
python -c "
from rag.query_planner import plan_knowledge_query

# 1. A醇 → 视黄醇
plan, qp = plan_knowledge_query('A醇怎么用')
assert '视黄醇' in qp.rewritten_query, f'A醇 should become 视黄醇, got: {qp.rewritten_query}'
print('[PASS] A醇 → 视黄醇')

# 2. 退换货 → doc_types 含 policy
plan, qp = plan_knowledge_query('退换货说明')
assert 'policy' in (qp.hard_filters.doc_types or []), f'expected policy, got: {qp.hard_filters.doc_types}'
print('[PASS] 退换货 → policy')

# 3. 敏感肌 → soft_terms
plan, qp = plan_knowledge_query('敏感肌使用VC要注意什么')
assert '敏感肌' in qp.soft_terms, f'expected 敏感肌 soft term, got: {qp.soft_terms}'
assert '维生素C' in qp.rewritten_query, f'VC should become 维生素C, got: {qp.rewritten_query}'
print('[PASS] 敏感肌 soft term + VC 标准化')

# 4. 普通查询不触发改写
plan, qp = plan_knowledge_query('防晒霜怎么选')
assert '防晒霜' in qp.rewritten_query or '防晒' in qp.rewritten_query
print('[PASS] 普通查询不误改')

print('全部 Query Planner 断言通过')
"
```

### 2.3 父子分块逻辑

```powershell
python -c "
from rag.parent_child import build_parent_child_records, aggregate_parent_hits, build_local_parent_windows

# 1. 构建父/子块
text = '''## 使用方法
取适量产品涂抹于面部，早晚各一次。

## 注意事项
避免接触眼睛。如出现红肿请立即停用。'''
parents, children = build_parent_child_records(1, text, {'source': 'test.md', 'doc_type': 'manual'})

assert len(parents) > 0, 'must produce parent chunks'
assert len(children) > 0, 'must produce child chunks'
assert all(c['parent_id'] for c in children), 'every child must have parent_id'
assert all(c['parent_id'].startswith('doc-1:p-') for c in children), 'parent_id format wrong'
print(f'[PASS] 父块={len(parents)}, 子块={len(children)}')

# 2. 聚合同一父块的多个子块命中
hits = [
    {'parent_id': parents[0]['parent_id'], 'rerank_score': 0.95, 'content': children[0]['content']},
    {'parent_id': parents[0]['parent_id'], 'rerank_score': 0.80, 'content': children[1]['content']},
]
groups = aggregate_parent_hits(hits, limit=3)
assert len(groups) == 1, 'same parent_id should merge into one group'
print(f'[PASS] 聚合后 {len(groups)} 组')

# 3. 构建局部窗口
parent_map = {p['parent_id']: p for p in parents}
windows = build_local_parent_windows(parent_map, groups, max_chars=12000)
assert len(windows) > 0, 'must produce parent windows'
print(f'[PASS] 生成 {len(windows)} 个父块窗口')

print('全部父子分块断言通过')
"
```

- [ ] 2.1 Dispatcher 7 个断言全部通过
- [ ] 2.2 Query Planner 4 个断言全部通过
- [ ] 2.3 父子分块 3 个断言全部通过

---

## 阶段 3：集成测试

> **目的**：验证改动在实际 LLM + Milvus + PG 环境下的行为。需要 AI 服务运行。

### 3.1 启动 AI 服务

```powershell
# 终端 1：启动 AI 服务
cd ai-service
python -m main
# 等待看到 "Uvicorn running on http://0.0.0.0:8000"
```

### 3.2 Shopping Dispatcher 集成

```powershell
# 测试 1：推荐 → 期望 capability=recommend
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"推荐一款200元以内的防晒霜","conversation_id":"test-disp-1"}' \
  | grep -o '"capability":"[^"]*"' | head -1

# 测试 2：加购 → 期望 transaction_unsupported
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"帮我加入购物车","conversation_id":"test-disp-2"}' \
  | grep -o '"capability":"[^"]*"' | head -1

# 测试 3：对比 → 期望 capability=compare
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"第一和第二款哪个好","conversation_id":"test-disp-3","user_id":1}' \
  | grep -o '"capability":"[^"]*"' | head -1
```

### 3.3 商品硬约束集成

```powershell
# 测试 4：200 元以内 → 所有卡片 price <= 200
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"推荐200元以内的护肤品","conversation_id":"test-hard-1"}' \
  > /tmp/resp.json
python -c "
import json
with open('/tmp/resp.json') as f:
    data = json.load(f)
cards = data.get('product_cards', [])
violations = [c for c in cards if float(c.get('price', c.get('base_price', 0))) > 200]
assert not violations, f'FOUND {len(violations)} cards over budget!'
print(f'OK: {len(cards)} cards, all <= 200')
"
```

### 3.4 Knowledge Query Planner 集成

```powershell
# 测试 5：search_knowledge 返回 query_plan
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"A醇怎么用","conversation_id":"test-qp-1"}' \
  | grep -o '"query_plan"[^}]*}'
```

### 3.5 现有 E2E 脚本

```powershell
python scripts/verify_shopping_e2e.py
python scripts/verify_shopping_focus_and_compare.py
```

- [ ] 3.2 推荐 → capability=recommend
- [ ] 3.2 加购 → capability=transaction_unsupported
- [ ] 3.3 所有卡片价格 ≤ 200
- [ ] 3.4 search_knowledge 返回 query_plan
- [ ] 3.5 verify_shopping_e2e 通过
- [ ] 3.5 verify_shopping_focus_and_compare 通过

---

## 阶段 4：父子分块迁移（独立测试）

> **目的**：验证新 collection 的构建、检索和评测。**不影响旧索引**。

### 4.0 修改 .env 切换 collection

```powershell
# 在 ai-service/.env 中临时修改（测试完恢复）
# MILVUS_COLLECTION=knowledge_parent_child_v1
# RAG_PARENT_CHILD_ENABLED=true
```

### 4.1 Dry Run

```powershell
python scripts/reindex_knowledge_parent_child.py --dry-run --limit 2
```

期望：每篇文档 parent > 0 且 child > 0，无异常。

### 4.2 冒烟导入

```powershell
python scripts/reindex_knowledge_parent_child.py --source all --limit 2 --replace
```

### 4.3 阻断检查

```powershell
python -c "
from rag.vector_store import MilvusVectorStore
store = MilvusVectorStore()

# 1. 有数据
stats = store.stats()
assert stats.get('row_count', 0) > 0, 'collection is empty'
print(f'[CHECK 1] row_count={stats[\"row_count\"]}')

# 2. 同一 doc_id 同时有 parent 和 child
from pymilvus import Collection
col = Collection(store.collection_name)
col.load()
rows = col.query(expr='doc_id == 900001', output_fields=['chunk_type', 'parent_id', 'child_index'], limit=100)
types = set(r['chunk_type'] for r in rows)
assert 'parent' in types and 'child' in types, f'missing chunk types: {types}'
print(f'[CHECK 2] chunk_types={types}')

# 3. child 有 parent_id
child_rows = [r for r in rows if r['chunk_type'] == 'child']
assert all(r.get('parent_id') for r in child_rows), 'child missing parent_id'
print(f'[CHECK 3] {len(child_rows)} children all have parent_id')

# 4. 检索可用
hits = store.search('敏感肌使用视黄醇注意事项', top_k=5)
assert len(hits) > 0, 'search returned no results'
print(f'[CHECK 4] search returned {len(hits)} hits')
for h in hits[:3]:
    has_pid = bool(h.metadata.parent_id)
    print(f'  chunk_type={h.metadata.chunk_type}, parent_id={has_pid}, score={h.score:.4f}')
"
```

### 4.4 重启 AI 服务并测检索

```powershell
# 重启 AI 服务（新 .env 生效）
# 然后发起知识检索请求
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"敏感肌可以用视黄醇吗","conversation_id":"test-pc-1"}' \
  | grep -o '"retrieved_contexts"'
```

### 4.5 恢复旧配置

```powershell
# .env 恢复为：
# MILVUS_COLLECTION=my_rag_collection
# RAG_PARENT_CHILD_ENABLED=false
# 重启 AI 服务
```

- [ ] 4.1 Dry run 成功
- [ ] 4.2 冒烟导入成功
- [ ] 4.3 阻断检查全部通过
- [ ] 4.4 检索返回 retrieved_contexts
- [ ] 4.5 旧配置恢复并验证

---

## 阶段 5：DAG 证据契约测试

> **目的**：验证子任务结果包含 execution_contract 和 evidence。

```powershell
# 发送复合请求（多 Agent 并行）
curl -s -X POST http://localhost:8000/api/assistant/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question":"推荐一款防晒霜，并解释防晒霜的SPF值是什么意思","conversation_id":"test-dag-1","user_id":1}' \
  > /tmp/dag.json

python -c "
import json
with open('/tmp/dag.json') as f:
    data = json.load(f)

# 1. sub_results 存在
assert 'sub_results' in data or data.get('task_type') == 'orchestrator', 'not an orchestrator response'
subs = data.get('sub_results', [])
print(f'sub_results: {len(subs)} items')

# 2. 每个 sub_result 有 execution_contract
for sub in subs:
    ec = sub.get('execution_contract')
    if ec:
        print(f'  [{sub[\"id\"]}] status={ec.get(\"status\")}, evidence={len(ec.get(\"evidence\",[]))}, route={ec.get(\"route\")}')
    else:
        print(f'  [{sub[\"id\"]}] WARNING: no execution_contract')

# 3. evidence 存在
for sub in subs:
    ev = sub.get('evidence', [])
    if ev:
        print(f'  [{sub[\"id\"]}] evidence: {len(ev)} items')
        for e in ev[:2]:
            print(f'    kind={e.get(\"kind\")}, ref_id={e.get(\"ref_id\")}')
"
```

- [ ] 5.1 sub_results 包含 execution_contract
- [ ] 5.2 evidence 非空
- [ ] 5.3 evidence.kind 和 evidence.ref_id 正确

---

## 阶段 6：完整评测

> **目的**：跑 142 条 golden case，产出 V2.3 基线。

### 6.1 跑评测

```powershell
python -m evals.run_agent_eval --direct --deepeval --ragas 2>&1 | tee /tmp/eval-v2.3.log
```

### 6.2 对比 V2.2 基线

```powershell
# 查看关键指标
python -c "
import json
from pathlib import Path
from evals.agent_metrics import calculate_agent_metrics

# 加载最新报告
reports = sorted(Path('evals/reports').glob('agent-v2.3*.json'))
if reports:
    report = json.loads(reports[-1].read_text())
    print('=== V2.3 关键指标 ===')
    print(f'Contract Pass Rate: {report.get(\"contract_pass_rate\", \"N/A\")}')
    print(f'Task Success Rate: {report.get(\"task_success_rate\", \"N/A\")}')
    # 按场景分解
    by_scenario = report.get('by_scenario', {})
    for scenario, metrics in by_scenario.items():
        tc = metrics.get('task_completion', {}).get('mean', 'N/A')
        tr = metrics.get('tool_correctness', {}).get('mean', 'N/A')
        cr = metrics.get('contract_pass_rate', 'N/A')
        print(f'  {scenario}: Contract={cr}, TC={tc}, TR={tr}')
"
```

### 6.3 与 V2.2 关键指标比较

| 指标 | V2.2 基线 | V2.3 目标 | 实际 |
|---|---|---|---|
| Shopping Tool Correctness | 0.4348 | ≥ 0.70 | ___ |
| Shopping Task Success | 30.43% | ≥ 55% | ___ |
| Multi-Agent Tool Correctness | 0.4167 | ≥ 0.65 | ___ |
| Context Precision | 0.404 | ≥ 0.60 | ___ |
| Faithfulness | 0.6672 | ≥ 0.75 | ___ |
| Knowledge P95 | 18.2s | 不恶化超 15% | ___ |

- [ ] 6.1 评测全部完成
- [ ] 6.2 指标已提取
- [ ] 6.3 对比表已填写

---

## 附录 A：阻塞问题速查

| 现象 | 可能原因 | 检查 |
|---|---|---|
| compileall 报 SyntaxError | 文件编码或缩进问题 | 用 IDE 打开报错文件检查 |
| dispatch_shopping_capability 返回 None | 缓存/环境未 refresh | 重启 Python 进程 |
| 导入 shopping.capabilities 失败 | 缺 capability 模块文件 | 检查 `shopping/capabilities/` 目录 |
| 卡片价格超预算 | relaxed recall 残留 | 检查 `_enforce_hard_filters` 是否被调用 |
| parent_child 检索无结果 | collection 未建或 schema 不匹配 | 检查 `MILVUS_COLLECTION` 和 `RAG_PARENT_CHILD_ENABLED` |
| execution_contract 缺失 | 子任务非 orchestrator 模式 | 确认请求触发了 complex 分支 |

## 附录 B：快速回退

```powershell
# 恢复旧配置
# .env: MILVUS_COLLECTION=my_rag_collection
# .env: RAG_PARENT_CHILD_ENABLED=false
# 重启 AI 服务
```

父子分块的新 collection `knowledge_parent_child_v1` 保留不删，用于后续调优。