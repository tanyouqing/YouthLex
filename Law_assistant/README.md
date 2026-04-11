# 青律 Legal Triage Agent

基于 `FastAPI + LangGraph` 的高校学生维权智能体后端骨架项目。

当前版本已接入 `MiniMax 2.5` 的实际大模型调用，并在图节点中接入了官方法律检索服务：

- 首轮会固定执行“安抚 → 初步法律定性 → 单项追问”，不会直接一次性出完整交付物
- 收集阶段每轮只追问 1 项高价值信息，但会自动吸收用户一轮里补充的多项事实和证据
- 用户明确回复“开始整理 / 没有更多 / 补不了了”等口令后，系统才会进入最终整理并生成交付物
- 前端可先传参考场景 `scenario_hint`，后端会结合首条真实案情做软路由，必要时覆盖 hint
- 若首轮使用 `scenario_hint` 建立会话，系统会把欢迎语“遇到维权困难了？跟我讲讲，我来帮你解决”写入正式历史
- 取证补槽已改成“规则优先 + LLM 标准化兜底”，短答店名、口语化金额、部分时间地点都会先被整理成可用格式
- 内部新增 `missing / usable / complete` 三档槽位状态；只要信息可用就会进入下一项，软缺口会写入最终总结
- `legal_grounding` 节点会先检索法规，再生成法律定性与法条依据摘要
- `deliverables` 节点会先检索类案，再生成催告函、维权步骤和最终总结
- 当用户未显式选择场景时，系统会先做 5+1 场景自动路由
- 检索前会做一层场景化 query 改写，以提升法规和类案命中率
- 系统会自动抽取“纠纷六要素”并更新 `evidence_slots`
- 相同 `session_id` 的连续请求会自动复用上轮状态，支持多轮补充事实
- 维权 SOP 已按纠纷场景做模板增强，输出更具体的先后步骤、平台和部门建议
- 催告函已升级为结构化模板生成，能够代入已知事实、证据和维权动作
- 相似案例会统一整理为“案情摘要 / 结果 / 维权启示”格式，更适合侧边栏展示
- 已增加统一日志记录，可观测场景路由、检索 query、节点耗时与降级原因
- MiniMax 与得理检索的超时、重试和日志级别已进入配置层
- 已固定前端对接响应结构，并补充会话快照接口与前端接入文档

当检索为空或检索失败时，系统会自动降级为谨慎版 LLM 响应，不会中断整条处理链。

## 项目特性

- 使用 `LangGraph` 预置 5 个阶段节点：
  - 情绪安抚与共情
  - 法条亮剑与定性
  - 证据链完善与填槽
  - 维权 SOP 指导
  - 核心交付物生成
- 使用 `FastAPI` 暴露健康检查与单轮运行接口
- 使用 `.env` 管理 MiniMax 2.5 的 OpenAI 兼容配置，并通过统一 LLM 服务封装发起真实调用
- 使用官方得理开放平台检索接口为关键节点提供法规和类案上下文
- 使用轻量场景路由和检索改写层提升首句识别与检索相关性
- 为前端预留统一的侧边栏结构：证据槽位、行动步骤、催告函、相似案例

## 当前对话流程

当前“维权小助手”已经改为引导式多轮模式：

1. 用户可先在前端选择一个参考场景，页面先展示欢迎语，不会立刻启动图流程。
2. 用户输入首条真实纠纷描述后，后端会结合真实案情和可选的 `scenario_hint` 确认最终场景。
3. 系统随后会先安抚情绪，再结合检索到的法规做初步定性，并只追问 1 个当前最关键的缺失信息。
4. 取证阶段会先用规则抽取，再在必要时用 LLM 把口语化表述整理成规范值，例如店名、约数金额、费用项或部分时间地点。
5. 在收集阶段，接口返回的 `current_stage` 通常停在 `slot_filling`，`follow_up_questions` 也只会保留 1 条。
6. 当用户明确表示“开始整理”“没有更多了”“补不了了”等时，系统才会生成最终总结、维权步骤、催告函和相似案例。
7. 如果仍有证据缺口或仅拿到“可用但不够完整”的信息，系统会把这些软缺口写进最终总结，但交付物结构本身不变。

## 目录结构

```text
.
├── app
│   ├── api/routes
│   ├── core
│   ├── graphs/legal_triage
│   ├── schemas
│   └── services
├── data
│   ├── cases
│   ├── laws
│   └── templates
├── tests
├── .env
├── .env.example
├── requirements.txt
└── README.md
```

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后可访问：

