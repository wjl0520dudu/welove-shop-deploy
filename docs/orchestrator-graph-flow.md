# AI-Service 主图流程图 + 架构图（Orchestrator 版）

> 本文档配套 `commit 12d8350`（主图接入 Orchestrator 多问题拆解），描述当前 `AssistantGraph`
> 的**分层架构、图拓扑、State 流转、SSE 事件时序、四重反空返回防线**。
>
> 代码位置：[ai-service/assistant/graph.py](../ai-service/assistant/graph.py)
> 相关 Schema：[ai-service/agents/schemas.py](../ai-service/agents/schemas.py)
> Prompt：[ai-service/agents/prompts.py](../ai-service/agents/prompts.py) `ORCHESTRATOR_PROMPT`
> 状态：[ai-service/agents/state.py](../ai-service/agents/state.py) `AssistantState`
>
> 📌 **图分两类**：架构图（§0）描述模块分层与依赖，流程图（§1 起）描述运行时数据流。

---

## 零、系统架构图（分层视角）

### 0.1 整体分层

```mermaid
flowchart TB
    subgraph 客户端["🌐 客户端"]
        FE[Web H5 / 小程序]
    end

    subgraph 网关["🔒 网关 / Java 层"]
        GW[welove-api 网关<br/>JWT 鉴权 + 请求转发]
    end

    subgraph AI服务["🧠 ai-service（本项目）"]
        direction TB

        subgraph API层["📡 API 层"]
            API[api/assistant_routes.py<br/>/run + /stream SSE]
            SCHEMA[api/schemas.py<br/>AIResponse 契约]
            ADAPT[api/response_adapter.py<br/>normalize / SSE 事件]
        end

        subgraph 编排层["🎯 编排层 (Orchestrator)"]
            GRAPH[assistant/graph.py<br/>AssistantGraph<br/>LangGraph StateGraph]
            NODES[assistant/nodes.py<br/>shopping/knowledge/<br/>chitchat/unknown/format]
            STATE[agents/state.py<br/>AssistantState TypedDict]
        end

        subgraph 智能体层["🤖 智能体层"]
            SHOP[shopping/agent.py<br/>ShoppingAgent + 4 工具]
            KNOW[knowledge/agent.py<br/>KnowledgeAgent + RAG]
            CHIT[create_agent 闲聊 Agent]
        end

        subgraph 基础设施["⚙️ 基础设施"]
            LLM[core/llm.py<br/>init_chat_model]
            PROMPT[agents/prompts.py<br/>ROUTER + ORCHESTRATOR<br/>+ SHOPPING + KNOWLEDGE]
            SCHEMAS[agents/schemas.py<br/>IntentDecision<br/>OrchestratorDecision]
            RUNTIME[agents/runtime.py<br/>checkpointer + store + MCP]
            MEMORY[agents/memory.py<br/>business_memory 读写]
        end

        subgraph 数据层["💾 数据层"]
            PG[("PostgreSQL<br/>welove_shop_search<br/>checkpointer / store<br/>users.profile / pgvector")]
            MILVUS[(Milvus 2.5<br/>knowledge_collection<br/>product_mm_collection)]
            OSS[(阿里云 OSS<br/>知识库文件)]
        end

        subgraph 外部AI依赖["☁️ 外部 AI 依赖"]
            QWEN[通义千问<br/>qwen-plus / -turbo<br/>text-embedding-v4]
            RERANK[DashScope Rerank<br/>qwen3-rerank]
            BOCHA[博查 Web Search<br/>MCP + HTTP 兜底]
        end
    end

    subgraph Java业务["🏢 Java 业务层"]
        JAVA_API[welove-shop-api<br/>商品/订单/用户/购物车]
        PG_BIZ[(PostgreSQL<br/>welove_shop_db<br/>业务主库)]
    end

    FE -->|HTTPS| GW
    GW -->|POST /api/assistant/*| API
    API --> ADAPT --> SCHEMA
    API --> GRAPH

    GRAPH --> NODES
    GRAPH --> STATE
    GRAPH --> SCHEMAS
    GRAPH --> PROMPT
    GRAPH --> RUNTIME
    GRAPH --> MEMORY

    NODES --> SHOP
    NODES --> KNOW
    NODES --> CHIT

    SHOP --> LLM
    KNOW --> LLM
    CHIT --> LLM
    GRAPH --> LLM

    SHOP -->|HTTP + JWT| JAVA_API
    JAVA_API --> PG_BIZ

    KNOW --> MILVUS
    KNOW --> BOCHA
    KNOW --> RERANK

    RUNTIME --> PG
    MEMORY --> PG
    RUNTIME --> OSS

    LLM --> QWEN
    KNOW --> QWEN

    classDef api fill:#dbeafe,stroke:#2563eb
    classDef orch fill:#fef3c7,stroke:#d97706,stroke-width:2px
    classDef agent fill:#dcfce7,stroke:#16a34a
    classDef infra fill:#f3e8ff,stroke:#9333ea
    classDef data fill:#fee2e2,stroke:#dc2626
    classDef ext fill:#fce7f3,stroke:#db2777

    class API,SCHEMA,ADAPT api
    class GRAPH,NODES,STATE orch
    class SHOP,KNOW,CHIT agent
    class LLM,PROMPT,SCHEMAS,RUNTIME,MEMORY infra
    class PG,MILVUS,OSS,PG_BIZ data
    class QWEN,RERANK,BOCHA,JAVA_API ext
```

