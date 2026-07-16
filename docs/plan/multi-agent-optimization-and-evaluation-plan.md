# 多 Agent、检索与评测优化计划

> 文档用途：作为后续开发参考，记录当前实现边界、优化目标、技术方案、验收标准和量化指标。
>
> 项目定位：校招/实习项目中的 MVP。优先保证可解释、可复现、低成本和可量化，不为了贴合简历模板而堆叠不必要的组件。

## 1. 总体目标

当前系统已经具备以下能力：

- 基于 LangGraph 的 Supervisor/Orchestrator；
- Shopping、Knowledge、Chitchat 三类 Agent 路由；
- 复杂问题拆解、子任务执行和结果聚合；
- 知识库 Milvus 混合检索、RRF、Rerank；
- 商品文本、结构化字段、图片向量的多路检索与排序；
- Checkpointer、业务记忆和用户偏好记忆；
- run_id、trace_id、AgentRun、AgentStep、ToolCall 等可观测基础。

后续优化目标不是重新设计系统，而是把当前“能够运行”的 MVP 提升为：

```text
可路由 → 可编排 → 可并行 → 可恢复 → 可评测 → 可观测
```

重点解决四类问题：

1. 复杂问题当前是串行执行，`depends_on` 尚未真正参与调度；
2. 图片是全局状态，可能导致复杂问题中的知识子任务误走 ShoppingAgent；
3. 用户偏好已经能够读取，但尚未成为明确的个性化排序特征；
4. 已有运行日志和测试基础，但还没有统一评测集、指标计算和结果报表。

## 2. 当前架构基线

### 2.1 当前 Agent 架构

当前主链路位于 `ai-service/assistant/graph.py`：

```text
用户请求
  ↓
analyze_request
  ├─ simple  → route_intent → Shopping / Knowledge / Chitchat
  └─ complex → prepare_subtask
                 ↓
              route_intent
                 ↓
              执行一个子任务
                 ↓
              collect_subtask
                 ↓
              下一个子任务
                 ↓
              synthesize_final
```

当前复杂问题本质上是：

```text
t1 → t2 → t3 → 固定格式聚合
```

而不是并行 DAG：

```text
t1 ─┐
    ├→ 聚合
t2 ─┘
```

`OrchestratorTask` 已经拥有 `id`、`intent_hint` 和 `depends_on` 字段，这是后续实现 DAG 调度的基础。但目前 `depends_on` 主要被保存和展示，没有完成：

- 拓扑排序；
- 无依赖任务并发执行；
- 依赖结果注入；
- 循环依赖检测；
- 子任务超时和失败隔离。

### 2.2 当前意图识别

主路由目前主要使用 LLM structured output：

```text
LLM → IntentDecision(task_type, confidence, reason)
```

项目中存在规则分类和复合意图检测辅助代码，但尚未形成真正的：

```text
LLM + 向量相似度 + 规则
→ 加权投票
→ 置信度校准
```

当前不建议为了匹配简历话术强行增加向量意图分类。系统意图类别较少，优先采用“高确定性规则 + LLM + 低置信度兜底”的方案。

### 2.3 当前记忆

当前记忆可以按功能划分为三类：

| 记忆类型 | 当前实现 | 作用 |
|---|---|---|
| 对话记忆 | LangGraph Checkpointer；chat-service 另有 Redis/数据库上下文 | 保存消息和多轮上下文 |
| 业务记忆 | Store 中保存商品卡片、关注商品、购物车待确认动作、知识实体 | 支持“刚才推荐的商品”“上一个成分”等指代 |
| 用户画像 | Store/用户资料中保存肤质、性别、预算、偏好标签 | 跨会话保留用户偏好 |

当前不是 ChromaDB 情景记忆，也没有对历史事件做向量检索。因此后续文档和简历中应准确描述为“分层业务记忆”，不应直接宣称“ChromaDB 三层记忆”。

### 2.4 当前评测和监控

当前已有：

- `run_id`、`trace_id`；
- SSE 的 route、tool_call、tool_result、final 事件；
- `AgentRun`、`AgentStep`、`ToolCall` 数据结构和管理接口；
- RAG 和多模态检索的单元测试、验证脚本；
- 多模态检索离线评测脚本和部分 LLM Judge 缓存能力。

当前缺少：

