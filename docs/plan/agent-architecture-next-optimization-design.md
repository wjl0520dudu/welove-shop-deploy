# Agent 架构后续优化设计（MVP）

> 状态：设计稿，尚未实施。
>
> 目的：在不推翻已完成的任务级路由、DAG 编排、个性化与评测闭环的前提下，处理当前评测中最影响体验的 Shopping 工具选择、严格约束、图文检索一致性、RAG 上下文质量和多 Agent 聚合问题。
>
> 适用范围：`ai-service`。商品事实仍以商品服务/PostgreSQL 为准；知识库检索使用 Milvus；不在本阶段新增真实加购、下单或支付执行能力。

---

## 1. 当前基线与问题排序

### 1.1 已有能力

当前主图位于 `ai-service/assistant/graph.py`：

```text
用户请求
  └─ analyze_request
       ├─ simple  → route_intent → Shopping / Knowledge / Chitchat
       └─ complex → Orchestrator 生成任务 DAG
                         → 按拓扑层级并发执行子任务
                         → 依赖结果注入
                         → synthesize_final 聚合
```

- 路由：高置信规则优先，Structured LLM Router 兜底，低置信度澄清；
- 编排：DAG ID/依赖/环/深度校验、并发、超时与失败隔离；
- Shopping：`create_agent` 挂载推荐、对比、详情、用户上下文四个高层工具；
- Knowledge：`create_agent` 挂载知识检索与指代消解，已有 Hybrid 检索、Rerank、外部搜索兜底和 grounding check；
- 图文商品检索：多模态召回、LLM-as-Judge 过滤和个性化重排；
- 评测：Contract、DeepEval Agent 指标、RAGAS 和统一报告已落地。

### 1.2 本地 Phase 4 基线（V2.2）

以下数值来自本地文件 `docs/phase-test-results.local.md`，只能作为后续同数据集、同环境下的对比基线，不能包装为线上指标：

| 场景 | Task Success / Pass@1 | Tool Correctness | 主要问题 |
|---|---:|---:|---|
| Shopping | 30.43% | 0.4348 | 漏调/错调推荐、对比、详情能力 |
| Multi-Agent | 33.33% | 0.4167 | 子任务工具选择与聚合链路不稳定 |
| Knowledge | 71.88% | 0.8438 | 召回到文档后，最终上下文仍不够精确 |
| Multimodal Shopping | 60.00% | 0.8000 | 图文链路未统一复用文本侧结构化约束 |

RAG 专项结果：`Recall@5=0.8646`、`MRR@5=0.8958`、`NDCG@5=0.8489`，但 `Context Precision=0.404`、`Faithfulness=0.6672`。这说明“相关文档大多能找到”，但“交给生成模型的片段组织”仍是瓶颈。

### 1.3 优先级

1. **P0：Shopping Hybrid Capability Dispatcher + 严格约束闭环。** 直接针对最低的 Tool Correctness 和商品卡片约束错误。
2. **P1：多模态商品检索复用结构化需求与约束。** 让“按图找同款且预算 200 元内”具备确定语义。
3. **P1：Knowledge Query Planner + 父子分块。** 对症改善 Context Precision，而不是重复堆叠召回通道。
4. **P1：DAG 任务结果契约与证据约束聚合。** 减少多 Agent 中“上游自然语言结论污染下游”的问题。
5. **P2：延迟、观测和代码边界治理。** 在核心正确性改善后再做。

---

## 2. Shopping：Hybrid Capability Dispatcher

### 2.1 目标与边界

这不是删除 `ShoppingAgent`，也不是把系统退化为纯规则。目标是将**高确定性的能力选择**收紧，而将模糊理解、补槽、解释、追问和复杂组合需求保留给 LLM。

现状中，`ShoppingAgent` 通过 `create_agent` 将以下工具交给模型自由选择：

```python
SHOPPING_HIGH_LEVEL_TOOLS = [
    recommend_products,
    compare_products,
    answer_product_detail,
    get_user_shopping_context,
]
```

这使工具选择成为不稳定的生成式步骤。应改为如下 Hybrid 策略：

```text
用户请求 / DAG 子任务
  → Capability Dispatcher
      ├─ 高确定性规则：直接确定 action
      ├─ 模糊或复合：LLM 输出受 Schema 约束的 action
      └─ 无法判定：clarify
  → Capability 执行真实业务工具
  → 基于事实结果组织自然语言答案
```