**分层职责**：

| 层 | 主要模块 | 职责 |
| --- | --- | --- |
| 📡 API 层 | `assistant_routes.py` / `schemas.py` / `response_adapter.py` | FastAPI 路由、请求/响应契约、SSE 事件格式化 |
| 🎯 编排层 | `assistant/graph.py` / `assistant/nodes.py` / `agents/state.py` | LangGraph 图定义、节点实现、共享 State |
| 🤖 智能体层 | `shopping/agent.py` / `knowledge/agent.py` | 具体 Agent 实现，含工具调用 & RAG |
| ⚙️ 基础设施 | `core/llm.py` / `agents/prompts.py` / `agents/runtime.py` / `agents/memory.py` | LLM 客户端、Prompt 模板、跨轮记忆 |
| 💾 数据层 | PG (`welove_shop_search`) / Milvus / OSS | ai-service 侧：短期记忆 (checkpointer)、长期记忆 (store)、用户画像 (users.profile)、向量检索、文件存储 |
| ☁️ 外部 AI | 通义千问 / DashScope Rerank / 博查 | LLM、Embedding、Rerank、Web 搜索兜底 |

---

### 0.2 Orchestrator 模块内部架构

```mermaid
flowchart LR
    subgraph 入口["🚪 入口"]
        RUN["AssistantGraph.run() /<br/>AssistantGraph.astream()"]
    end

    subgraph 图定义["📐 图定义（LangGraph）"]
        BUILD["_build()<br/>StateGraph 装配"]
        COMPILE["compile()<br/>+ checkpointer<br/>+ store"]
    end

    subgraph Planner["🟡 Planner 组件"]
        ANALYZE["_analyze_request<br/>意图 + 复杂度"]
        NORMALIZE["_normalize_orchestrator_decision<br/>结果格式化"]
        FALLBACK["_fallback_orchestrator_decision<br/>启发式兜底"]
        HEUR["_heuristic_split_tasks<br/>正则切分 + 意图猜测"]
        BUILDLLM["_build_structured_llm<br/>json_schema 优先"]
    end

    subgraph Executor["🔄 Executor 组件"]
        PREPARE["_prepare_subtask<br/>取任务 / 重置字段"]
        ROUTE["_route<br/>路由到 worker"]
        WORKERS["worker 节点<br/>(共用)"]
        COLLECT["_collect_subtask<br/>归档 sub_results"]
        AFTER["_after_collect<br/>next / done"]
    end

    subgraph Aggregator["🎁 Aggregator 组件"]
        SYNTH["_synthesize_final<br/>Markdown 分段<br/>+ dedupe cards/sources"]
        FMT["format_response<br/>打包 AIResponse"]
    end

    subgraph 数据契约["📋 数据契约"]
        DECISION["OrchestratorDecision<br/>{mode, reason, tasks[]}"]
        TASK["OrchestratorTask<br/>{id, question,<br/>intent_hint, depends_on}"]
        STATE_D["AssistantState<br/>共享字段"]
    end

    RUN --> BUILD --> COMPILE
    BUILD -.引用.-> ANALYZE
    BUILD -.引用.-> PREPARE
    BUILD -.引用.-> ROUTE
    BUILD -.引用.-> WORKERS
    BUILD -.引用.-> COLLECT
    BUILD -.引用.-> SYNTH
    BUILD -.引用.-> FMT

    ANALYZE --> BUILDLLM
    ANALYZE --> NORMALIZE
    ANALYZE --> FALLBACK
    FALLBACK --> HEUR
    NORMALIZE --> DECISION
    HEUR --> TASK

    PREPARE --> STATE_D
    COLLECT --> STATE_D
    SYNTH --> STATE_D
    AFTER --> STATE_D

    classDef planner fill:#fef3c7,stroke:#d97706,stroke-width:2px
    classDef exec fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    classDef agg fill:#fce7f3,stroke:#db2777,stroke-width:2px
    classDef contract fill:#e0e7ff,stroke:#6366f1,stroke-dasharray:5 5
    classDef entry fill:#dbeafe,stroke:#2563eb

    class RUN entry
    class BUILD,COMPILE entry
    class ANALYZE,NORMALIZE,FALLBACK,HEUR,BUILDLLM planner
    class PREPARE,ROUTE,WORKERS,COLLECT,AFTER exec
    class SYNTH,FMT agg
    class DECISION,TASK,STATE_D contract
```