- 统一 Golden Dataset；
- Agent Contract 自动判定；
- DeepEval 评测入口；
- RAGAS 知识问答评测；
- Recall/MRR/NDCG 统一计算和对比报表；
- Prompt、模型、检索配置版本记录；
- 失败样本归因和版本回归对比。

## 3. 指标体系

### 3.1 MRR 是什么

MRR（Mean Reciprocal Rank，平均倒数排名）用于衡量“第一个相关结果出现得有多靠前”。

对于一个查询，如果第一个相关结果排在第 `rank` 位，则：

```text
RR = 1 / rank
```

如果 Top-K 内没有相关结果，则：

```text
RR = 0
```

对 N 个查询取平均：

```text
MRR@K = (1 / N) × Σ RR@K
```

例子：

| 查询 | 第一个相关结果位置 | RR |
|---|---:|---:|
| q1 | 1 | 1.00 |
| q2 | 2 | 0.50 |
| q3 | 5 | 0.20 |
| q4 | Top-5 未命中 | 0 |

```text
MRR@5 = (1.00 + 0.50 + 0.20 + 0) / 4 = 0.425
```

### 3.2 MRR、Recall、NDCG 的区别

| 指标 | 主要关注点 | 适用问题 |
|---|---|---|
| Recall@K | 相关结果是否进入 Top-K | 召回阶段是否漏掉正确答案 |
| MRR@K | 第一个相关结果是否靠前 | 用户是否能快速看到一个正确结果 |
| NDCG@K | 多个结果的相关等级和排序 | Top-K 整体排序质量 |

MRR 只重点关注第一个相关结果。如果 Top-5 中有很多相关商品，但第一个相关商品排在第 3 位，MRR 只能反映第一个相关商品的位置，无法完整体现其余商品的质量。因此商品推荐不能只看 MRR，应与 Recall@5、NDCG@5 一起报告。

### 3.3 MRR 在本项目中的适用范围

#### 知识库 RAG

适合使用：

- `Recall@5`：正确知识片段是否被召回；
- `MRR@5`：第一个正确知识片段是否靠前；
- `NDCG@5`：多个知识片段的整体排序质量；
- `Faithfulness`：最终回答是否被检索上下文支持；
- `P95 Latency`：检索和生成延迟。

注意：知识库存在同一文档多个相邻 Chunk 的情况。评测时应同时提供：

- Chunk-level MRR；
- Document-level MRR，避免同一文档重复 Chunk 造成虚高。

#### 商品文本/图片/图文检索

适合使用：

- `Recall@5`：目标品类或相关商品是否进入 Top-5；
- `MRR@5`：第一个相关商品的位置；
- `NDCG@5`：多个商品的相关等级排序；
- `Category Precision@5`：Top-5 中正确品类商品的比例；
- `P95 Latency`：图片上传到商品卡片返回的延迟。

对于图片检索，相关性标签建议优先来自数据库结构化字段和人工/离线构造的查询标签，不把视觉 LLM Judge 放到线上链路中。数据库中的 `product_id`、category、sub_category、title、tags 和 image_url 应保持一致，由结构化字段完成明显异类过滤。

#### Agent 总体执行

MRR 不适合直接评估 Agent 总体质量。Agent 更适合使用：

- `Route Accuracy`：是否进入正确 Agent；
- `Tool Contract Pass Rate`：工具名称、参数和调用顺序是否正确；
- `Task Success Rate / Pass@1`：一次执行是否满足完整任务契约；
- `Pass@K`：同一任务独立执行 K 次，至少成功一次；
- `P95 E2E Latency`：端到端耗时；
- `TTFT`：首个可见 SSE token 延迟；
- `Subtask Coverage`：复杂问题中子问题是否全部覆盖。

当前模型温度较低、没有多次采样和 retry 机制时，主指标应报告 `Pass@1`，不要只报告 Pass@3。

### 3.4 推荐的 MVP 指标集

| 模块 | 主指标 | 辅助指标 |
|---|---|---|
| Knowledge RAG | Recall@5、NDCG@5、MRR@5 | Faithfulness、P95 Latency |
| 商品文本/图片检索 | Recall@5、NDCG@5、MRR@5 | Category Precision@5、P95 Latency |
| Agent 路由 | Route Accuracy | 低置信度率、误路由率 |
| Agent 工具调用 | Tool Contract Pass Rate | 工具失败率、参数错误率 |
| 多 Agent 任务 | Task Success Rate/Pass@1 | Subtask Coverage、P95 E2E Latency、TTFT |
| 个性化推荐 | Preference Compliance@K | 加偏好前后 NDCG@5 差值 |

