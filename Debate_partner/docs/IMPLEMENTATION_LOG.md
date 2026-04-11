# Implementation Log

## 2026-04-09 - 阶段 12：FastAPI v1 接口落地

### 本次目标

1. 实现可联调的 `/api/v1` 后端接口  
2. 对齐现有 OpenAPI 契约与错误格式  
3. 保持 Streamlit 回归基线不变

### 已完成内容

- 新增 FastAPI API 层：
  - `GET /api/v1/health`
  - `POST /api/v1/sessions`
  - `GET /api/v1/sessions/{session_id}`
  - `POST /api/v1/sessions/{session_id}/turn`
- 新增内存会话存储：
  - 24h TTL
  - 全局锁 + 单会话锁，确保并发安全
- 新增统一错误处理：
  - `INVALID_ARGUMENT` / `SESSION_NOT_FOUND` / `SESSION_ALREADY_ENDED` / `INTERNAL_ERROR`
  - 统一返回 `ErrorResponse`（含 `trace_id`）
- Graph 编排接入：
  - `turn(send)` 空文本强校验返回 400
  - 已结束会话再次 `send` 返回 409
- 新增测试：
  - `tests/test_session_store.py`
  - `tests/test_api.py`（环境无 fastapi 时自动 skip）
- 文档同步：
  - README、API_V1、OpenAPI、FRONTEND_AGENT_GUIDE、PROJECT_CODE_GUIDE
## 2026-04-09 - 阶段 11：Streamlit 节点观测与文档对齐

### 本次目标

1. 让 Streamlit 页面可直接验证完善后的图结构效果  
2. 核验并更新文档与代码一致性

### 已完成内容

- `streamlit_app.py` 新增“节点观测（测试用）”面板：
  - 节点链路状态表（init 到 report）
  - 当前轮关键字段（含 `end_reason_code/report_source`）
  - 结构化反驳与引用映射
  - `debug` 信息
  - 最新一轮历史快照展示
- `README.md`、`PROJECT_CODE_GUIDE.md` 更新：
  - 同步结束策略、结构化快照、报告可观测字段
  - 明确 Streamlit 新增节点观测调试能力

## 2026-04-09 - 阶段 10：三节点正式化与结束策略收敛

### 本次目标

1. 正式化 `judge_continue_or_end` / `ask_next_challenge` / `generate_debate_report`  
2. 收敛结束策略为“仅显式结束”  
3. 增强报告可观测性与稳定兜底

### 已完成内容

- `judge_continue_or_end`：
  - 仅保留两类结束条件：`ui_action=end`、达到 `max_rounds`
  - 新增 `end_reason_code`（`IN_PROGRESS/USER_ENDED/MAX_ROUNDS_REACHED`）
  - 新增 `debug.judge` 命中信息
- `ask_next_challenge`：
  - 历史沉淀新增结构化快照：
    - `counterargument_structured_snapshot`
    - `counterargument_citations_snapshot`
    - `counterargument_quality_flags`
  - 使用防御性拷贝避免跨轮污染
- `generate_debate_report`：
  - 升级为“LLM输出 + 校验修复 + fallback”模式
  - 新增 `report_source`、`report_quality_flags`、`debug.report`
  - 修复规则包括：列表标准化、字段截断、分数夹紧到 0~100
- 文档与契约同步：
  - `docs/API_V1.md`、`docs/openapi/debate-agent-v1.yaml` 新增结束码与报告可观测字段
- 测试新增与回归：
  - 覆盖关键词不提前结束、显式结束码、历史快照防污染、报告修复与 fallback
## 2026-04-09 - 阶段 7：新增 Next.js 对接 API 文档契约（v1）

### 本次目标

1. 增加面向前后端分离架构的 API 文档  
2. 同时提供人读版与机器可读版契约  
3. 明确迁移期 Streamlit 作为行为回归基线

### 已完成内容

- 新增人读版 API 文档：`docs/API_V1.md`
  - 说明单轮语义（每次 turn 只处理一次动作）
  - 定义 `send` / `end` 行为及 `report` 出现条件
  - 提供统一错误模型 `ErrorResponse` 与前端处理建议
  - 提供 `send`、`end`、错误响应示例
- 新增 OpenAPI 契约：`docs/openapi/debate-agent-v1.yaml`
  - 基路径：`/api/v1`
  - 接口：`POST /sessions`、`POST /sessions/{session_id}/turn`、`GET /sessions/{session_id}`、`GET /health`
  - 模型：`TurnRequest`、`SessionStateSummary`、`DebateReport`、`ErrorResponse`
- 更新 `README.md`
  - 增加 API 文档入口
  - 增加接口清单与联调建议
  - 更新目录结构

### 设计说明

- 当前只冻结文档契约，不提前实现 FastAPI，避免边开发边改接口导致前端反复返工。
- `ErrorResponse` 统一后，前端可基于 `error.code` 做稳定分支。
- `SessionStateSummary` 字段与现有 `DebateState` 关键子集对齐，不引入未实现能力。
## 2026-04-07 - 阶段 0：项目骨架与说明文档