**组件划分**：

| 组件 | 内部函数 | 职责 |
| --- | --- | --- |
| 🟡 **Planner** | `_analyze_request` + `_normalize` + `_fallback` + `_heuristic_split_tasks` + `_build_structured_llm` | 判断 simple/complex、生成任务 DAG、四重反空返回防线 |
| 🔄 **Executor** | `_prepare_subtask` + `_route` + worker 节点 + `_collect_subtask` + `_after_collect` | 串行执行子任务、共享 State、循环控制 |
| 🎁 **Aggregator** | `_synthesize_final` + `format_response` | 聚合 Markdown 答案、去重卡片/来源、打包最终响应 |
| 📋 **数据契约** | `OrchestratorDecision` + `OrchestratorTask` + `AssistantState` | 三层间数据流转的强类型契约 |

---

### 0.3 依赖关系一览

```mermaid
flowchart LR
    subgraph 上游["调用方"]
        HTTP[HTTP /run]
        SSE[SSE /stream]
    end

    subgraph 主干["AssistantGraph"]
        GR[graph.py]
    end

    subgraph 内部依赖["ai-service 内依赖"]
        ND[nodes.py]
        SP[shopping/agent]
        KN[knowledge/agent]
        ST[state.py]
        SH[schemas.py]
        PR[prompts.py]
        RT[runtime.py]
        MEM[memory.py]
        LLM[core/llm.py]
        ERR[core/errors.py]
    end

    subgraph 外部依赖["外部依赖"]
        LG["langgraph<br/>StateGraph / checkpointer /<br/>store / add_messages"]
        LC["langchain<br/>with_structured_output /<br/>create_agent"]
        PYD[pydantic BaseModel]
    end

    HTTP --> GR
    SSE --> GR

    GR --> ND
    GR --> ST
    GR --> SH
    GR --> PR
    GR --> RT
    GR --> MEM
    GR --> ERR

    ND --> SP
    ND --> KN
    ND --> LLM

    SP --> LLM
    KN --> LLM

    GR --> LG
    GR --> LC
    ND --> LG
    SP --> LG
    KN --> LG
    SH --> PYD
    ST --> LG

    classDef caller fill:#dbeafe,stroke:#2563eb
    classDef core fill:#fef3c7,stroke:#d97706,stroke-width:2px
    classDef internal fill:#dcfce7,stroke:#16a34a
    classDef external fill:#f3e8ff,stroke:#9333ea

    class HTTP,SSE caller
    class GR core
    class ND,SP,KN,ST,SH,PR,RT,MEM,LLM,ERR internal
    class LG,LC,PYD external
```