在没有真实线上流量时，不虚构 CTR、加购率、转化率。可以使用固定离线 Case 评估个性化偏好是否被满足。

### 3.5 RAG 分块策略优化

#### 当前基线

当前知识库存在两类分块链路：

1. 通用文档上传链路：`ai-service/rag/document_pipeline.py` 使用 `CharacterTextSplitter`，默认 `chunk_size=800`、`chunk_overlap=120`，主要按空行分段；
2. 商品知识 v2 链路：已经按照业务结构切分：营销描述一个 Chunk、FAQ 一问一答一个 Chunk、用户评价每三条一个 Chunk。

因此，当前商品知识的分块已经有一定的文档结构意识，但通用知识文档仍然偏基础，存在以下风险：

- 标题和正文可能被拆开；
- 一个问答可能被拆成两个 Chunk；
- 列表、表格、步骤说明可能在中间断开；
- 单个段落过长时，单纯按空行无法进一步稳定切分；
- 相邻 Chunk 之间的语义依赖只能依赖固定 overlap；
- 同一文档的多个相邻 Chunk 可能重复进入 Top-K，造成 MRR 或 Recall 的虚高。

#### 几种策略的定位

| 策略 | 核心做法 | 优点 | 缺点 | 当前适用性 |
|---|---|---|---|---|
| 固定/字符分块 | 按字符数和 overlap 切分 | 成本低、实现简单 | 容易破坏语义边界 | 当前基线 |
| 递归分块 | 按段落、换行、句号等分隔符逐级降级 | 通用、低成本、比固定切分稳定 | 仍不了解文档业务结构 | 建议作为通用兜底 |
| 文档结构分块 | 按标题、章节、FAQ、表格、列表、字段切分 | 语义完整、可解释、无需额外模型 | 需要针对文档格式编写解析器 | 当前首选 |
| 父子分块 | 小 Child 用于检索，大 Parent 用于上下文 | 提高召回精度，同时保留完整上下文 | 需要新增 parent/child 关系和回填逻辑 | 第二阶段推荐 |
| 语义分块 | 根据句子 Embedding 相邻相似度寻找边界 | 对长篇自然语言语义边界更敏感 | 需要额外 Embedding、阈值调参和离线成本 | 后续实验项 |

这里需要区分两个概念：

- “递归分块”主要是切分算法；
- “语义分块”主要是根据内容相似度决定边界；
- “文档结构分块”主要是利用标题、FAQ、表格等文档结构；
- “父子分块”主要是检索粒度和上下文粒度分离。

它们不是完全互斥的方案，可以组合使用。

#### 当前项目推荐方案

当前最推荐的组合是：

```text
文档类型识别
  ↓
结构感知切分
  ├─ Markdown 标题/章节 → 保留标题路径
  ├─ FAQ → 问题 + 答案保持完整
  ├─ 表格/列表/步骤 → 尽量保持整体
  ├─ 商品营销/评价 → 使用现有业务结构切分
  └─ 普通长段落 → 递归分块兜底
  ↓
必要时建立 Parent-Child 关系
  ↓
Child 检索，Parent 回填上下文
```

推荐顺序如下：

1. 先将通用 `CharacterTextSplitter` 升级为递归分块，并支持中文句号、问号、感叹号、分号等分隔符；
2. 再增加 Markdown 标题、FAQ、列表和表格的结构感知切分；
3. 对需要跨段回答的长文档增加父子分块；
4. 最后再评估语义分块是否有增量收益。

对于当前电商知识库，第一选择不是纯语义分块，而是“文档结构分块 + 递归兜底”。原因是商品 FAQ、营销描述和用户评价本身已经有明确结构，结构化切分比调用 Embedding 判断边界更便宜、更稳定，也更容易在面试中解释。

#### 父子分块设计

父子分块可以采用以下数据结构：

```json
{
  "parent_id": "doc_12_section_03",
  "chunk_level": "child",
  "chunk_index": 2,
  "content": "烟酰胺适合哪些肤质？"
}
```

