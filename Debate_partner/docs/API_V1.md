# Debate Partner API v1（前后端联调用）

> 状态：接口契约文档（v1）  
> 目标：供 Next.js 前端按契约开发，不依赖后端源码阅读。

## 1. 范围与基线

- 基础路径：`/api/v1`
- 版本策略：从 `v1` 开始，后续破坏性变更新增 `v2`
- 当前仓库已实现 FastAPI v1 接口，文档与实现保持同步演进
- Streamlit 仍保留，作为迁移期行为基线和回归对照

本地 API 启动命令：

```bash
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
```

## 2. 单轮语义（必须遵守）

- 每次 `turn` 调用只处理一次用户动作，然后结束本次调用。
- `action=send`：执行一轮攻防链路，通常返回 `assistant_brief/assistant_detail`。
- `action=end`：直接进入报告链路，返回 `report`，并设置 `should_end=true`。
- `send` 文本中即使包含“结束”等词，也不会触发提前结束；结束只由 `action=end` 或达到 `max_rounds` 触发。
- 会话结束判定以响应中的 `should_end` 为准，不以前端本地状态猜测。

## 3. 数据模型（核心）

## 3.1 `TurnRequest`

```json
{
  "action": "send",
  "user_text": "我主张房东应当退还全部押金。"
}
```

- `action`：`send | end`
- `user_text`：用户本轮文本；`end` 时可为空字符串

## 3.2 `SessionStateSummary`

```json
{
  "session_id": "session_01HXYZ...",
  "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
  "scenario_hint": "rental_dispute",
  "max_rounds": 5,
  "round_index": 1,
  "ui_action": "send",
  "should_end": false,
  "end_reason": "",
  "end_reason_code": "IN_PROGRESS",
  "assistant_brief": "【核心反驳】...【进一步追问】...",
  "assistant_detail": "【主张概括】...【反方核心反驳】...【进一步追问】...",
  "attack_target": "证据链薄弱",
  "attack_target_category": "证据链薄弱",
  "attack_target_reason": "关键事实缺少可核验的证据链闭环支持。",
  "attack_target_source": "llm",
  "retrieval_mode": "vector",
  "knowledge_sufficiency": true,
  "knowledge_missing_aspects": [],
  "counterargument_structured": {
    "claim_summary": "你方主张房东应退还全部押金。",
    "core_rebuttal": "你方尚未证明押金扣减责任的事实闭环。",
    "legal_basis": "现有法条适配路径不完整，需补足要件映射。",
    "case_strategy": "类案通常先审查交接证据，再判断扣减合理性。",
    "evidence_challenge": "缺少退租交接清单与维修费用原始凭证。",
    "logic_challenge": "当前论证存在结论先行，推理链条断裂。",
    "support_gap_notes": []
  },
  "counterargument_citations": {
    "claim_summary": ["CASE_CN_0001"],
    "core_rebuttal": ["CASE_CN_0001"],
    "legal_basis": ["STATUTE_CN_0001"],
    "case_strategy": ["CASE_CN_0001"],
    "evidence_challenge": ["CASE_CN_0001"],
    "logic_challenge": ["ISSUE_RULE_0001"]
  },
  "counterargument_quality_flags": [],
  "report_source": null,
  "report_quality_flags": [],
  "history_count": 1,
  "updated_at": "2026-04-09T10:18:00+08:00",
  "report": null
}
```

- `assistant_brief`：主展示文本，建议直接显示在聊天气泡
- `assistant_detail`：完整分段文本，建议放在“详情展开”
- `end_reason_code`：标准化结束码（`IN_PROGRESS | USER_ENDED | MAX_ROUNDS_REACHED`）
- `attack_target_category`：固定分类，用于前端标签展示与统计（法律依据不足/证据链薄弱/因果链不完整/损失计算不充分/规则适用错误/程序或主体适格瑕疵/论点信息不足）
- `attack_target_reason`：本轮选择该攻击点的简要原因
- `attack_target_source`：`llm | fallback | reranked`
- `retrieval_mode`：`vector | keyword_fallback`
- `knowledge_sufficiency`：检索结果是否足够支撑反驳输出
- `knowledge_missing_aspects`：检索不足时的缺失维度（可能为空）
- `counterargument_structured`：结构化反驳主体（Next.js 可按段落独立渲染）
- `counterargument_citations`：按段落绑定的 `record_id` 列表（用于引用追溯）
- `counterargument_quality_flags`：质量风险标签（如缺失引用补位、fallback 生成）
- `report_source`：报告来源（`llm | fallback`，无报告时为 `null`）
- `report_quality_flags`：报告质量标签（修复/降级信息）
- `report`：仅在会话结束后出现对象；未结束时为 `null`