关键依赖：

- `graph.py` 是**唯一**同时依赖 `langgraph.StateGraph` 和所有编排层模块的枢纽
- worker 节点通过 `nodes.py` 接入，`shopping/agent.py` 和 `knowledge/agent.py` 本身**不感知** Orchestrator 存在（松耦合）
- `state.py` 的 `AssistantState` 是全图 State 契约，改字段前需确认所有节点都能兼容
- 外部只依赖 langgraph / langchain / pydantic 三大件，没有绑定其他编排框架

---

## 一、主图整体拓扑

```mermaid
flowchart TD
    START([START]) --> analyze[analyze_request<br/>意图 + 复杂度分析]

    analyze -->|simple| route[route_intent<br/>意图路由]
    analyze -->|complex| prepare[prepare_subtask<br/>准备下一个子任务]

    prepare --> route

    route -->|shopping| shopping[shopping<br/>导购 Agent]
    route -->|knowledge| knowledge[knowledge<br/>知识 Agent]
    route -->|chitchat| chitchat[chitchat<br/>闲聊 Agent]
    route -->|unknown| unknown[unknown<br/>兜底节点]

    shopping --> after_worker{orchestrator_mode?}
    knowledge --> after_worker
    chitchat --> after_worker
    unknown --> after_worker

    after_worker -->|simple| format[format_response<br/>拼装最终响应]
    after_worker -->|complex| collect[collect_subtask<br/>归档子任务结果]

    collect --> after_collect{还有子任务?}
    after_collect -->|next| prepare
    after_collect -->|done| synth[synthesize_final<br/>聚合 Markdown 分段]

    synth --> format
    format --> END([END])

    classDef planner fill:#fef3c7,stroke:#d97706,stroke-width:2px
    classDef worker fill:#dbeafe,stroke:#2563eb,stroke-width:1.5px
    classDef loop fill:#dcfce7,stroke:#16a34a,stroke-width:1.5px
    classDef terminal fill:#fce7f3,stroke:#db2777,stroke-width:1.5px

    class analyze,prepare,synth planner
    class route,shopping,knowledge,chitchat,unknown worker
    class collect loop
    class format terminal
```

**节点分组**：

| 分组 | 节点 | 职责 |
|-----|-----|-----|
| 🟡 Planner | `analyze_request` / `prepare_subtask` / `synthesize_final` | Orchestrator 编排逻辑 |
| 🔵 Worker | `route_intent` / `shopping` / `knowledge` / `chitchat` / `unknown` | 业务执行，simple / complex 共享 |
| 🟢 Loop | `collect_subtask` | 子任务收尾 + 循环控制 |
| 🩷 Terminal | `format_response` | 最终响应打包 |

---

## 二、两条路径对比

### 2.1 simple 路径（单意图 / 澄清补充 / 元问题）

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant G as AssistantGraph
    participant P as Planner<br/>(orchestrator_llm)
    participant R as Router<br/>(router_llm)
    participant W as Worker<br/>(shopping/knowledge/...)
    participant F as format_response

    U->>G: question
    G->>P: analyze_request<br/>ORCHESTRATOR_PROMPT
    P-->>G: mode=simple<br/>tasks=[]
    G->>R: route_intent<br/>ROUTER_PROMPT
    R-->>G: route=shopping|knowledge|...
    G->>W: 执行业务
    W-->>G: answer + product_cards + sources
    G->>F: format_response
    F-->>U: AIResponse