```json
{
  "parent_id": "doc_12_section_03",
  "chunk_level": "parent",
  "content": "## 烟酰胺适用肤质\n烟酰胺通常适合多数肤质……"
}
```

建议流程：

```text
Child 300～500 字符/或一个完整 FAQ 问答
  ↓ embedding + BM25 检索
命中 Child
  ↓ parent_id 回填父级章节
使用 Parent 作为 LLM 上下文
```

父子分块不是无条件更好。它更适合：

- 一个问题需要多个相邻段落才能回答；
- 文档标题和正文需要一起提供；
- Child 太短导致检索精准但生成上下文不足；
- 希望降低重复 Chunk 对 Top-K 的影响。

如果当前知识库主要是“一问一答”的 FAQ，直接保留完整 FAQ Chunk 可能比父子分块更简单、更好。

#### 语义分块的使用边界

语义分块可以按句子生成 Embedding，计算相邻句子的相似度，在相似度明显下降处切分。它适合：

- 没有稳定标题结构的长篇文章；
- 段落长度差异很大；
- 一个自然段内部包含多个主题；
- 固定分块和结构分块在多跳问题上效果不理想。

但它不建议作为第一阶段方案：

- 每次重建索引需要更多 Embedding 调用；
- 相似度阈值需要调参；
- 结果受 Embedding 模型版本影响；
- 对 FAQ、表格、字段型商品知识不一定优于结构化切分；
- 更难定位“为什么这里被切开”。

#### 分块优化的评测方法

所有策略必须使用相同的数据集、Embedding、Milvus 配置、Rerank 模型、Query 和生成 Prompt，单独比较分块策略，避免把多个变量同时修改。

建议至少建立以下版本：

```text
V0：当前 CharacterTextSplitter 800/120
V1：递归分块 500～800 + overlap
V2：文档结构分块 + 递归兜底
V3：V2 + Parent-Child
V4：V2 + Semantic Chunking（实验项）
```

主要评测指标：

| 维度 | 指标 | 说明 |
|---|---|---|
| 召回覆盖 | Recall@5 | 相关 Chunk/Document 是否进入 Top-5 |
| 首个命中 | MRR@5 | 第一个相关 Chunk/Document 是否靠前 |
| 排序质量 | NDCG@5 | 多个相关结果的等级排序 |
| 上下文质量 | RAGAS Context Recall | 回答所需信息是否被检索上下文覆盖 |
| 上下文纯度 | RAGAS Context Precision | 检索上下文中无关内容是否减少 |
| 最终答案 | Faithfulness、Answer Relevancy | 固定生成链路下，回答是否有依据且切题 |
| 重复程度 | Duplicate/Adjacent Hit Rate | Top-K 是否被同一文档相邻 Chunk 占满 |
| 切分完整性 | Boundary Break Rate | FAQ、标题、步骤、表格是否被错误截断 |
| 成本性能 | Chunk Count、Index Size、Embedding Cost | 分块数量和重建索引成本 |
| 在线性能 | P50/P95 Retrieval Latency | 检索耗时是否可接受 |

MRR 和 NDCG 建议同时计算 Chunk-level 与 Document-level：

- Chunk-level：判断具体知识片段能否命中；
- Document-level：同一文档多个相邻 Chunk 只算一个文档，避免重复命中造成指标虚高。

#### 分块优化的专项验收指标

建议先使用离线 30～50 条 Query，其中至少包含：

- 单 Chunk 可回答的问题；
- 需要相邻两个 Chunk 的问题；
- FAQ 问答；
- 标题/章节依赖问题；
- 表格和列表问题；
- 同一文档多个主题的问题；
- 无答案问题。

每个 Query 标注：

```json
{
  "query": "烟酰胺和视黄醇可以一起使用吗？",
  "relevant_doc_ids": [12],
  "relevant_chunk_ids": ["doc_12_chunk_03"],
  "difficulty": "single_chunk",
  "answerable": true
}
```

父子分块还需要额外记录：

- 命中的 Child ID；
- 回填的 Parent ID；
- Parent 是否包含正确答案；
- Parent 上下文长度；
- 回填后是否引入无关内容。

最终不要只看某一个指标。推荐使用以下决策规则：

```text
优先选择：
1. Document-level Recall@5 不下降；
2. MRR@5 或 NDCG@5 提升；
3. Context Precision 不下降；
4. Faithfulness 不下降；
5. P95 延迟和索引成本在预算内。
```