### 本次目标

根据需求，仅完成以下两项：

1. 设计项目目录结构
2. 编写 README 的项目说明部分

### 已完成内容

- 创建目录骨架：`app/`、`knowledge/`、`docs/`、`tests/`、`scripts/`
- 在目录中创建占位文件（`.gitkeep`），确保结构可见、可提交
- 新建 `README.md`，补充：
  - 项目背景与模块定位
  - MVP 当前范围
  - 法律与合规说明（Demo 不构成法律意见）
  - 后续技术方向
  - 建议目录结构树
  - 当前进度清单

### 设计理由

- 采用 `app/` + `knowledge/` 分层，便于将“流程逻辑”与“数据资产”解耦。
- `app/graph/nodes` 和 `app/graph/schemas` 拆分，有利于 LangGraph 节点扩展与 State 演进。
- `app/services` 单独承载模型与检索适配，方便未来替换供应商或接入外部 RAG。
- `knowledge/` 按知识类型分目录，和后续法规/案例/争点/模板的版本化管理一致。
- 先做文档和骨架，能让团队在编码前对边界、命名与职责快速达成一致。

### 未做事项（按要求暂停）

- 未实现 LangGraph 状态与节点
- 未生成知识库示例数据
- 未接入任何模型或运行入口

> 备注：以上内容仅为工程实现记录，不构成法律意见。

## 2026-04-07 - 阶段 1：知识库 Schema 与示例数据

### 本次目标

1. 设计知识库 schema
2. 生成示例知识文件

### 已完成内容

- 新增 schema 文档与主 schema 文件：
  - `knowledge/schema/README.md`
  - `knowledge/schema/knowledge_record.schema.json`
- 采用统一记录结构（envelope）：
  - 顶层通用元数据：`record_id`、`record_type`、`scenario_tags`、`source` 等
  - 类型化内容：`content` 按 `record_type` 约束
- 生成四类示例知识（JSONL）：
  - `knowledge/statutes/statutes.demo.jsonl`（8 条）
  - `knowledge/cases/cases.demo.jsonl`（6 条）
  - `knowledge/issue_rules/issue_rules.demo.jsonl`（6 条）
  - `knowledge/rebuttal_templates/rebuttal_templates.demo.jsonl`（8 条）
- 场景覆盖：
  - 租房纠纷（`rental_dispute`）
  - 家教/兼职欠薪（`part_time_wage`）
- 完成可读性与可运行性处理：
  - 统一为 UTF-8 无 BOM
  - JSONL 行级解析通过

### 设计理由

- `JSONL + 统一信封结构`：便于本地轻检索、后续向量化、以及多类型混合召回。
- `record_type` 条件约束：LangGraph 节点可按类型路由，降低 prompt 拼装复杂度。
- `scenario_tags` 与 `linked_*`：支持“先按场景筛，再按关联扩展”的检索策略。
- `quality_level/source`：为 Demo 与生产数据分级，避免误把示例当正式法源。

### 风险提示

- 当前法律条文和案例均为 Demo 级示例（含示意化表达与 mock case）。
- 不构成正式法律意见，后续应替换为可核验的正式法源与裁判文书数据。

## 2026-04-07 - 阶段 2：LangGraph 骨架可运行版

### 本次目标

按需求先实现最小可运行流程：

1. 定义 state
2. 定义节点函数签名和基础逻辑
3. 构建图
4. 用占位逻辑跑通流程

### 已完成内容

- 新增 State 定义：
  - `app/graph/schemas/state.py`
- 新增知识访问与轻检索：
  - `app/knowledge/repository.py`
- 新增节点函数（占位逻辑）：
  - `app/graph/nodes/debate_nodes.py`
- 新增图构建逻辑：
  - `app/graph/builder.py`
- 新增 demo 入口：
  - `main.py`
- 新增依赖清单：
  - `requirements.txt`
- 更新 README，完整记录当前实现并详细解释图与节点。

### 验证结果

- 运行 `python main.py` 已可完成多轮辩论与结束收敛，并产出结构化报告。
- 发现并修复 `GraphRecursionError`：
  - 原因：节点数量较多，超过 LangGraph 默认递归步数 25。
  - 修复：在 `main.py` invoke 时设置 `recursion_limit=100`。

### 说明

- 当前阶段故意保持占位实现，优先保证图能跑。
- 检索、解析、反驳与评分均为可替换模块，下一步可平滑升级。

## 2026-04-07 - 阶段 3：LLM 节点替换（MiniMax）

### 本次目标

将原本“需要 LLM 但仍为规则占位”的节点替换为 LLM 版本，并保持图可运行。

### 已完成内容

- 新增 MiniMax OpenAI 兼容客户端：
  - `app/services/llm_client.py`