## 3.3 `DebateReport`

```json
{
  "debate_background": "租房押金争议",
  "user_claim_summary": ["主张退还押金"],
  "defendant_rebuttal_points": ["证据不足"],
  "user_strengths": ["主张明确"],
  "user_weaknesses": ["证据薄弱"],
  "evidence_improvement_suggestions": ["补充交接记录"],
  "legal_argument_suggestions": ["补充法条适配论证"],
  "overall_score": 72,
  "end_reason": "用户点击结束辩论"
}
```

## 3.4 `ErrorResponse`（统一错误格式）

```json
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "action must be one of: send, end",
    "details": {
      "field": "action"
    }
  },
  "trace_id": "trace_01HXYZ..."
}
```

- `error.code`：稳定错误码，前端按此分支处理
- `error.message`：给开发者的可读错误信息
- `error.details`：可选结构化上下文
- `trace_id`：用于服务端日志检索与排障

## 4. 接口定义

## 4.1 `POST /api/v1/sessions`

创建新会话并返回初始状态摘要。

请求示例：

```json
{
  "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
  "scenario_hint": "rental_dispute",
  "max_rounds": 5
}
```

响应示例（201）：

```json
{
  "session": {
    "session_id": "session_01HXYZ...",
    "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
    "scenario_hint": "rental_dispute",
    "max_rounds": 5,
    "round_index": 0,
    "ui_action": "send",
    "should_end": false,
    "end_reason": "",
    "end_reason_code": "IN_PROGRESS",
    "assistant_brief": "",
    "assistant_detail": "",
    "attack_target": "",
    "attack_target_category": "",
    "attack_target_reason": "",
    "attack_target_source": null,
    "retrieval_mode": "keyword_fallback",
    "knowledge_sufficiency": true,
    "knowledge_missing_aspects": [],
    "counterargument_structured": {},
    "counterargument_citations": {},
    "counterargument_quality_flags": [],
    "report_source": null,
    "report_quality_flags": [],
    "history_count": 0,
    "updated_at": "2026-04-09T10:00:00+08:00",
    "report": null
  }
}
```

## 4.2 `POST /api/v1/sessions/{session_id}/turn`

处理单轮动作。

### `send` 示例

请求：

```json
{
  "action": "send",
  "user_text": "我主张房东应退还押金。"
}
```

响应（200）：

```json
{
  "session": {
    "session_id": "session_01HXYZ...",
    "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
    "scenario_hint": "rental_dispute",
    "max_rounds": 5,
    "round_index": 1,
    "ui_action": "send",
    "should_end": false,
    "end_reason": "",
    "end_reason_code": "IN_PROGRESS",
    "assistant_brief": "【核心反驳】现有证据不足以支持你的结论。\\n【进一步追问】请补充入住与退租时的对比证据。",
    "assistant_detail": "【主张概括】...\\n【反方核心反驳】...\\n【法律依据】...\\n【进一步追问】...",
    "attack_target": "证据链薄弱",
    "attack_target_category": "证据链薄弱",
    "attack_target_reason": "关键事实缺少可核验的证据链闭环支持。",
    "attack_target_source": "llm",
    "retrieval_mode": "vector",
    "knowledge_sufficiency": true,
    "knowledge_missing_aspects": [],
    "counterargument_structured": {
      "claim_summary": "你方主张房东应退还押金。",
      "core_rebuttal": "现有证据不足以支持全额返还。",
      "legal_basis": "需补足法条要件与事实映射。",
      "case_strategy": "优先核查交接记录与损耗证据。",
      "evidence_challenge": "你方证据链缺少关键时间节点。",
      "logic_challenge": "事实到责任的推导存在跳步。",
      "support_gap_notes": []
    },
    "counterargument_citations": {
      "claim_summary": ["CASE_CN_0001"],
      "core_rebuttal": ["CASE_CN_0001"],
      "legal_basis": ["STATUTE_CN_0001"],
      "case_strategy": ["CASE_CN_0001"],
      "evidence_challenge": ["CASE_CN_0001"],
      "logic_challenge": ["ISSUE_RULE_0001"]
    },
    "counterargument_quality_flags": [],
    "report_source": null,
    "report_quality_flags": [],
    "history_count": 1,
    "updated_at": "2026-04-09T10:12:30+08:00",
    "report": null
  }
}
```