### 2.2 Action Schema

新增独立的业务动作模型，不复用顶层 `IntentDecision`：

```python
class ShoppingAction(BaseModel):
    capability: Literal["recommend", "compare", "detail", "user_context", "clarify"]
    confidence: float = Field(ge=0, le=1)
    reason: str
    product_ids: list[int] = []
    requested_fields: list[Literal["price", "stock", "sku", "ingredients", "overview"]] = []
```

推荐规则优先级：

| 条件 | 结果 | 备注 |
|---|---|---|
| 有图片且任务允许使用图片 | `recommend` | 进入多模态推荐能力，而不是让文本 Agent 决定是否看图 |
| 明确“对比/哪个好/前两款”且能解析到至少两件商品 | `compare` | 无法解析商品时澄清 |
| 明确“多少钱/库存/规格/成分/第二款”且能定位单品 | `detail` | 不能定位时澄清 |
| 明确“推荐/找/买/适合我/预算” | `recommend` | 由能力内部解析 `ShoppingNeed` |
| 明确要求查看收藏、历史、订单 | `user_context` | 只读，不执行交易 |
| 其余情况 | Structured LLM Router | 仅在这里支付一次模型决策成本 |

### 2.3 执行形态

第一版建议作为 `ShoppingAgent.run()` 内部策略，不立刻删除 `create_agent`：

```python
async def run(...):
    action = await shopping_action_dispatcher(question, business_memory)

    if action.capability == "recommend":
        result = await RecommendCapability().run(...)
    elif action.capability == "compare":
        result = await CompareCapability().run(...)
    elif action.capability == "detail":
        result = await DetailCapability().run(...)
    elif action.capability == "user_context":
        result = await UserShoppingContextCapability().run(...)
    else:
        return clarify_result(...)

    return await compose_grounded_shopping_answer(question, action, result)
```

其中 `compose_grounded_shopping_answer` 可先保留 `create_agent` 作为最终表达层；但它**不再允许选择或重复执行工具**。若不需要个性化话术，可直接使用能力返回的确定性文案，进一步降低延迟。

### 2.4 与 DAG 的关系

对 Orchestrator 已生成且通过校验的 `intent_hint`：

- 保持目前“可信 `intent_hint` 避免再调用顶层 Router”的优化；
- 在 Shopping 子任务内部继续通过 Dispatcher 选择 `recommend/compare/detail`；
- 后续可将 `capability_hint` 加入 `OrchestratorTask`，但不是第一阶段必需条件；
- 明确规则可覆盖错误 hint，例如任务中出现“比较前两件商品”时不可误走推荐。

### 2.5 验收

- Shopping Tool Correctness：`0.4348 → >= 0.70`；
- Shopping Task Success：`30.43% → >= 0.55`；
- 推荐、对比、详情 golden case 中不得出现错误 capability；
- 保留 `tool_calls`、`capability`、`dispatch_source`（rule/llm/clarify）和 `reason` 以供 Contract/DeepEval 评估。

---

## 3. 商品检索：硬约束、软偏好与事实校验

### 3.1 当前已有实现与缺口

商品检索不是知识库侧的 `MetadataFilter`，而是 `ShoppingRetrievalPlan.filters`，随后被 `build_milvus_filter_expr()` 转成 Milvus `expr`。当前已支持：类目、子类目、品牌、价格区间、评分、商品 ID、上架状态。

例如“推荐一双 200 元以内的鞋”当前可以生成：

```text
(category == "鞋子" || sub_category == "鞋子")
&& base_price <= 200
&& status == 1
```

问题在于候选不足时，当前 relaxed recall 会将 `budget_max` 扩到 `1.2 倍`，甚至仅保留类目。这不应适用于用户本轮明确表达的“200 元以内”。

### 3.2 Filter Contract

新增商品专用的过滤语义，不与 RAG `MetadataFilter` 混用：

```python
class ProductFilterPlan(BaseModel):
    # 用户本轮明确说出的不可违反条件
    hard: ProductHardFilter
    # 可影响排序，允许放宽
    soft_preferences: ProductSoftPreference
    # 每个字段是否可放宽，默认 false
    relaxation_policy: dict[str, bool]

class ProductHardFilter(BaseModel):
    category: str | None = None
    category_id: int | None = None
    product_id: int | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    status: int = 1
```