- 新增 Prompt 模块：
  - `app/prompts/debate_prompts.py`
- 替换节点实现（LLM 主逻辑）：
  - `parse_user_claim`
  - `identify_attack_target`
  - `build_counterargument`
  - `generate_debate_report`
  - 文件：`app/graph/nodes/debate_nodes.py`
- 保留并复用：
  - `retrieve_knowledge` 本地轻检索逻辑（JSONL + 关键词）
  - `judge_continue_or_end` 流程收敛规则
- 更新依赖：
  - `requirements.txt` 新增 `openai>=1.51.0`
- 更新 README：补充 MiniMax 环境配置、节点 LLM 化说明、降级策略。

### 设计说明

- 模型默认使用 `MiniMax-M2.5`，可通过 `MINIMAX_MODEL` 环境变量覆盖。
- API key 与 base URL 只从环境变量读取，不写入代码文件。
- LLM 调用失败时采用节点级降级结果，避免图因单点失败中断。

### 风险提示

- 若未配置 `OPENAI_API_KEY`，会进入降级模式，输出质量明显低于 LLM 正常模式。
- 示例知识仍为 Demo 数据，不构成正式法律意见。

## 2026-04-07 - 阶段 4：改为 `.env` 读取 API 配置

### 本次目标

将运行配置改为通过项目根目录 `.env` 读取，而不是手动设置 shell 环境变量。

### 已完成内容

- `app/services/llm_client.py` 增加 `.env` 自动加载（`python-dotenv`）。
- 新增 `.env.example` 模板文件。
- 新增 `.env` 占位文件（空 key，避免硬编码密钥）。
- 新增 `.gitignore`，忽略 `.env`。
- `requirements.txt` 增加 `python-dotenv>=1.0.1`。
- README 更新为 `.env` 配置流程。

## 2026-04-07 - 阶段 5：项目代码说明文档

### 本次目标

新增一份给开发者使用的项目代码说明文档，详细解释：

1. 项目各文件职责
2. LangGraph 图结构
3. State 定义
4. 节点定义与输入输出

### 已完成内容

- 新增文档：
  - `docs/PROJECT_CODE_GUIDE.md`
- 文档包含：
  - 架构分层说明
  - 逐文件职责总览
  - LangGraph 流程与条件边解释
  - `DebateState` 字段级解读（含子结构）
  - 各节点的输入、输出、降级逻辑、扩展建议
  - 运行时数据流与调试建议

## 2026-04-08 - 阶段 6：前端接入与单轮交互重构

### 本次目标

1. 将输入源从 `pending_user_inputs` 改为前端输入框/CLI 实时输入  
2. 将 LangGraph 改为“单轮 invoke 闭环”  
3. 新增 Streamlit 可视化页面（含详情展开和底部报告区）  
4. 更新 README 与 docs，完整说明新版图结构和状态字段

### 已完成内容

- 状态重构：
  - 删除 `pending_user_inputs`
  - 新增 `ui_action`（`send` / `end`）
  - 增加 `assistant_brief`、`assistant_detail` 字段（并落到历史记录）
  - 文件：`app/graph/schemas/state.py`

- 图路由重构（单轮闭环）：
  - `fetch_user_input` 后按 `ui_action` 条件分流：
    - `end -> generate_debate_report`
    - `send -> parse_user_claim`
  - `ask_next_challenge` 后直接 `END`（不再回环到 `fetch_user_input`）
  - 文件：`app/graph/builder.py`

- 节点能力增强：
  - `fetch_user_input` 改为规范化当前输入与动作
  - 新增回复分段器，生成简版与详情双轨回复
  - `ask_next_challenge` 只把简版放主回复，完整内容保存在详情字段
  - `generate_debate_report` 不再在聊天内容内展开报告正文
  - 文件：`app/graph/nodes/debate_nodes.py`

- 前端新增：
  - 新建 `streamlit_app.py`
  - 顶部预设（背景/场景/轮次）
  - 聊天区中每条 Agent 消息支持 `详情` 按钮展开完整分段
  - 页面底部独立“辩论总结报告”区域

- CLI 入口改造：
  - `main.py` 改为逐轮输入模式，支持 `/end` 结束并生成报告

- 测试新增：
  - `tests/test_reply_views.py`
  - `tests/test_graph_routes.py`

- 依赖与文档更新：
  - `requirements.txt` 新增 `streamlit`
  - `README.md` 更新运行方式和迁移说明
  - `docs/PROJECT_CODE_GUIDE.md` 更新为新版图结构与状态说明

### 兼容性说明

- 旧版批处理字段 `pending_user_inputs` 已移除。  
- 需要调用方在每轮 invoke 时传入：
  - `current_user_input`
  - `ui_action`

### 验证项（本阶段）

- 单轮 send 可产出“核心反驳 + 进一步追问”简版回复。  
- 每轮都保留完整详情文本（用于前端展开查看）。  
- end 动作可直接产出结构化报告，并在前端底部展示。  



