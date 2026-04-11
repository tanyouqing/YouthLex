# Frontend Agent 接入指南（Next.js 目标）

> 读者：负责前端实现的 coding agent  
> 目标：不读后端源码也能按契约完成前端页面与联调

## 1. 项目简要内容

- 项目是一个“法律辩论陪练 Agent”，当前主链路已完整：
  - `init_session -> fetch_user_input -> parse_user_claim -> identify_attack_target -> retrieve_knowledge -> assess_knowledge_support -> build_counterargument -> judge_continue_or_end -> (ask_next_challenge | generate_debate_report)`
- 单轮语义：
  - 每次调用只处理一次动作（`send` 或 `end`），完成后即返回当前状态
- 当前阶段：
  - Streamlit 可直接测试完整图
  - Next.js 为下一阶段目标前端
  - FastAPI v1 已实现，可直接联调（默认 `http://localhost:8000/api/v1`）

## 2. 何处需要调用（前端调用边界）

前端只需要调用“会话 API 层”，不直接调用节点函数。

本地 API 启动命令：

```bash
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
```

### 2.1 启动与会话流程

1. 页面启动：调用 `GET /api/v1/health` 做探活。  
2. 新会话：调用 `POST /api/v1/sessions`。  
3. 用户发送：调用 `POST /api/v1/sessions/{session_id}/turn`，`action=send`。  
4. 用户结束：调用同一 `turn` 接口，`action=end`。  
5. 页面刷新恢复：调用 `GET /api/v1/sessions/{session_id}`。

### 2.2 当前回归基线（Streamlit）

- 测试入口：`streamlit run streamlit_app.py`
- 页面底部有 `节点观测（测试用）` 面板，可对照 API 字段验证：
  - `end_reason_code`
  - `counterargument_structured/citations`
  - `report_source/report_quality_flags`
  - `debug.*`

## 3. API 接口（v1 契约）

权威来源：
- 人读版：[API_V1.md](/D:/tencentKAIWU/Debate_partner/docs/API_V1.md)
- OpenAPI：[debate-agent-v1.yaml](/D:/tencentKAIWU/Debate_partner/docs/openapi/debate-agent-v1.yaml)

### 3.1 基础路径

- `/api/v1`

### 3.2 接口清单

- `POST /api/v1/sessions`
  - 创建会话，返回 `session` 状态摘要
- `POST /api/v1/sessions/{session_id}/turn`
  - 单轮动作：`action=send | end`
- `GET /api/v1/sessions/{session_id}`
  - 查询会话当前状态（页面恢复）
- `GET /api/v1/health`
  - 服务探活

### 3.3 关键请求/响应字段（前端必须消费）

- 请求：
  - `TurnRequest.action`: `send | end`
  - `TurnRequest.user_text`: 文本内容，`end` 可空
- 响应 `SessionStateSummary`：
  - 会话控制：`session_id`, `round_index`, `should_end`, `end_reason`, `end_reason_code`
  - 展示文本：`assistant_brief`, `assistant_detail`
  - 攻击点：`attack_target`, `attack_target_category`, `attack_target_reason`, `attack_target_source`
  - 检索状态：`retrieval_mode`, `knowledge_sufficiency`, `knowledge_missing_aspects`
  - 结构化反驳：`counterargument_structured`, `counterargument_citations`, `counterargument_quality_flags`
  - 报告状态：`report_source`, `report_quality_flags`, `report`

### 3.4 错误模型（统一）

- `ErrorResponse`：
  - `error.code`
  - `error.message`
  - `error.details`
  - `trace_id`
- 常见错误码：
  - `INVALID_ARGUMENT`
  - `SESSION_NOT_FOUND`
  - `SESSION_ALREADY_ENDED`
  - `INTERNAL_ERROR`

## 4. 前端必须有的内容（硬性要求）

### 4.1 页面与布局

- 单页主界面（或等价路由）必须是三栏结构：
  - 左侧边栏（固定）：配置区（你要求的“绘画配置”，按本项目语义落为会话/辩论配置）
    - `case_background`
    - `scenario_hint`
    - `max_rounds`
    - `新建会话` 操作
  - 中间主栏：对话区 + 输入区
    - 对话消息流（用户/Agent）
    - 文本输入、`发送`、`结束辩论`
  - 右侧分栏（固定）：报告区
    - `report` 为空时显示“等待报告生成”
    - `report` 非空时渲染完整报告内容
    - 同区展示 `report_source`、`report_quality_flags`

### 4.2 必备功能

- 新建会话：调用 `POST /sessions` 并保存 `session_id`
- 单轮发送：调用 `POST /sessions/{id}/turn`（`action=send`）
- 主动结束：调用 `POST /sessions/{id}/turn`（`action=end`）
- 页面恢复：支持 `GET /sessions/{id}` 回填状态

### 4.3 必备展示内容

- 聊天气泡主文本：`assistant_brief`
- 详情展开区：`assistant_detail`
- 结构化反驳区（卡片或分段）：
  - 数据源：`counterargument_structured`
  - 引用源：`counterargument_citations`
  - 质量标签：`counterargument_quality_flags`
- 右侧报告分栏（始终占位）：
  - `report == null`：显示空态占位（例如“对话结束后在此生成报告”）
  - `report != null`：渲染 `report` 全字段
  - 质量信息固定显示位：`report_source`、`report_quality_flags`

### 4.4 交互与状态控制

- 按 `end_reason_code` 控制可发送状态：
  - `IN_PROGRESS`：允许发送
  - `USER_ENDED` / `MAX_ROUNDS_REACHED`：禁用发送，只允许“新建会话”
- `send` 期间防重复提交（按钮 loading / disable）
- 请求失败后可重试，不丢失当前输入草稿

### 4.5 错误处理（必须实现）

- 统一处理 `ErrorResponse`：展示 `error.message`，保留 `trace_id`
- 至少对以下错误码做分支：
  - `INVALID_ARGUMENT`：输入提示
  - `SESSION_NOT_FOUND`：提示重建会话
  - `SESSION_ALREADY_ENDED`：禁用发送并提示已结束
  - `INTERNAL_ERROR`：通用错误 + 重试入口

### 4.6 调试与回归能力

- 提供开发态调试面板（可开关）：
  - 展示关键字段：`end_reason_code`、`retrieval_mode`、`knowledge_sufficiency`
  - 展示 `debug` 原始对象
- 可对照 Streamlit 节点观测面板做一致性回归
- 调试面板建议放在中间主栏底部抽屉，不占用左侧配置和右侧报告主区域

## 5. 给 coding agent 的交付检查清单

- 已按 `/api/v1` 契约封装接口层（含类型）。
- 已实现 `send/end` 单轮调用与状态回填。
- 已实现错误码分支处理（含 `trace_id` 透出）。
- 已实现报告区、结构化反驳区、结束状态禁用策略。
- 已实现开发态调试面板（字段 + debug）。
- 可用 Streamlit 节点观测面板对照字段语义做回归检查。