```

**特征**：
- Planner 判断为 simple → 直接跳过所有 orchestrator 节点
- 与老版主图行为完全一致，无额外延迟（Planner 那次调用是 500-800ms 内的一次预判）

### 2.2 complex 路径（跨意图 / 依赖追问 / 多独立问题）

```mermaid
sequenceDiagram
    autonumber
    participant U as 用户
    participant G as AssistantGraph
    participant P as Planner
    participant R as Router
    participant W1 as Worker(t1)
    participant W2 as Worker(t2)
    participant W3 as Worker(t3)
    participant S as synthesize_final

    U->>G: "推荐防晒+烟酰胺功效+价格对比"
    G->>P: analyze_request
    P-->>G: mode=complex<br/>tasks=[t1, t2, t3]

    Note over G: 循环开始（current_idx=0）

    G->>G: prepare_subtask(t1)
    G->>R: route_intent(t1.question)
    R-->>G: route=shopping
    G->>W1: shopping
    W1-->>G: 推荐 3 款防晒
    G->>G: collect_subtask(t1)

    G->>G: prepare_subtask(t2)
    G->>R: route_intent(t2.question)
    R-->>G: route=knowledge
    G->>W2: knowledge
    W2-->>G: 烟酰胺功效知识
    G->>G: collect_subtask(t2)

    G->>G: prepare_subtask(t3)
    G->>R: route_intent(t3.question)
    R-->>G: route=shopping
    G->>W3: shopping
    W3-->>G: 价格对比（依赖 t1 商品）
    G->>G: collect_subtask(t3)

    Note over G: 循环结束（idx == len(tasks)）

    G->>S: synthesize_final
    S-->>U: Markdown 分段答案<br/>1. ... 2. ... 3. ...
```

**关键点**：
- 子任务**串行执行**（Phase 1 简化实现，Phase 2 再看是否上 DAG 并行）
- 所有子任务共享主图 `checkpointer` + `messages`，t2/t3 能看到 t1 的 AIMessage 上下文
- t3 的 `depends_on=["t1"]` 让 route 有依据判断"这些商品"指代前面 t1 推荐的商品

---

## 三、State 流转（AssistantState）

```mermaid
flowchart LR
    subgraph 输入["🟦 输入字段"]
        question
        conversation_id
        user_id
        jwt_token
    end

    subgraph Planner产出["🟡 Planner 产出"]
        original_question
        orchestrator_mode
        orchestrator_reason
        sub_questions
        current_subquestion_index
    end

    subgraph 子任务运行["🟢 子任务运行时"]
        active_subtask
        subtask_heading
        answer
        product_cards
        sources
        tool_calls
    end

    subgraph 聚合["🩷 最终聚合"]
        sub_results
        result
    end

    输入 --> Planner产出
    Planner产出 -->|prepare_subtask| 子任务运行
    子任务运行 -->|collect_subtask| 聚合
    聚合 -->|synthesize_final| result