### `end` 示例

请求：

```json
{
  "action": "end",
  "user_text": ""
}
```

响应（200）：

```json
{
  "session": {
    "session_id": "session_01HXYZ...",
    "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
    "scenario_hint": "rental_dispute",
    "max_rounds": 5,
    "round_index": 1,
    "ui_action": "end",
    "should_end": true,
    "end_reason": "用户点击结束辩论",
    "end_reason_code": "USER_ENDED",
    "assistant_brief": "【核心反驳】本轮不再追加新的攻防观点，辩论已结束。\\n【进一步追问】请查看页面右侧的“辩论总结报告”区域。",
    "assistant_detail": "【核心反驳】...\\n【进一步追问】...\\n【系统说明】结束原因：用户点击结束辩论；报告生成方式：标准模式。",
    "attack_target": "证据链薄弱",
    "attack_target_category": "证据链薄弱",
    "attack_target_reason": "关键事实缺少可核验的证据链闭环支持。",
    "attack_target_source": "llm",
    "retrieval_mode": "vector",
    "knowledge_sufficiency": true,
    "knowledge_missing_aspects": [],
    "counterargument_structured": {
      "claim_summary": "你方主张房东应退还押金。",
      "core_rebuttal": "本轮不再追加新的攻防观点，转入总结。",
      "legal_basis": "本轮结束，不新增法条展开。",
      "case_strategy": "本轮结束，不新增类案展开。",
      "evidence_challenge": "本轮结束，不新增证据质疑。",
      "logic_challenge": "本轮结束，不新增逻辑质疑。",
      "support_gap_notes": []
    },
    "counterargument_citations": {
      "claim_summary": ["CASE_CN_0001"],
      "core_rebuttal": ["CASE_CN_0001"],
      "legal_basis": ["STATUTE_CN_0001"],
      "case_strategy": ["CASE_CN_0001"],
      "evidence_challenge": ["CASE_CN_0001"],
      "logic_challenge": ["ISSUE_RULE_0001"]
    },
    "counterargument_quality_flags": [],
    "report_source": "llm",
    "report_quality_flags": [],
    "history_count": 1,
    "updated_at": "2026-04-09T10:15:00+08:00",
    "report": {
      "debate_background": "租房押金争议",
      "user_claim_summary": ["主张退还押金"],
      "defendant_rebuttal_points": ["证据不足"],
      "user_strengths": ["主张明确"],
      "user_weaknesses": ["证据薄弱"],
      "evidence_improvement_suggestions": ["补充交接记录"],
      "legal_argument_suggestions": ["补充法条适配论证"],
      "overall_score": 72,
      "end_reason": "用户点击结束辩论"
    }
  }
}
```

## 4.3 `GET /api/v1/sessions/{session_id}`

查询会话当前状态，用于页面刷新或恢复。

响应（200）：

