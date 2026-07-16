# Phase 3 用户偏好个性化推荐测试指南

## 1. 测试目标

验证用户画像和对话中学习到的偏好能够稳定参与文本、图片和图文商品推荐，同时保证：

1. 本轮明确条件始终高于长期偏好；
2. 长期偏好只做软重排，不作为不可靠的硬过滤条件；
3. 图片候选只根据数据库结构化文本字段做偏好判断，不增加视觉 LLM Judge；
4. 偏好有来源、置信度、更新时间、过期时间、正负向和品类作用域；
5. 旧版 `skin_type/preference_tags` 数据保持兼容；
6. 推荐结果能够解释匹配偏好或偏好冲突；
7. H5 能接收 AI 返回的 `suggested_questions`，并用于下一次新会话的“猜你想问”。

## 2. 偏好事实结构

```json
{
  "aspect": "preference",
  "value": "清爽",
  "polarity": "like",
  "source": "explicit_user_statement",
  "confidence": 0.9,
  "updated_at": "2026-07-16T12:00:00+08:00",
  "expires_at": "2027-01-12T12:00:00+08:00",
  "scope": {
    "category": "防晒"
  }
}
```

关键语义：

- `polarity=like`：正向偏好；
- `polarity=dislike`：避雷项；
- `source=registered_profile`：注册/资料页画像；
- `source=explicit_user_statement`：用户在对话里明确表达；
- `scope.category`：只对相同或兼容商品品类生效；
- `expires_at`：过期事实不参与排序；
- 新的冲突事实覆盖同作用域的旧事实。

## 3. 优先级

```text
本轮明确条件
> 本轮解析出的偏好/避雷项
> 长期显式偏好事实
> 注册画像标签
> 商品热度与召回顺序
```

示例：用户长期喜欢“清爽”，但本轮明确说“这次想要滋润一些”，本轮“滋润”必须优先，长期“清爽”不得反向拉高商品。

长期预算只参与软重排，不写入 Milvus/PG 的硬过滤条件。只有用户本轮明确提出的预算才能进入检索过滤。

## 4. 自动化测试

在 `ai-service` 目录执行：

```powershell
python -m pytest tests/test_personalization.py -q
python -m pytest tests/test_shopping_ranking_and_cards.py -q
python -m pytest tests/test_recommend_capability.py -q
python -m pytest tests/test_assistant_graph.py -q
python -m pytest tests/test_api_contract.py -q
python -m pytest tests/test_router_tools.py -q
```

如需完整回归：

```powershell
python -m pytest -q
```

H5 构建验证：

```powershell
cd ../web/welove-shop
npm run build:h5
```

## 5. 离线偏好排序评测

该评测不调用 LLM、Milvus、Redis、PostgreSQL 或 Java 服务：

```powershell
python -m evals.run_preference_eval --k 3
```

保存报告：

```powershell
python -m evals.run_preference_eval --k 3 --output evals/reports/preference-v1.json
```

输出指标：

- `Baseline Preference Compliance@3`：不使用长期偏好时 Top-3 的偏好满足率；
- `Personalized Preference Compliance@3`：加入长期偏好软重排后的满足率；
- `Preference Compliance@3 Delta`：个性化前后差值；
- `Baseline NDCG@3`：基线排序质量；
- `Personalized NDCG@3`：个性化排序质量；
- `NDCG@3 Delta`：个性化前后排序增量。

不得在未实际运行时填写指标数值。

## 6. 文本推荐必测 Case

### Case A：长期偏好生效

历史偏好：

```json
{"value":"清爽","polarity":"like","scope":{"category":"防晒"}}
```

本轮：

```text
推荐几款防晒
```

期望：

- 清爽、轻薄、水感、不黏候选获得小幅加分；
- 商品卡 `_matched_preferences` 包含 `清爽`；
- `reason` 或 `rank_reason` 包含长期偏好说明；
- 非清爽商品仍可保留，证明这是软重排而非硬过滤。

### Case B：本轮条件覆盖长期偏好

历史偏好：喜欢清爽。

本轮：

```text
这次想找滋润一些的面霜，不要清爽型
```

期望：

- `清爽` 不进入 `personalization_preferences`；
- 本轮 `滋润` 和 `avoid=清爽` 生效；
- 不得因为长期偏好把清爽商品排到前面。

### Case C：长期避雷项

历史偏好：不喜欢香味重。

期望：

- 结构化文本包含“香味重/持久留香”的商品被软降权；
- 商品卡 `_preference_conflicts` 包含对应避雷项；
- 风险提示说明偏好冲突。

### Case D：品类作用域隔离

历史偏好：防晒品类喜欢清爽。

本轮：推荐耳机。

期望：防晒的“清爽”偏好不参与耳机排序。

## 7. 图片/图文推荐必测 Case

准备同一品类的多个候选商品，并保证数据库字段中分别包含“清爽/轻薄”和“滋润/厚重”等结构化文本。

期望流程：

```text
图片/图文三路召回
→ RRF/VL Rerank
→ 品类相关性过滤
→ 结构化字段偏好软重排
→ Top-K 商品卡
```

确认：

- 偏好重排发生在相关性过滤之后；
- 不调用额外视觉 LLM 判断用户偏好；
- 图片相似度仍是主要排序先验，偏好只允许调整相邻候选；
- 不允许低相关商品仅因偏好命中越过明显高相关商品。

## 8. 偏好学习验证

用户输入：

```text
预算 200 以内，想要清爽且不要香味重的防晒
```

期望复用 ShoppingNeed 解析结果写入：

- `preference=清爽, polarity=like, scope.category=防晒`；
- `preference=香味重, polarity=dislike, scope.category=防晒`；
- `budget_max=200, scope.category=防晒`；
- 无额外偏好抽取 LLM 调用。

预算事实默认 90 天过期，普通偏好事实默认 180 天过期；肤质作为稳定画像不设置默认过期时间。

## 9. API 与 H5 验证

最终 AIResponse 新增：

```json
{
  "suggested_questions": [
    "按我油皮的情况，有哪些合适的护肤品？",
    "有哪些更符合我‘清爽’偏好的防晒？"
  ]
}
```

验证：

1. chat-service 的 SSE final 事件原样透传该字段；
2. H5 收到后更新 `learnedRecommended`；
3. 用户点击“新对话”后，“猜你想问”优先展示这些问题；
4. 没有动态偏好时继续显示原季节、肤质和通用问题。

## 10. 验收标准

1. 旧画像数据无需迁移即可生效；
2. 新偏好事实可以合并、覆盖冲突和自动过期；
3. 本轮条件覆盖长期偏好的测试通过；
4. 文本和图片推荐都产生可解释的偏好排序字段；
5. `Preference Compliance@3` 和 `NDCG@3` 个性化后不低于基线；
6. 品类作用域隔离 Case 不发生偏好串场；
7. H5 构建通过，推荐问题可以从 AI final 响应更新；
8. 外部服务不可用时应明确记录未覆盖的集成路径。