```

**字段用途索引**（见 `agents/state.py`）：

| 字段 | 写入节点 | 读取方 |
|-----|---------|-------|
| `original_question` | analyze_request | 后续 log / 兜底 |
| `orchestrator_mode` | analyze_request | `_after_analyze` 路由 / SSE / 前端 |
| `orchestrator_reason` | analyze_request | SSE / 前端展示分段理由 |
| `sub_questions` | analyze_request | prepare_subtask 取任务 / 前端展示 DAG |
| `current_subquestion_index` | analyze_request → collect_subtask | prepare_subtask 取下一个 / `_after_collect` |
| `active_subtask` | prepare_subtask | collect_subtask 归档时读回 |
| `subtask_heading` | prepare_subtask | SSE `orchestrator_subtask` + `token` 事件 |
| `answer / product_cards / sources / tool_calls` | worker 节点 | collect_subtask 归档到 sub_results |
| `sub_results` | collect_subtask（累加） | synthesize_final 聚合 |
| `result` | format_response | API `/run` 或 SSE `final` 事件 |

---

## 四、Planner 决策与四重反空返回防线

`_analyze_request` 内部执行流程，重点是 Bug 1/2/3 的修复落点：

```mermaid
flowchart TD
    start_node([进入 analyze_request]) --> check_empty{question 为空?}
    check_empty -->|是| simple_empty[return simple<br/>reason=问题为空]
    check_empty -->|否| check_llm{orchestrator_llm 存在?}
    check_llm -->|否| fallback_no_llm[启发式兜底<br/>reason=编排模型未配置]

    check_llm -->|是| build_msg[拼装 messages<br/>ORCHESTRATOR_PROMPT + 上下文 + 历史]
    build_msg --> call1[Planner LLM 调用 #1<br/>method=json_schema ✅ Bug 1]

    call1 -->|异常| fallback_exc[启发式兜底<br/>reason=结构化拆解失败]
    call1 -->|成功| check_none1{decision is None?}

    check_none1 -->|否| normalize[_normalize_decision]
    check_none1 -->|是| log_retry[⚠️ WARN + 重试一次<br/>✅ Bug 2 主动重试]
    log_retry --> call2[Planner LLM 调用 #2]

    call2 -->|异常| fallback_retry_exc[启发式兜底<br/>reason=重试失败]
    call2 -->|成功| check_none2{decision is None?}

    check_none2 -->|是| fallback_still_none[启发式兜底<br/>reason=结构化拆解返回空<br/>✅ Bug 2 长尾防御]
    check_none2 -->|否| normalize

    normalize --> check_half_baked{LLM 说 complex<br/>但 tasks &lt; 2?}
    check_half_baked -->|是| fallback_half[启发式兜底<br/>reason=LLM 拆解不完整<br/>✅ Bug 2 二次防御]
    check_half_baked -->|否| return_normalized[return normalized]

    subgraph 启发式引擎["_heuristic_split_tasks (✅ Bug 3)"]
        heur_split[正则切分:<br/>然后/还有/另外/顺便/再/以及/并且/<br/>此外/同时/另/接着 +<br/>前瞻断言 第X个/它们/这几款/前面]
        heur_intent[_guess_intent_hint 关键词表<br/>shopping/knowledge/chitchat]
        heur_deps["依赖识别:<br/>t2+ 含 这些/它们/第X个 → depends_on=[t1]"]

        heur_split --> heur_intent --> heur_deps
    end

    fallback_exc --> 启发式引擎
    fallback_no_llm --> 启发式引擎
    fallback_retry_exc --> 启发式引擎
    fallback_still_none --> 启发式引擎
    fallback_half --> 启发式引擎

    classDef bug1 fill:#fef3c7,stroke:#d97706,stroke-width:2px
    classDef bug2 fill:#dcfce7,stroke:#16a34a,stroke-width:2px
    classDef bug3 fill:#dbeafe,stroke:#2563eb,stroke-width:2px

    class call1 bug1
    class log_retry,check_none2,fallback_still_none,check_half_baked,fallback_half bug2
    class heur_split,heur_intent,heur_deps bug3
```

**四重防线映射到代码**：

| 层 | 修复内容 | 代码位置 |
|---|---------|---------|
| 🟡 Bug 1 | `method="json_schema"` 主选，异常回退 `function_calling` | [graph.py `_build_structured_llm`](../ai-service/assistant/graph.py) |
| 🟢 Bug 2a | `decision is None` 主动重试一次 | `_analyze_request` 步骤 3 |
| 🟢 Bug 2b | 重试仍空 → 启发式兜底 + warning 日志 | `_analyze_request` 步骤 5 |
| 🟢 Bug 2c | LLM 声称 complex 但 tasks &lt; 2 → 启发式补救 | `_analyze_request` 步骤 7 |
| 🔵 Bug 3 | 启发式 pattern 补 `此外/同时/第X个` + 前瞻断言 | `_HEURISTIC_SPLIT_PATTERN` |

---

## 五、SSE 事件时序（complex 场景）

前端会依次收到以下事件（`assistant/graph.py::astream`）：

```mermaid
sequenceDiagram
    participant B as 前端
    participant G as AssistantGraph
    participant W as Worker

    G-->>B: 🚀 start<br/>{run_id, trace_id, conversation_id}
    G-->>B: 📋 orchestrator_plan<br/>{mode:complex, reason, tasks:[t1,t2,t3]}

    Note over G: 循环第 1 轮

    G-->>B: 🏷️ orchestrator_subtask<br/>{task:t1, heading:"1. 推荐防晒"}
    G-->>B: 💬 token "我会分成几个部分依次回答：\n\n1. 推荐防晒\n"
    G-->>B: 🧭 route<br/>{task_type:shopping, reason}
    W-->>G: 流式生成子任务答案
    G-->>B: 💬 token (子任务 1 的答案，逐字)
    G-->>B: 💬 token ...

    Note over G: 循环第 2 轮

    G-->>B: 🏷️ orchestrator_subtask<br/>{task:t2, heading:"\n\n2. 烟酰胺功效"}
    G-->>B: 💬 token "\n\n2. 烟酰胺功效\n"
    G-->>B: 🧭 route<br/>{task_type:knowledge}
    W-->>G: ...
    G-->>B: 💬 token (子任务 2 答案)

    Note over G: 循环第 3 轮

    G-->>B: 🏷️ orchestrator_subtask<br/>{task:t3, heading:"\n\n3. 价格对比"}
    G-->>B: 💬 token "\n\n3. 价格对比\n"
    G-->>B: 🧭 route<br/>{task_type:shopping}
    W-->>G: ...
    G-->>B: 💬 token (子任务 3 答案)

    G-->>B: 🎁 final<br/>AIResponse (含 sub_questions, sub_results)
    G-->>B: 🏁 done
```

**事件类型完整清单**：

| type | 何时 emit | data 字段 | 前端用途 |
|-----|----------|----------|---------|
| `start` | 请求开始 | `run_id / trace_id / conversation_id` | 记录会话 |
| `orchestrator_plan` | analyze_request 判定 complex | `mode / reason / tasks[]` | 显示"分成 N 个部分" |
| `orchestrator_subtask` | 每次 prepare_subtask | `task{id,question,intent_hint,depends_on} / heading` | 分段标题条 / DAG 进度 |
| `token` | LLM 流式增量 | `content` | 打字机效果 |
| `route` | route_intent 完成 | `task_type / reason` | 显示当前子任务走哪个 Agent |
| `tool_call` | 工具被调用 | `tool_name / input` | 工具调用可视化 |
| `tool_result` | 工具返回 | `tool_name / output` | 同上 |
| `final` | format_response 结束 | 完整 `AIResponse` | 拿到最终结构化响应 |
| `done` | 流关闭 | `{}` | 前端关流 |
| `error` | 异常 | `error_code / message` | 错误提示 |

---

## 六、意图路由内部结构（route_intent 节点内部）

```mermaid
flowchart LR
    in([进入 route_intent]) --> get_q[取 question]
    get_q --> load_mem[读 business_memory<br/>last_product_cards<br/>last_focused_product<br/>last_knowledge_entities<br/>user_preferences]
    load_mem --> build[拼 messages:<br/>ROUTER_PROMPT SystemMessage +<br/>context SystemMessage +<br/>history]
    build --> call[router_llm.ainvoke<br/>with_structured_output IntentDecision]
    call -->|异常/None| unknown_out["return route=unknown"]
    call -->|正常| out["return route + route_reason"]

    classDef ctx fill:#f0f9ff,stroke:#0284c7
    class load_mem ctx
```

- ROUTER_PROMPT 内容参考 [prompts.py](../ai-service/agents/prompts.py) `ROUTER_PROMPT`
- 关键分类规则：指代词 + 上下文类型双维判断（"更便宜"→ shopping、"副作用"→ knowledge）
- 复合意图按第一个意图分类 —— 这层判断被 Orchestrator 覆盖了，用户的复合意图先被 analyze_request 拆完再进 route_intent

---

## 七、常见路径示例

### 7.1 单意图推荐

```
用户: "给我推荐一款适合油皮的防晒"
────────────────────────────────────
analyze_request → mode=simple
route_intent → shopping
shopping_node → 3 款防晒 + product_cards
format_response → AIResponse (task_type=shopping)
```

### 7.2 单意图多细节（正确不拆解）

```
用户: "烟酰胺是什么、怎么用、有什么注意事项？"
────────────────────────────────────
analyze_request → mode=simple ⭐ 判断这是同一意图，KnowledgeAgent 一次分点回答
route_intent → knowledge
knowledge_node → 分 3 点回答
format_response → AIResponse (task_type=knowledge)
```

### 7.3 跨意图 + 依赖（Orchestrator 典型场景）

```
用户: "推荐三款补水面霜，然后比较这些哪个更便宜，第二个含什么成分？"
────────────────────────────────────
analyze_request → mode=complex
  tasks = [
    { id: t1, q: "推荐三款补水面霜",     intent: shopping,  deps: []      },
    { id: t2, q: "比较这些哪个更便宜",   intent: shopping,  deps: [t1]    },
    { id: t3, q: "第二个含什么成分？",   intent: knowledge, deps: [t1]    },
  ]

prepare_subtask(t1) → route_intent → shopping → 推荐 → collect(t1)
prepare_subtask(t2) → route_intent → shopping → 对比 → collect(t2)
prepare_subtask(t3) → route_intent → knowledge → 成分 → collect(t3)
synthesize_final → Markdown "1. ... 2. ... 3. ..."
format_response → AIResponse (task_type=orchestrator)
```

### 7.4 LLM 空返回 → 启发式兜底（Bug 修复后的路径）

```
用户: 复合问题
────────────────────────────────────
analyze_request
  → LLM 调用返回 None
  → ⚠️ WARN "结构化拆解返回 None，重试一次"
  → 重试 LLM 调用
  → 若仍 None
    → ⚠️ WARN "结构化拆解重试后仍为空，尝试启发式拆解"
    → _heuristic_split_tasks(question) 拆出 N 个 task
    → 若 N ≥ 2  → mode=complex 进 Orchestrator
    → 若 N < 2  → mode=simple 走原路径
```

---

## 八、图表维护约定

- 修改主图拓扑（增删节点 / 改路由条件）时，必须同步更新 §1 的 `flowchart TD`
- 修改 State 字段时，必须同步更新 §3 的字段索引表
- 新增 SSE 事件类型时，必须同步更新 §5 的事件清单
- 修改 Planner 逻辑（比如未来接入并行 DAG scheduler）时，重画 §4 的决策流程图
- 图表默认用 Mermaid，GitHub / VSCode Markdown Preview / Obsidian 都能直接渲染

---

## 九、相关文档

- 测试基线：[orchestrator-test-data-and-results.md](./orchestrator-test-data-and-results.md)
- Bug 调查记录：[orchestrator-known-issues.md](./orchestrator-known-issues.md)
- Feature commit：`12d8350 feat(ai-service): 主图接入 Orchestrator 多问题拆解 + 反空返回四重防线`
- 反幻觉前置工作：`1a7b884 feat(ai-service): 知识问答接入博查兜底 + 反幻觉四层防线`