执行规则：

1. 当前 query 明确给出的预算、商品 ID、上架状态必须是 hard filter，禁止放宽；
2. 能精确映射的类目也是 hard filter；映射失败时只允许移除类目 **检索过滤** 来救回语义候选，但最终仍须由结构化类目事实校验；
3. 画像预算、品牌、颜色、风格、场景只作为 soft preference，不得覆盖当前 query；
4. `rerank` 和个性化之后，出卡前以商品服务/数据库的当前字段做 final validation；
5. 条件严格导致候选不足时，返回少于 `top_k` 的真实结果，并提示用户放宽条件；禁止为了凑数量输出违反 hard filter 的商品。

### 3.3 图文检索接入同一 Contract

当前图片请求绕过文本 ShoppingAgent Tool Loop，直接走多模态检索、Judge、偏好重排。这一决定保留，但图文链路必须也解析 `ShoppingNeed + ProductFilterPlan`：

```text
图片 + 文本描述
  → 结构化需求 / ProductFilterPlan
  → 带 Milvus expr 的图文三路召回
  → RRF
  → 基于商品结构化字段的 LLM-as-Judge
  → 个性化软重排
  → 数据库事实终检
```

例如“找图中同款，200 元内”：图像相似度负责候选相似性；`price <= 200`、`status=1` 负责检索前约束；Judge 只读商品名称、类目、品牌、描述、价格等结构化事实判断相关性，不额外调用 VL 模型，从而控制成本。

### 3.4 验收

- 增加 `strict_budget`、`strict_category`、`image_plus_budget` Contract cases；
- 任意最终商品卡片都满足用户显式 hard filter；
- 检索 trace 必须记录 `hard_filters`、`soft_preferences`、`relaxed_fields` 和 `final_validation`；
- 预算严格 case 不因召回不足出现超预算商品。

---

## 4. Knowledge：Query Planner 与父子分块

### 4.1 参考来源与采用范围

本节明确参考用户提供的文章：