- 健康检查: `GET http://127.0.0.1:8000/health`
- 智能体接口: `POST http://127.0.0.1:8000/api/v1/triage/run`
- 流式接口: `POST http://127.0.0.1:8000/api/v1/triage/stream`
- 会话快照: `GET http://127.0.0.1:8000/api/v1/triage/session/{session_id}`

## 环境变量

项目默认从根目录 `.env` 读取配置：

- `OPENAI_BASE_URL`
- `OPENAI_API_KEY`
- `MINIMAX_MODEL`
- `DELILEGAL_BASE_URL`
- `DELILEGAL_APP_ID`
- `DELILEGAL_SECRET`

如需重新配置，可参考 `.env.example`。

## 得理开放平台测试

仓库已补充一套针对比赛官方接口的独立测试脚本与说明文档，用于验证：

- 类案检索 `POST /api/qa/v3/search/queryListCase`
- 法规检索 `POST /api/qa/v3/search/queryListLaw`
- 法规详情 `GET /api/qa/v3/search/lawInfo`

运行方式：

```powershell
.\.venv\Scripts\python.exe scripts\test_delilegal_api.py --guide-docx "D:\服创赛D06赛道帮助指引.docx"
```

或先配置环境变量后直接运行：

```powershell
.\.venv\Scripts\python.exe scripts\test_delilegal_api.py
```

脚本会把真实请求/响应样例写入 `docs/delilegal_api_samples/`，详细接入说明见 `docs/delilegal_api_guide.md`。

## 项目内如何调用法律检索服务

这一轮已经把官方接口整理成“低层客户端 + 高层知识库门面”两层：

- 低层客户端：`app/services/delilegal_client.py`
- 高层门面：`app/services/knowledge_base.py`

推荐业务代码直接调用高层门面，不要在节点里手写 `appid/secret`、请求头和 `lawId` 拼接逻辑。

最小示例：

```python
from app.services.knowledge_base import LegalKnowledgeBase

with LegalKnowledgeBase() as knowledge_base:
    legal_basis = knowledge_base.retrieve_legal_basis(
        "兼职工资被拖欠，学生可以主张哪些法律依据？",
        scenario="labor",
    )
    similar_cases = knowledge_base.retrieve_similar_cases(
        "房东无故不退押金，学生租客如何维权？",
        scenario="housing",
    )
```

两个推荐接入点：

- “法条亮剑与定性”节点调用 `retrieve_legal_basis(...)`
- “核心交付物生成”节点调用 `retrieve_similar_cases(...)`

如果需要看更细的接口设计、返回结构和异常处理建议，请直接查阅 `docs/delilegal_api_guide.md`。

## 接口说明

### `GET /health`

返回服务状态与当前模型名称。

### `POST /api/v1/triage/run`

用户每发送一轮消息调用一次；后端会返回本轮助手回复、完整会话历史、进度信息和侧边栏交付物。

说明：

- 一次调用不一定会走到 `deliverables`
- 首轮和大多数收集轮次会停在 `slot_filling`
- 只有显式进入整理时，`current_stage` 才会落到 `deliverables`

请求示例：

```json
{
  "user_input": "老板拖欠我兼职工资，还把我拉黑了",
  "scenario_hint": "labor"
}
```

字段约定：

- `scenario`
  - 显式强指定场景，兼容旧调用方
- `scenario_hint`
  - 首轮真实输入时的参考场景，后端会做软路由，必要时可覆盖
- `session_id`
  - 首轮不传，后续轮次复用后端返回的同一个会话 ID

响应示例：