如果 V2 的 Recall@5、MRR@5、NDCG@5 和 Context Precision 都优于 V0，且索引成本可接受，就可以将 V2 作为默认策略。只有当 V3 在多 Chunk 问题上的 Context Recall 或 Faithfulness 有明显增量时，才值得引入 Parent-Child。

#### 已有 Chunk 和向量索引如何迁移

分块发生在“文档入库阶段”，不是用户查询时动态发生。修改分块策略后，原来的 Chunk 内容、数量、边界和 Embedding 都可能发生变化，因此不能简单地在旧索引后面持续追加新 Chunk，否则会出现：

- 同一份知识同时存在 V0 和 V1 两套切片；
- 旧 Chunk 和新 Chunk 重复召回；
- MRR/NDCG 受到旧数据污染；
- 相邻 Chunk 的数量增加，Top-K 被重复内容占满；
- 无法判断线上结果来自哪一种分块策略。

推荐使用“分块策略版本化 + 新集合重建 + 灰度切换”的方式。

```text
当前线上：knowledge_chunks_v0
        ↓
使用新策略重新解析全部文档
        ↓
写入：knowledge_chunks_v1
        ↓
离线计算 Recall/MRR/NDCG/RAGAS
        ↓
V1 达标后切换读取配置
        ↓
观察一段时间后删除 V0
```

建议在 Chunk metadata 中增加：

```json
{
  "chunk_strategy": "structure_recursive",
  "chunk_version": "v1",
  "parent_id": "doc_12_section_03",
  "chunk_level": "child"
}
```

对于当前 MVP，推荐两种实现方式：

1. 最稳妥：创建新的 Milvus Collection，例如 `knowledge_chunks_v1`，评测通过后修改 `MILVUS_COLLECTION` 或使用 Collection Alias 切换；
2. 数据量较小时：删除旧 `doc_id` 的向量后重新切分、重新 Embedding、重新 upsert，但必须保留数据集和配置版本，方便回滚。

不建议把 V0 和 V1 无标记地混在同一个 Collection 中。即使放在同一个 Collection，也必须增加 `chunk_version` 并在查询时只过滤当前版本。

#### 文档增量更新策略

当只是新增文档时，直接使用当前生效的 Chunk 策略入库即可；当修改了某一篇已有文档时，只需要：

```text
删除该 doc_id 的旧 Chunk
  ↓
重新解析该文档
  ↓
重新生成 Embedding
  ↓
写入当前策略版本的 Chunk
```

当全局分块策略发生变化时，不能只对新文档使用新策略、旧文档继续使用旧策略后就直接比较整体指标。应优先完整重建一套 V1，完成离线对比后再统一切换。这样才能把“分块策略变化”与“文档分布变化”区分开。

#### 是否需要动态增加 Chunk

可以增加新的粒度，但应该是“离线构建多粒度索引”，而不是查询时临时切分：

```text
Child Chunk：用于精确检索
Parent Chunk：用于上下文补全
```

这属于 Parent-Child 方案，需要通过 `parent_id` 建立关系，并在召回 Child 后回填 Parent。它不是把旧 Chunk 随意追加到原索引中。

对于当前项目，推荐的迁移顺序是：

```text
V0：现有 CharacterTextSplitter
V1：递归分块 + 版本化重建
V2：结构感知分块 + 递归兜底 + 版本化重建
V3：V2 + Parent-Child 多粒度索引
```

## 4. 分阶段开发计划

## Phase 0：统一数据契约和可观测字段

### 目标

让每次 Agent 执行、每个子任务和每次检索都能被稳定记录和复现。

### 主要工作

1. 为子任务增加字段：

```json
{
  "id": "t1",
  "question": "根据图片推荐方便面",
  "intent_hint": "shopping",
  "depends_on": [],
  "use_image": true,
  "status": "pending"
}
```

2. 为 Agent Run 记录：

- agent_version；
- prompt_version；
- model_name；
- route；
- confidence；
- start_time、end_time、duration_ms；
- error_code；
- fallback_used。

3. 为检索记录：

- query_id；
- retrieval_mode；
- candidate_count；
- top_k；
- 是否使用 RRF；
- 是否使用 rerank；
- 各阶段耗时；
- 最终 product_id/source_id 列表。

### 验收标准