```json
{
  "session": {
    "session_id": "session_01HXYZ...",
    "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
    "scenario_hint": "rental_dispute",
    "max_rounds": 5,
    "round_index": 1,
    "ui_action": "send",
    "should_end": false,
    "end_reason": "",
    "end_reason_code": "IN_PROGRESS",
    "assistant_brief": "【核心反驳】...",
    "assistant_detail": "【主张概括】...",
    "attack_target": "证据链薄弱",
    "attack_target_category": "证据链薄弱",
    "attack_target_reason": "关键事实缺少可核验的证据链闭环支持。",
    "attack_target_source": "llm",
    "retrieval_mode": "vector",
    "knowledge_sufficiency": true,
    "knowledge_missing_aspects": [],
    "counterargument_structured": {
      "claim_summary": "你方主张房东应退还押金。",
      "core_rebuttal": "现有证据不足以支撑你的结论。",
      "legal_basis": "需补足法条要件映射。",
      "case_strategy": "优先核查交接记录与损耗证据。",
      "evidence_challenge": "缺少关键原始凭证。",
      "logic_challenge": "推理链条存在跳步。",
      "support_gap_notes": []
    },
    "counterargument_citations": {
      "claim_summary": ["CASE_CN_0001"],
      "core_rebuttal": ["CASE_CN_0001"],
      "legal_basis": ["STATUTE_CN_0001"],
      "case_strategy": ["CASE_CN_0001"],
      "evidence_challenge": ["CASE_CN_0001"],
      "logic_challenge": ["ISSUE_RULE_0001"]
    },
    "counterargument_quality_flags": [],
    "report_source": null,
    "report_quality_flags": [],
    "history_count": 1,
    "updated_at": "2026-04-09T10:16:00+08:00",
    "report": null
  }
}
```

## 4.4 `GET /api/v1/health`

用于部署探活和前端启动前连通性检查。

响应（200）：

```json
{
  "status": "ok",
  "service": "debate-agent",
  "version": "v1",
  "timestamp": "2026-04-09T10:20:00+08:00"
}
```

## 5. 常见错误码与前端处理建议

- `INVALID_ARGUMENT`
  - 场景：`action` 非法、`max_rounds` 越界、`user_text` 长度超限
  - 建议：提示用户修正输入，保持提交按钮可用
- `SESSION_NOT_FOUND`
  - 场景：`session_id` 不存在或已过期
  - 建议：提示会话失效，引导重建会话
- `SESSION_ALREADY_ENDED`
  - 场景：会话已结束仍尝试 `send`
  - 建议：禁用发送，仅允许“新建会话”
- `INTERNAL_ERROR`
  - 场景：服务端未预期异常
  - 建议：显示通用错误并支持重试；上报 `trace_id`

## 6. 联调建议（Next.js）

- 首屏加载先调用 `GET /api/v1/health`
- 新开对话时调用 `POST /api/v1/sessions`
- 用户发送消息调用 `POST /api/v1/sessions/{session_id}/turn`（`action=send`）
- 用户点击结束调用同一路径（`action=end`）
- 页面恢复时调用 `GET /api/v1/sessions/{session_id}`
- 本地向量索引构建（首次）：`python -m app.knowledge.index_cli build`
- 新增 JSONL 后更新索引：`python -m app.knowledge.index_cli update`
- 索引与模型缓存校验：`python -m app.knowledge.index_cli verify`
- 本地模型缓存硬约束：`HF_HOME`、`SENTENCE_TRANSFORMERS_HOME`、`TRANSFORMERS_CACHE`、`TORCH_HOME`、`XDG_CACHE_HOME` 必须在 `D:\`，否则会返回 `MODEL_CACHE_PATH_INVALID`

## 7. 契约测试清单（后续实现 API 时逐条对照）

- `POST /sessions`：默认值生效（`max_rounds=5`、`ui_action=send`）
- `POST /sessions/{id}/turn(send)`：`round_index` 递增，`report=null`
- `POST /sessions/{id}/turn(end)`：`should_end=true`，`report` 非空
- `GET /sessions/{id}`：与最近一次 `turn` 返回状态一致
- 错误响应：所有 4xx/5xx 都返回统一 `ErrorResponse`

## 8. 与 Streamlit 基线对齐说明

- `assistant_brief` 对齐 Streamlit 主气泡展示字段
- `assistant_detail` 对齐 Streamlit “详情”展开字段
- `report` 只在会话结束后展示，对齐现有底部报告区行为
- Streamlit 页面提供“节点观测（测试用）”面板，可直接核验链路状态、结构化反驳、报告来源与调试字段
- 文档字段以 `DebateState` 关键子集为准，未引入未实现能力