```json
{
  "session_id": "demo-session",
  "scenario": "labor",
  "scenario_label": "劳动与兼职纠纷",
  "assistant_message": "同学先别着急，我先帮你把当前情况接住。从你描述看，这件事已经有劳动报酬主张依据。接下来我只确认一项：事情大概发生在什么时候、什么地点？",
  "current_stage": "slot_filling",
  "assistant_turn": {
    "role": "assistant",
    "content": "同学先别着急，我先帮你把当前情况接住。从你描述看，这件事已经有劳动报酬主张依据。接下来我只确认一项：事情大概发生在什么时候、什么地点？",
    "stage": "slot_filling"
  },
  "conversation_history": [
    {
      "role": "assistant",
      "content": "遇到维权困难了？跟我讲讲，我来帮你解决"
    },
    {
      "role": "user",
      "content": "老板拖欠我兼职工资，还把我拉黑了"
    },
    {
      "role": "assistant",
      "content": "这是当前轮的助手回复。"
    }
  ],
  "progress": {
    "current_stage": "slot_filling",
    "completed_stages": [
      "empathy",
      "legal_grounding",
      "slot_filling"
    ],
    "remaining_stages": [
      "slot_filling",
      "action_plan",
      "deliverables"
    ],
    "next_stage": "slot_filling",
    "collected_slots": [
      "counterparty",
      "breach_fact"
    ],
    "missing_slots": [
      "time_place",
      "amount",
      "agreement",
      "existing_evidence"
    ],
    "evidence_completion_ratio": 0.33,
    "evidence_complete": false,
    "deliverables_ready": false
  },
  "frontend": {
    "display_mode": "slot_collection",
    "primary_panel": "evidence_slots",
    "input_placeholder": "请补充事情发生的时间、地点，必要时可按时间顺序描述",
    "follow_up_questions": [
      "事情大概发生在什么时候、什么地点？如果有多次发生，也可以按时间顺序补充。"
    ],
    "suggested_actions": [
      "回答当前这一项",
      "整理对应证据后再补充"
    ]
  },
  "sidebar": {
    "evidence_slots": {
      "counterparty": "老板",
      "time_place": null,
      "amount": null,
      "agreement": null,
      "breach_fact": "老板拖欠我兼职工资，还把我拉黑了",
      "existing_evidence": []
    },
    "action_steps": [],
    "demand_letter": "",
    "similar_cases": []
  }
}
```

当用户后续明确回复“开始整理”后，同一个 `session_id` 会返回 `current_stage = "deliverables"` 的最终整理结果，届时 `sidebar.action_steps / demand_letter / similar_cases` 会被完整填充。

### `GET /api/v1/triage/session/{session_id}`

用于页面刷新后恢复聊天记录、进度和侧边栏快照。

不存在的 `session_id` 会返回：

```json
{
  "detail": "Session not found"
}
```

### `POST /api/v1/triage/stream`

用于 `Next.js` 前端按阶段接收流式事件。当前实现采用 `SSE`，但请求方法仍然是 `POST`，这样可以直接提交 `user_input/scenario/session_id`。

首轮若采用“先选场景、后输入真实案情”的前端流程，建议提交 `user_input + scenario_hint`，不要把场景卡片示例文案直接发送给后端。

返回头：

```text
Content-Type: text/event-stream
Cache-Control: no-cache
```

事件类型：

- `session`
  - 返回 `session_id` 和已确认场景
- `stage_started`
  - 某个阶段开始执行
- `stage_completed`
  - 某个阶段执行结束，并返回当前快照
- `complete`
  - 整轮完成，返回完整 `TriageResponse`
- `error`
  - 流式处理中断，前端应提示重试或改用同步接口

示例事件流：

```text
event: session
data: {"session_id":"demo-session","scenario":"labor"}

event: stage_started
data: {"stage":"empathy","session_id":"demo-session"}

event: stage_completed
data: {"stage":"empathy","session_id":"demo-session","assistant_turn":{"role":"assistant","content":"...","stage":"empathy"},"progress":{...},"frontend":{...},"sidebar":{...}}

event: complete
data: {"response":{"session_id":"demo-session","scenario":"labor","assistant_message":"...","current_stage":"deliverables", ...}}
```

## 前端对接文档

- 接口契约：`docs/frontend_api_contract.md`
- 前端实现清单：`docs/frontend_requirements.md`

## 当前实现边界

已完成：

- 服务入口与路由注册
- 配置读取与 MiniMax 模型工厂
- LangGraph 5 阶段编排
- MiniMax 实际调用链与失败兜底
- `legal_grounding` 节点法规检索接入
- `deliverables` 节点类案检索接入
- 场景自动路由
- 检索 query 改写
- 纠纷六要素自动抽取
- 基于 `session_id` 的多轮会话状态更新
- 场景化维权 SOP 生成
- 模板化催告函生成
- 结构化相似案例展示
- 显式检索异常分类与降级
- 节点耗时和检索 query 日志
- MiniMax / 得理超时与重试参数配置化
- API 请求/响应模型
- 前端友好响应结构与会话快照接口
- 面向 Next.js 的 SSE 阶段级流式接口
- 参考场景 `scenario_hint` 软路由与欢迎语持久化
- 基础测试

暂未实现：

- 会话持久化
- 法律文书模板渲染

## 测试

```powershell
pytest
```


启动：uvicorn app.main:app --reload