- 一个请求可以通过 `trace_id` 关联到 Agent、子任务、工具和检索记录；
- 同一个 Case 可以区分不同模型、Prompt 和检索配置；
- 失败请求能够明确归因到 route、tool、retrieval 或 generation。

## Phase 1：修复任务级路由并实现 DAG 编排

### 目标

实现无依赖子任务并发、有依赖任务等待前置结果，并解决图片污染所有子任务的问题。

### 主要工作

1. 图片从全局隐式条件改为任务级 `use_image`；
2. `intent_hint=knowledge` 时，不得因为全局图片自动路由到 ShoppingAgent；
3. 对任务依赖做校验：

- 检查重复 ID；
- 检查非法依赖；
- 检查循环依赖；
- 限制最多任务数；
- 限制最大执行深度。

4. 使用拓扑分层：

```text
Level 0：t1、t2，无依赖，可 asyncio.gather 并发
Level 1：t3，依赖 t1、t2，等待前置结果
Level 2：t4，依赖 t3
```

5. 依赖任务接收结构化前置结果，而不是只接收自然语言拼接；
6. 单个子任务超时或失败时，其他独立任务继续执行；
7. 最终聚合保留确定性格式。只有当子任务之间存在冲突或需要统一解释时，才选择性调用一次最终 LLM。

### 验收标准

- 无依赖任务能够并行执行；
- 依赖任务不会早于前置任务执行；
- 循环依赖被拒绝并返回稳定错误；
- 图片+知识复合问题能够分别进入 ShoppingAgent 和 KnowledgeAgent；
- 一个子任务失败不会导致无关子任务全部丢失；
- 多问题 Case 的 Subtask Coverage 达到预设阈值。

## Phase 2：增强低成本路由可靠性

### 当前实现状态（2026-07-16）

已完成主链路实现：

- 高确定性规则覆盖图片检索、明确商品操作、知识问法、问候和对话元问题；
- 明确单意图可跳过 Orchestrator LLM，减少不必要的规划调用；
- 规则无法判断时调用一次 Structured LLM Router；
- LLM 低置信度、调用异常或空结果进入 `unknown` 澄清兜底；
- DAG 子任务复用 `intent_hint`，高确定性冲突规则可覆盖错误 hint；
- API、SSE 和 `sub_results` 记录 rule、LLM、最终 route、confidence、source 和 fallback；
- 新增路由 Golden Dataset、指标计算和 rules/hybrid 离线评测入口。

测试与评测方式见 `docs/plan/phase2-router-test-guide.md`。

### 实测结果

已使用 22 条路由 Golden Case 完成混合路由评测：

| 指标 | 结果 | 说明 |
|---|---:|---|
| Route Accuracy | 95.45% | 22 条 Case 中 21 条最终路由正确 |
| Misroute Rate | 0% | 没有请求被静默送入错误 Agent |
| Rule Direct Rate | 81.82% | 18/22 条 Case 由规则直接完成路由 |

结果表明，当前规则优先策略已经覆盖绝大多数明确请求；剩余不确定请求交给 LLM 或安全澄清兜底，未产生业务 Agent 误路由。以上数据属于离线 Golden Dataset 结果，不等同于线上真实流量指标。

### 推荐方案

```text
高确定性规则
  ↓ 命中则直接路由
否则调用 LLM Structured Router
  ↓
低置信度 → fallback / 澄清问题
```

规则适合处理：

- 图片商品检索；
- 加入购物车、购买、价格、库存；
- 成分、功效、用法、禁忌；
- 明显闲聊和元问题。

LLM 负责：

- 指代消解；
- 上下文相关路由；
- 混合表达；
- 规则无法判断的请求。

向量意图分类暂列为可选项。只有当路由 Case 数量扩大、规则和 LLM 仍然存在明显误判时，再引入语义原型向量分类。

### 验收标准

- 每个路由 Case 有期望 route；
- 规则、LLM 和最终 route 都被记录；
- 低置信度请求不会静默进入错误 Agent；
- 使用 Route Accuracy、误路由率和低置信度率进行对比。

## Phase 3：用户偏好参与个性化推荐

### 偏好数据结构

偏好不应被限制为固定字段，可使用动态事实结构：