- [《面试必考！RAG 知识库全链路深度解析：父子分块 × Rerank × 查询重写 × 标准化改写》](https://juejin.cn/post/7646397474869329971)

文章中的核心顺序为：**父块保存完整语境，子块向量化并携带 `parent_id`；先检索与 Rerank 子块，再按 `parent_id` 回查父块；同一父块的多个命中子块做去重/聚合。**

本项目会保留该顺序和关键数据结构，但将文章示例中的 LangChain/Qdrant 存储实现适配为当前 `rag/document_pipeline.py`、`rag/vector_store.py`、Milvus 和 PostgreSQL/现有文档存储。不会为了照搬文章引入 Qdrant 或第二套向量库。

### 4.2 为什么现在做

当前知识库的文档级指标已经不错，但 RAGAS Context Precision 很低。这说明不是首先缺少“多查几次”，而是需要同时满足：

- **子块小**：让 query 与具体段落语义对齐，减少噪声；
- **父块完整**：让生成模型获得必要的标题、小节、前后语境，避免只看到半句话；
- **先子后父**：Reranker 面对短子块更精准、更省；父块只用于最终供料，不能先拿长文去 Rerank。

### 4.3 数据模型

建议把“父块”理解为**文档结构中的局部语义窗口**，不是整篇文档或整章。每个父块包含标题路径与有限正文；多个子块属于该父块。

```python
class ParentChunk(BaseModel):
    parent_id: str                 # e.g. "doc-42:p-0007"
    doc_id: int
    doc_name: str
    heading_path: list[str]        # ["A 醇", "使用方法", "注意事项"]
    content: str                   # 建议约 800~1200 tokens 的局部窗口
    start_offset: int
    end_offset: int
    category_id: int | None = None
    doc_type: str = "text"
    content_hash: str
    index_version: str

class ChildChunk(BaseModel):
    chunk_id: str                  # e.g. "doc-42:p-0007:c-0002"
    parent_id: str
    doc_id: int
    content: str                   # 建议约 180~350 tokens，带少量 overlap
    child_index: int
    metadata: dict
```

Milvus 保存 `ChildChunk.content` 的向量和可过滤 metadata：`chunk_id`、`parent_id`、`doc_id`、`category_id`、`doc_type`、`chunk_type`、`index_version`；父块原文由 PostgreSQL/文档存储保存。若初期不想增加新表，可先将父块以 `chunk_type="parent"` 存入现有文档存储，检索时仅在 Milvus 搜 child。

### 4.4 入库实现（参考文章的父/子层次，适配当前项目）

文章使用递归分割器生成父块与子块，并让子块携带 `parent_id`。下列代码是本项目的适配版骨架；实际 token 计数需复用项目的 tokenizer/embedding 模型，而不能简单按字符数上线。

```python
# ai-service/rag/parent_child_chunker.py  （拟新增）
from __future__ import annotations

from dataclasses import dataclass
from langchain_text_splitters import RecursiveCharacterTextSplitter


PARENT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=160,
    separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", "，", ""],
)
CHILD_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=320,
    chunk_overlap=48,
    separators=["\n\n", "\n", "。", "；", "，", ""],
)


def build_parent_child_chunks(doc_id: int, text: str, base_meta: dict) -> tuple[list[dict], list[dict]]:
    """参考文章：父块保存语境，子块带 parent_id 进入向量库。"""
    parents: list[dict] = []
    children: list[dict] = []

    for parent_index, parent_text in enumerate(PARENT_SPLITTER.split_text(text)):
        parent_id = f"doc-{doc_id}:p-{parent_index:04d}"
        parent = {
            "parent_id": parent_id,
            "doc_id": doc_id,
            "content": parent_text,
            "heading_path": infer_heading_path(parent_text, base_meta),
            **base_meta,
        }
        parents.append(parent)

        # 文章的关键点：child 才参与向量检索，且 child 持有 parent_id。
        for child_index, child_text in enumerate(CHILD_SPLITTER.split_text(parent_text)):
            children.append({
                "chunk_id": f"{parent_id}:c-{child_index:04d}",
                "parent_id": parent_id,
                "doc_id": doc_id,
                "content": child_text,
                "child_index": child_index,
                **base_meta,
            })
    return parents, children
```

入库要求：

1. 先写父块，再写 child 向量；失败时以文档/版本为范围回滚；
2. 同一个文档重建索引时，先写新 `index_version`，验证完成后再切换 active version，避免半新半旧；
3. 删除文档时按 `doc_id + index_version` 同时删除父块与 child vectors；
4. 向量中的 metadata 保留当前已有的 `doc_id/category_id/doc_type/chunk_type`，使现有 filter 能无缝演进。

### 4.5 查询实现：先 Rerank 子块，再回填父块

这是文章最值得严格遵守的部分。**不能先取长父块再 Rerank。**

```python
# ai-service/rag/retriever.py  （拟改造的核心流程）
async def retrieve_parent_child(plan: RetrievalPlan) -> RetrievalOutput:
    # 1) 只从 child collection/child chunk_type 召回较多候选
    candidates = milvus.hybrid_search(
        query=plan.query,
        expr=build_milvus_expr(plan.filter),
        top_k=30,
        output_fields=["chunk_id", "parent_id", "doc_id", "content", "child_index"],
    )

    # 2) 文章中的关键顺序：对子块精排，不把长父块丢给 reranker
    ranked_children = reranker.rerank(
        query=plan.query,
        documents=[item["content"] for item in candidates],
        top_n=8,
    )

    # 3) 同一 parent 多个 child 命中时聚合，而非重复塞给 LLM。
    parent_scores: dict[str, float] = {}
    parent_hits: dict[str, list[dict]] = {}
    for rank, hit in enumerate(ranked_children):
        parent_id = hit["parent_id"]
        # 第一命中全量计分，后续命中衰减；与文章的父级分数合并思想一致。
        weight = 1.0 if not parent_hits.get(parent_id) else 0.5
        parent_scores[parent_id] = parent_scores.get(parent_id, 0.0) + hit["rerank_score"] * weight
        parent_hits.setdefault(parent_id, []).append(hit)

    selected_parent_ids = [
        parent_id for parent_id, _ in sorted(parent_scores.items(), key=lambda x: x[1], reverse=True)[:3]
    ]
    parents = parent_store.get_many(selected_parent_ids)

    # 4) 供给 LLM 的 Context 只含 top 父块中的命中 child 局部窗口，避免整章膨胀。
    contexts = build_local_parent_windows(parents, parent_hits, max_chars=6000)
    return RetrievalOutput(sources=to_sources(contexts), knowledge_context=render_context(contexts))
```

`build_local_parent_windows()` 不能把父块全文无限拼接。建议按命中 child 的 `child_index` 扩展前后各一个 sibling，保留标题路径，并设总 token/字符预算。例如最多 3 个父块、每父块最多 2 个命中窗口、总 Context 不超过 6000~8000 tokens（最终数值根据模型上下文与延迟实测确定）。

### 4.6 查询重写与标准化：同样参考文章，但选择性使用

文章还提出查询扩写/改写、对话 Query 压缩、词典映射、LLM 改写和 NER 标准化。本项目的取舍如下：

| 文章做法 | 本项目是否采用 | 落地方式 |
|---|---|---|
| 词典标准化 | **优先采用** | 同义词、品类、成分、常见别称先规则映射；零额外模型成本 |
| 多轮 Query 压缩 | **优先采用** | 仅有指代、多轮冗余、上下文过长时触发；结合已有 `resolve_reference` |
| LLM 改写 | **条件采用** | 规则未覆盖且 query 不清晰时，输出 Schema 受限的检索计划 |
| Multi-Query | 暂不优先 | 当前已有 hybrid/RRF/rerank；先观察父子分块后的 CP 是否达到目标 |
| HyDE | 暂不采用 | 会增加 embedding/LLM 成本和 P95，且可能把检索带偏 |
| NER + 实体标准化 | 后续增强 | 当词典和 LLM 解析在实体别名上仍有明显漏召回时再做 |

建议的 Query Planner：

```python
class KnowledgeQueryPlan(BaseModel):
    rewritten_query: str
    hard_filters: MetadataFilter = Field(default_factory=MetadataFilter)
    soft_terms: list[str] = []
    use_query_rewrite: bool = False
    allow_fallback: bool = True
```

注意：模型只输出受限业务字段，服务端验证并映射为 Milvus `expr`；模型永远不能直接拼接数据库/Milvus 查询表达式。高置信 `doc_type/product_id/category_id` 才可为 hard filter；场景、肤质、泛化品类等首先作为 soft term，召回不足时只能放宽软条件。

### 4.7 RAG 验收

同一知识测试集、同一运行环境下，记录改造前后：

| 指标 | 基线 | 第一阶段目标 | 说明 |
|---|---:|---:|---|
| Recall@5 | 0.8646 | 不低于 0.84 | 防止提高精度却丢失召回 |
| MRR@5 | 0.8958 | 不低于 0.88 | 防止第一相关块后移 |
| NDCG@5 | 0.8489 | 不低于 0.84 | 检查排序质量 |
| Context Precision | 0.404 | >= 0.60 | 父子分块的主指标 |
| Context Recall | 0.5561 | >= 0.65 | 检查关键信息是否进入 Context |
| Faithfulness | 0.6672 | >= 0.75 | 验证 Context 改善是否减少无依据补充 |
| Knowledge P95 | 18.2s | 不恶化超过 15% | 防止 Context 组织导致延迟失控 |

不承诺提升百分比；只有通过同一评测集和固定配置的实际报告，才能写入简历或 README。

---

## 5. DAG：任务结果契约与受证据约束的聚合

### 5.1 当前风险

当前 DAG 已能在依赖完成后注入 `answer/product_cards/sources`。其中自然语言 `answer` 适合展示，但不适合作为下游任务或最终聚合的事实来源：它可能压缩、遗漏或解释过度。

### 5.2 统一结果结构

新增内部执行契约，逐步替代宽松 dict：

```python
class Evidence(BaseModel):
    kind: Literal["product", "knowledge_source", "web_source"]
    ref_id: str
    facts: dict[str, Any]

class TaskExecutionResult(BaseModel):
    task_id: str
    route: Literal["shopping", "knowledge", "chitchat", "unknown"]
    capability: str | None = None
    status: Literal["success", "clarify", "empty", "failed", "blocked", "timeout"]
    answer: str
    evidence: list[Evidence] = []
    product_cards: list[dict] = []
    sources: list[dict] = []
    hard_constraints_satisfied: bool = True
    trace: dict[str, Any] = {}
```

聚合规则：

1. 依赖任务只消费 `evidence/product_cards/sources`，不把上游 `answer` 当作事实；
2. 推荐任务的卡片必须有真实 `product_id`，详情/对比只能引用该 ID 或服务端检索结果；
3. 知识子任务没有 source 时，聚合器不得将其断言包装成确定结论；
4. 任一子任务失败时仅报告该部分不可用，保留其他成功结果；
5. 聚合答复优先确定性拼装标题、结论、卡片和来源；仅当确实需要跨任务解释时调用受 evidence 约束的 LLM。

### 5.3 验收

- Multi-Agent Tool Correctness：`0.4167 → >= 0.65`；
- 对每一条 subtask 保留 route、capability、status、duration、evidence count；
- 依赖失败时下游状态必须是 `blocked`，不得伪造正常回答；
- 聚合商品卡片去重后仍满足各自 hard filter。

---

## 6. 交易动作：MVP 阶段的明确边界

### 6.1 决策

当前阶段不实现加购物车、创建订单、支付、地址修改等真实交易执行能力。

原因不是技术上不能调用 Java 服务，而是交易是带副作用的动作，需要幂等、防重、库存校验、价格快照、确认态、鉴权与审计；把它混入当前导购 Agent 会放大误调用风险，也偏离校招 MVP 的投入重点。

### 6.2 必须修正的路由行为

当前顶层规则可把“加购/下单”归入 shopping，但 `ShoppingAgent` 挂载的四个高层工具并没有对应交易 capability。MVP 应新增显式的**只读拒绝/引导分支**：

```text
“帮我加购物车” / “直接下单”
  → shopping_action = transaction_unsupported
  → 返回：当前导购助手支持商品推荐、对比、详情咨询；
           请在商品卡片或商品详情页完成加购/下单。
  → 不伪造“已加购/已下单”，不调用交易服务
```

在 Contract 评测中，这类 case 的正确性定义为：

- route 可以为 `shopping`；
- capability 必须为 `transaction_unsupported` 或同等显式状态；
- 不允许产生写操作 Tool Call；
- 最终答案不包含“已为你下单/已加入购物车”等虚假成功表述。

后续若扩展交易能力，应使用“两阶段确认”而不是普通 Agent tool loop：预览操作 → 用户明确确认 → 服务端幂等执行。

---

## 7. 延迟、观测与代码边界

### 7.1 延迟

当前复杂任务和图文任务 P95 接近 30 秒。主要原因是同一请求叠加了 Orchestrator、Router、Shopping tool loop/需求解析、Rerank、Judge、最终生成等多次模型调用。

优化顺序：

1. Capability Dispatcher 命中明确意图时跳过 Shopping Tool-selection loop；
2. 需求解析与 action 决策合并为一次 Structured Output（仅在推荐路径）；
3. Judge 只处理 `top_k * 2` 的候选，且只喂结构化文本字段；
4. Knowledge Query Rewrite 按条件触发，不对每条 query 调 LLM；
5. DAG 同层并发继续保留，子任务超时不阻塞成功分支；
6. 设每条链路独立的 TTFT/P50/P95 预算并进入评测报告。

### 7.2 观测字段

在现有 `run_id/trace_id/tool_calls/sub_results` 基础上统一补充：

```json
{
  "capability": "recommend",
  "dispatch_source": "rule",
  "hard_filters": {"budget_max": 200, "status": 1},
  "soft_preferences": ["轻便"],
  "relaxed_fields": [],
  "final_validation": {"passed": true, "failed_product_ids": []},
  "retrieval": {"candidate_count": 20, "reranked_count": 5},
  "parent_child": {"child_hits": 8, "parent_hits": 3}
}
```

这些字段是调试、Contract Test、DeepEval ToolCorrectness 和简历量化叙述的共同证据；不应把完整 chain-of-thought 返回给前端。

---

## 8. 实施顺序与提交切分

### Commit 1：Shopping Dispatcher 与交易 MVP 边界

- 新增 `ShoppingAction` 和 Dispatcher；
- 将推荐、对比、详情高确定请求直接交给 Capability；
- 新增 `transaction_unsupported`；
- 扩充 golden/contract cases 和 trace 字段。

### Commit 2：商品严格约束 + 图文统一 Filter

- 引入 `ProductFilterPlan`；
- 修改 relaxed recall，只放宽显式可放宽字段；
- 最终商品事实校验；
- 多模态检索接入同一需求与过滤计划。

### Commit 3：Knowledge Query Planner + 词典标准化

- 建立受限 Schema；
- 规则字典优先，LLM 仅兜底；
- 将可信字段映射为现有 `MetadataFilter`；
- 增加 Query rewrite/filter 评测样本。

### Commit 4：父子分块与检索改造

- 增加 parent/child 数据结构、版本化入库与清理；
- child 检索 → child rerank → parent 聚合/局部窗口；
- 回填 `retrieved_contexts`，跑 RAGAS 与检索指标；
- 可回滚到旧索引，直到新索引验证完成。

### Commit 5：DAG 结果契约与聚合校验

- 将子任务结果迁移到内部 Schema；
- 下游按 evidence 消费；
- 聚合约束校验与多 Agent Contract cases。

每个提交只覆盖一个可独立验证的行为变化，避免把索引迁移、Agent 改造和评测数据混在一次提交中而难以回归定位。

---

## 9. 不做的事项

- 不引入第二套向量数据库；
- 不为商品 Judge 额外增加 VL 调用，优先使用数据库结构化字段；
- 不为了提高召回无条件启用 HyDE/Multi-Query；
- 不把用户长期偏好覆盖当前明确需求；
- 不让 LLM 直接生成 Milvus/SQL 表达式；
- MVP 阶段不执行真实加购、下单、支付；
- 不把离线评测结果描述为线上生产指标。

---

## 10. 父子分块索引构建、验证与回退手册

### 10.1 适用边界：仅 KnowledgeAgent

父子递归分块只改造 KnowledgeAgent 的知识库 RAG collection：

```text
KnowledgeAgent
  └─ MILVUS_COLLECTION
       ├─ 旧：my_rag_collection
       └─ 新：knowledge_parent_child_v1
```

它不改造 ShoppingAgent 的商品检索 collection：

```text
ShoppingAgent
  ├─ MILVUS_PRODUCT_COLLECTION    = product_mm_collection
  └─ MILVUS_PRODUCT_V2_COLLECTION = product_mm_v2
```

因此商品文本 Dense/BM25、商品图片向量、图文融合向量、RRF、VL Rerank 与商品卡片逻辑均不需要迁移。商品是完整实体，不应按父/子文本块拆分；预算、库存、SKU、图片均属于商品或 SKU 级事实。

### 10.2 旧、新知识库 collection 对比

| 内容 | 旧 collection | 新父子 collection |
|---|---|---|
| Dense 文本向量 | 有 | 有 |
| Milvus BM25 sparse 向量 | 有 | 有 |
| `doc_id/category_id/product_id/doc_type` | 有 | 有 |
| `chunk_type` | 有，普通 `text/faq/...` | 有，增加 `parent/child` |
| `parent_id/child_index` | 无 | 有 |
| 检索对象 | 普通 chunk | child chunk |
| Rerank 对象 | 普通 chunk | child chunk |
| LLM 最终上下文 | 命中 chunk | child 命中后回填 parent 局部窗口 |

`MetadataFilter` 没有被删除，且在新 collection 中继续有效：`doc_ids`、`category_ids`、`product_id`、`doc_types`、`chunk_types` 均会编译为 Milvus metadata filter。父子模式下 Retriever 自动追加 `chunk_type="child"`，保证 parent 不参与第一阶段召回。

### 10.3 当前递归分块的真实参数

实现位于 `ai-service/rag/parent_child.py`，使用 LangChain `RecursiveCharacterTextSplitter`。它按分隔符优先级递归尝试切分，而不是每隔固定长度硬切：

```text
父块：## 标题 → ### 标题 → 空行 → 换行 → 句号 → 分号 → 逗号 → 字符级兜底
子块：空行 → 换行 → 句号 → 分号 → 逗号 → 字符级兜底
```

```python
PARENT_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=1200,
    chunk_overlap=160,
    separators=["\n## ", "\n### ", "\n\n", "\n", "。", "；", "，", ""],
)
CHILD_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=320,
    chunk_overlap=48,
    separators=["\n\n", "\n", "。", "；", "，", ""],
)
```

注意：当前 `RecursiveCharacterTextSplitter` 使用默认 `len` 计数，因此 `1200/320` 是**字符数**，不是严格 token 数。后续若需按模型 token 预算精确控制，再替换为 token-aware splitter；本次评测先保持参数和索引版本固定。

### 10.4 索引构建前置条件

在 `ai-service/.env` 配置独立 collection，绝不覆盖旧索引：

```env
MILVUS_COLLECTION=knowledge_parent_child_v1
RAG_PARENT_CHILD_ENABLED=true
```

随后重启 AI 服务。新 collection schema 除旧字段外，还必须包含：

```text
parent_id
child_index
chunk_type = parent | child
```

旧 collection 中的向量没有 `parent_id`，不可直接迁移复用；必须使用原始知识文档重新分块、重新 embedding、重新写入。

### 10.5 全量导入脚本

新增脚本：`ai-service/scripts/reindex_knowledge_parent_child.py`。

它复用两类 KnowledgeAgent 数据源，但不会沿用旧的固定分块函数：

| 历史脚本 | 是否复用为数据源 | 说明 |
|---|---|---|
| `ingest_general_knowledge.py` | 是 | 通用/跨商品知识文档 |
| `ingest_knowledge_v2.py` | 是 | 商品 `rag_knowledge` 组成的知识文档 |
| `ingest_knowledge.py` | 否 | 历史 MySQL 写库脚本 |
| `ingest_products_to_milvus.py` | 否 | ShoppingAgent 商品向量脚本，禁止用于本索引 |

新脚本统一调用：

```text
build_chunks_from_text()
  → build_parent_child_records()
  → parent + child 写入 MILVUS_COLLECTION
```

执行顺序：

```powershell
cd ai-service

# A. 不调用 embedding/Milvus，仅检查每篇文档是否能产生 parent + child
python scripts/reindex_knowledge_parent_child.py --dry-run --limit 2

# B. 小样本冒烟：通用知识前 2 篇 + 每个商品类目前 2 件
python scripts/reindex_knowledge_parent_child.py --source all --limit 2 --replace

# C. 冒烟检索正常后，正式全量导入
python scripts/reindex_knowledge_parent_child.py --source all --replace
```

`--limit 2` 仅限制规模：约为 2 篇通用知识 + 4 个类目各 2 篇商品知识；不带 `--limit` 才是全量。`--replace` 表示每篇文档写入前先删除目标 collection 内相同 `doc_id` 的数据，保证可安全重复执行而不产生重复 parent/child chunk。

### 10.6 冒烟导入后的阻断检查

在执行全量导入前，测试 Agent 必须确认：

1. 脚本每篇输出中 `parent > 0` 且 `child > 0`；
2. `GET /api/rag/stats` 返回的新 collection 数量大于 0；
3. 调用 `POST /api/rag/search` 时无 `parent_id`、`child_index`、Milvus schema、Rerank 错误；
4. 搜索返回结构含义正确：

```text
documents[*]         = child 命中与 Rerank 结果（应有 chunk_type=child、parent_id 非空）
knowledge_context    = 按 parent_id 回填后的 parent 局部上下文，供 LLM 使用
```

5. 对同一 `doc_id`，Milvus 中存在 `chunk_type=parent` 和 `chunk_type=child`；每个 child 的 `parent_id` 能定位到 parent。

示例检索请求：

```json
{
  "query": "敏感肌使用视黄醇要注意什么",
  "top_k": 5,
  "search_mode": "hybrid",
  "use_rerank": true
}
```

### 10.7 评测、切换与回退

全量导入后，保持模型、测试集、`top_k`、Rerank 配置和外部服务环境与旧索引评测一致，再比较检索指标与 RAGAS 指标。只有满足 4.7 的底线与目标，才保留新配置。

回退无需删除新 collection：

```env
MILVUS_COLLECTION=my_rag_collection
RAG_PARENT_CHILD_ENABLED=false
```

重启 AI 服务即可回到旧知识库索引。保留 `knowledge_parent_child_v1` 用于问题定位和后续参数调优。