```json
{
  "aspect": "texture",
  "value": "清爽",
  "polarity": "like",
  "source": "explicit_user_statement",
  "confidence": 0.95,
  "updated_at": "2026-07-16T12:00:00+08:00",
  "expires_at": null
}
```

必须保留：

- 来源；
- 置信度；
- 更新时间；
- 过期时间或衰减策略；
- 喜欢/不喜欢的 polarity。

### 个性化排序流程

```text
当前请求解析
  ↓
基础文本/结构化/图片召回
  ↓
数据库结构化字段硬过滤
  ↓
基础相关性排序
  ↓
偏好特征软重排
  ↓
必要时仅对 Top-N 候选调用 LLM
```

优先级建议：

```text
当前请求明确条件
> 本轮明确偏好
> 长期明确偏好
> 隐式行为偏好
> 热度和销量
```

LLM 的角色建议是“偏好解析器”，而不是每次全量商品 LLM Judge：

- 解析动态偏好；
- 处理冲突偏好；
- 对 Top-N 分数接近的商品进行有限重排；
- 生成推荐理由。

### 偏好的其他用途

偏好还可以用于：

- 生成当前会话推荐问题；
- 生成推荐 Chips；
- 补全购物需求的澄清问题；
- 做弱 Query 扩展；
- 解释“为什么推荐这个商品”。

### 验收指标

- `Preference Compliance@5`：Top-5 满足用户明确偏好的商品比例；
- 加偏好前后 `NDCG@5` 的变化；
- 偏好冲突时是否优先遵守本轮明确条件；
- 没有真实流量时不报告 CTR 或转化率。

## Phase 4：建立低成本 Agent 评测闭环

### 4.1 Golden Dataset

建议先准备 30～50 个 Case，按场景分层：

- 10 个单轮 Shopping；
- 10 个 Knowledge RAG；
- 10 个图文商品检索；
- 5 个多问题编排；
- 5 个指代、偏好和购物车场景。

每个 Case 至少包含：

```json
{
  "id": "complex_001",
  "query": "推荐方便面，并说明如何保存",
  "expected_routes": ["shopping", "knowledge"],
  "required_tools": ["search_multimodal_v1", "search_knowledge"],
  "required_product_category": ["方便面"],
  "must_answer": ["商品推荐", "保存方法"],
  "max_latency_ms": 10000
}
```

### 4.2 程序化 Contract Test

用 pytest 验证硬约束：

- route 是否正确；
- 是否调用了要求的工具；
- 工具参数是否合法；
- 商品 ID 是否来自数据库；
- 商品类别是否符合允许范围；
- 是否存在最终答案；
- 子问题是否全部覆盖；
- 错误状态是否正确；
- SSE 是否包含 final/done。

硬约束优先于 LLM Judge，因为它成本低、稳定且可复现。

### 4.3 DeepEval

DeepEval 只评估自然语言质量，不替代程序化契约测试。适合评估：

- 多问题最终回答是否覆盖所有子问题；
- Knowledge 回答是否与 sources 一致；
- 商品推荐理由是否与 product_cards 一致；
- 是否出现商品字段幻觉；
- 失败时是否给出清晰说明。

建议先用 20～30 个核心 Case 低频运行，不把每次线上请求都发送给 Judge。

### 4.4 RAGAS

RAGAS 只用于 Knowledge RAG 专项：

- Faithfulness；
- Answer Relevancy；
- Context Precision；
- Context Recall。

RAGAS 不负责评估商品排序、工具调用和多 Agent DAG 调度。

### 4.5 Task Success 和 Pass@K

当前 MVP 主指标使用：

```text
Task Success Rate ≈ Pass@1
```

一次执行满足完整 Contract 即成功。推荐定义为：

```text
Task Success
= 硬 Contract 通过
  + 最终回答 DeepEval Rubric 达标
```

未来引入 retry、多次采样或多计划后，再增加：

```text
Pass@3 = 同一任务独立执行 3 次，至少成功 1 次的比例
```

但必须同时保留 Pass@1，避免只展示重试后的成功率。

## 5. 评测脚本和报表设计

建议新增或逐步完善：

```text
ai-service/
  evals/
    datasets/
      agent_cases.jsonl
      knowledge_cases.jsonl
      product_cases.jsonl
    metrics.py
    run_agent_eval.py
    run_retrieval_eval.py
    reports/
```

检索评测脚本需要统一输出：

```json
{
  "variant": "hybrid_rrf_rerank",
  "recall@5": 0.0,
  "mrr@5": 0.0,
  "ndcg@5": 0.0,
  "avg_latency_ms": 0.0,
  "p95_latency_ms": 0.0
}
```

不要在没有实际运行结果时填写示例数值。报告应至少支持基线对比：

```text
Knowledge:
  dense
  hybrid
  hybrid + RRF
  hybrid + RRF + rerank

Product:
  pure_text
  structured_text
  text + image
  three_path + RRF
  three_path + RRF + rerank
```

每次报告同时记录：

- 数据集版本；
- 模型版本；
- Prompt 版本；
- 检索配置；
- 候选数和 Top-K；
- 指标结果；
- 延迟结果；
- 失败样本。

## 6. 监控闭环

第一阶段只做观测和降级，不做自动修改 Agent 权重：

```text
请求
  ↓
trace/run 记录
  ↓
Agent、工具、检索耗时和结果记录
  ↓
失败分类
  ├─ 路由失败
  ├─ 工具失败
  ├─ 检索无命中
  ├─ 结构化过滤为空
  └─ 生成失败
  ↓
离线评测集回归
```

建议监控：

- Task Success Rate；
- Route Accuracy；
- Tool Failure Rate；
- P50/P95 E2E Latency；
- TTFT；
- RAG Recall/MRR/NDCG；
- 商品 Recall/MRR/NDCG；
- 多模态图片不可达率；
- 空结果率；
- 部分成功率。

只有在有足够真实流量和稳定评测数据之后，才考虑按 Agent 版本做自动熔断或降级。

## 7. 推荐开发优先级

### P0：必须优先完成

1. 修复图片对复杂子任务的全局路由污染；
2. 统一子任务和 Agent 结果契约；
3. 增加路由、工具、最终结果的 Contract Test；
4. 建立 Golden Dataset 和 Recall/MRR/NDCG 计算基础。

### P1：最有技术含量、最值得写进简历

1. 实现真正的 DAG 调度；
2. 无依赖子任务并发执行；
3. 依赖结果注入和失败隔离；
4. 比较串行与并行的 P95 延迟和 Task Success Rate。

### P1.5：RAG 分块策略优化

1. 保留当前策略作为 V0 基线；
2. 实现递归分块，支持中文句子边界和长度兜底；
3. 实现 Markdown 标题、FAQ、列表、表格和商品知识结构感知切分；
4. 使用相同 Embedding、RRF、Rerank 和 Query，对比 V0～V2 的 Recall@5、MRR@5、NDCG@5、RAGAS Context Precision/Recall 和 P95 延迟；
5. 只有在多 Chunk 问题仍然明显时，再实现 Parent-Child；
6. 语义分块作为低优先级实验，不作为默认线上方案。

### P2：完善个性化能力

1. 动态偏好事实和置信度；
2. 结构化字段硬过滤；
3. 规则/特征个性化重排；
4. 根据偏好生成澄清问题和推荐 Chips。

### P3：评测与展示增强

1. 接入 DeepEval 评估自然语言质量；
2. 接入 RAGAS 评估知识 RAG；
3. 增加 Agent 运行报表；
4. 增加版本对比和失败样本详情。

## 8. 后续简历表述

当前实现可以表述为：

> 基于 LangGraph 构建 Supervisor-Orchestrator，支持购物推荐、知识问答和闲聊 Agent 的结构化路由；针对复杂问题实现任务拆解、子任务执行和结果聚合；知识库侧采用 Milvus 混合检索、RRF 与 Rerank，商品推荐侧融合文本、结构化字段和图像向量检索。

完成 Phase 1、Phase 3、Phase 4 后，可以升级为：

> 基于 LangGraph 实现多 Agent DAG 编排，支持无依赖子任务并行、依赖结果注入和失败隔离；通过 Contract Test、DeepEval 和 RAGAS 建立 Agent/RAG 评测闭环，使用 Recall@K、MRR@K、NDCG@K、Task Success Rate、Pass@1、TTFT 和 P95 Latency 量化评估检索质量、任务成功率和系统性能。

不应在尚未实现或没有实测数据时直接宣称：

- 三路融合意图识别；
- 多 Agent 并行调用；
- ChromaDB 情景记忆；
- LLM-as-Judge 自动降权；
- 工业级自动评测闭环。
