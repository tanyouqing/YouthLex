# 青律前端接口契约

本文面向后续 `Next.js` 前端实现，描述当前后端已经固定好的接口、字段语义和推荐接入方式。

## 1. 接口总览

当前前端至少需要对接以下 3 个接口：

- `GET /health`
  - 用于服务可用性检查
- `POST /api/v1/triage/run`
  - 用户每发送一轮消息时调用
- `POST /api/v1/triage/stream`
  - 用户发送消息后按阶段接收流式事件
- `GET /api/v1/triage/session/{session_id}`
  - 页面刷新、回访或重新进入会话时拉取快照

当前契约有一个重要语义变化：

- 场景选择页属于前端本地预会话状态，选卡片本身不会立即调用后端
- 前端会先展示固定欢迎语“遇到维权困难了？跟我讲讲，我来帮你解决”
- 用户输入首条真实案情后，前端才发起 `run/stream` 请求
- 首轮请求可通过 `scenario_hint` 传入参考场景，后端会结合真实描述做软路由
- 一次 `run/stream` 调用不一定直接进入 `deliverables`
- 首轮和中间收集轮次通常会停在 `slot_filling`
- 只有用户明确回复“开始整理 / 没有更多 / 补不了了”等后，才会进入最终整理

## 2. 请求约定

### 2.1 `POST /api/v1/triage/run`

请求体：

```json
{
  "user_input": "老板拖欠我兼职工资，还把我拉黑了",
  "scenario_hint": "consumer"
}
```

字段说明：

- `user_input: string`
  - 必填，用户当前输入
- `scenario: "housing" | "labor" | "consumer" | "debt" | "ip_reputation" | "other" | null`
  - 可选
  - 显式强指定场景，兼容旧调用方
- `scenario_hint: "housing" | "labor" | "consumer" | "debt" | "ip_reputation" | "other" | null`
  - 可选
  - 仅建议用于“场景先选、首条真实输入后再启动”的首轮请求
  - 后端会结合 `user_input` 与 `scenario_hint` 做软路由
  - 若真实描述明显属于其他场景，后端可能覆盖该 hint
- `session_id: string | null`
  - 可选
  - 首轮不传时后端自动生成
  - 后续轮次必须复用同一个 `session_id`

### 2.2 `GET /api/v1/triage/session/{session_id}`

路径参数：

- `session_id: string`
  - 必填，会话唯一标识

返回 404 表示后端内存中不存在该会话。

### 2.3 `POST /api/v1/triage/stream`

请求体与 `POST /api/v1/triage/run` 完全一致：

```json
{
  "user_input": "老板拖欠我兼职工资，还把我拉黑了",
  "scenario_hint": "consumer"
}
```

响应类型：

```text
Content-Type: text/event-stream
```

说明：

- 当前流式接口采用 `SSE`
- 但因为需要提交 JSON 请求体，所以前端应使用 `fetch` 而不是浏览器原生 `EventSource`
- 推荐在 Next.js 客户端组件中使用 `fetch + ReadableStream + TextDecoder` 解析

## 3. 响应结构

`POST /api/v1/triage/run` 和 `GET /api/v1/triage/session/{session_id}` 返回同一套结构。

```json
{
  "session_id": "demo-session",
  "scenario": "labor",
  "scenario_label": "劳动与兼职纠纷",
  "assistant_message": "同学先别着急，我先帮你把当前情况接住。从你描述看，这件事已经有可主张的法律依据。接下来我只确认一项：事情大概发生在什么时候、什么地点？",
  "current_stage": "slot_filling",
  "assistant_turn": {
    "role": "assistant",
    "content": "同学先别着急，我先帮你把当前情况接住。从你描述看，这件事已经有可主张的法律依据。接下来我只确认一项：事情大概发生在什么时候、什么地点？",
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
      "content": "最终建议"
    }
  ],
  "progress": {
    "current_stage": "slot_filling",
    "completed_stages": [
      "empathy",
      "legal_grounding",
      "slot_filling"
    ],
    "remaining_stages": ["slot_filling", "action_plan", "deliverables"],
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
      "breach_fact": "拖欠工资",
      "existing_evidence": []
    },
    "action_steps": [],
    "demand_letter": "",
    "similar_cases": []
  }
}
```

当用户明确要求“开始整理”后，同一个 `session_id` 返回的响应才通常会进入 `current_stage = "deliverables"`，并填充完整交付物。

## 4. 字段语义

### 4.1 顶层字段

- `session_id`
  - 前端必须保存
  - 每次继续聊天时原样传回
- `scenario`
  - 机器可读场景枚举
  - 首轮若传入 `scenario_hint`，这里返回的是后端最终确认后的场景，可能与 hint 不同
- `scenario_label`
  - 前端可直接展示的中文场景名
- `assistant_message`
  - 当前轮助手主回复
  - 不再等价于“最终总结”；首轮和补证轮次也会返回真实引导话术
- `current_stage`
  - 当前轮结束时所在阶段
  - 常见取值：
    - `slot_filling`：仍在收集信息
    - `deliverables`：已进入最终整理

### 4.2 `assistant_turn`

- 表示当前轮新增的助手消息
- 推荐直接插入聊天区消息流

### 4.3 `conversation_history`

- 当前会话完整消息历史
- 用于页面刷新后恢复聊天区
- 当前角色只有：
  - `user`
  - `assistant`

### 4.4 `progress`

- `completed_stages`
  - 已完成阶段列表，固定顺序
- `remaining_stages`
  - 尚未完成阶段列表
- `next_stage`
  - 下一阶段；收集期通常会继续返回 `slot_filling`
- `collected_slots`
  - 已收集到的六要素槽位 key
- `missing_slots`
  - 缺失槽位 key
- `evidence_completion_ratio`
  - 证据链完成度，范围 `0.00` 到 `1.00`
- `evidence_complete`
  - 六要素是否已补齐
- `deliverables_ready`
  - 当前是否已可展示催告函和案例

槽位 key 固定为：

- `counterparty`
- `time_place`
- `amount`
- `agreement`
- `breach_fact`
- `existing_evidence`

### 4.5 `frontend`

这是给前端的直接展示提示，不是业务真相来源。

- `display_mode`
  - 建议前端展示模式
  - 当前可能取值：
    - `slot_collection`
    - `action_guidance`
    - `deliverables_ready`
- `primary_panel`
  - 建议优先展开的侧边栏面板
  - 当前可能取值：
    - `evidence_slots`
    - `action_steps`
    - `demand_letter`
- `input_placeholder`
  - 建议输入框占位提示
- `follow_up_questions`
  - 当前轮建议追问
  - 当前实现会收敛为 1 条，建议渲染成提示卡，不要点击即自动发送
- `suggested_actions`
  - 当前轮建议动作，适合渲染成 CTA

### 4.6 `sidebar`

- `evidence_slots`
  - 结构化证据槽位
- `action_steps`
  - 维权行动步骤
- `demand_letter`
  - Markdown 格式催告函
- `similar_cases`
  - 建议展示 1 到 2 条

## 5. 前端接入建议

推荐时序：

1. 用户在场景选择页先选一个参考场景，此时前端只切到工作台并展示欢迎语，不调用后端
2. 用户首条真实案情输入时，不传 `session_id`，也不要传示例 prompt
3. 首轮请求传 `scenario_hint`，如果需要普通模式，调用 `POST /api/v1/triage/run`
4. 如果需要流式体验，调用 `POST /api/v1/triage/stream`
5. 收到首个 `session` 事件后保存 `session_id`
6. 收到 `stage_completed` 事件时更新进度条和侧边栏
7. 收到 `complete` 事件时，以其中的完整 `response` 作为聊天区和页面状态的最终真相来源
8. 刷新页面时，调用 `GET /api/v1/triage/session/{session_id}` 恢复正式会话

## 6. 流式事件协议

### 6.1 事件类型

- `session`
  - 用于通知会话已建立
- `stage_started`
  - 某个阶段开始执行
- `stage_completed`
  - 某个阶段已完成，并附带当前快照
- `complete`
  - 整个流程结束，附带完整 `TriageResponse`
- `error`
  - 流式处理失败

典型事件顺序：

```text
首轮或中间收集轮：
session → stage_started(empathy) → stage_completed(empathy)
       → stage_started(legal_grounding) → stage_completed(legal_grounding)
       → stage_started(slot_filling) → stage_completed(slot_filling)
       → complete

明确进入整理的轮次：
session → stage_started(legal_grounding) → stage_completed(legal_grounding)
       → stage_started(action_plan) → stage_completed(action_plan)
       → stage_started(deliverables) → stage_completed(deliverables)
       → complete
```

### 6.2 `session` 事件

```text
event: session
data: {"session_id":"demo-session","scenario":"labor"}
```

### 6.3 `stage_started` 事件

```text
event: stage_started
data: {"stage":"legal_grounding","session_id":"demo-session"}
```

### 6.4 `stage_completed` 事件

```json
{
  "stage": "legal_grounding",
  "session_id": "demo-session",
  "assistant_turn": {
    "role": "assistant",
    "content": "我已经结合检索到的法规信息完成了初步法律定性。",
    "stage": "legal_grounding"
  },
  "progress": {
    "current_stage": "legal_grounding",
    "completed_stages": ["empathy", "legal_grounding"],
    "remaining_stages": ["slot_filling", "action_plan", "deliverables"],
    "next_stage": "slot_filling",
    "collected_slots": ["counterparty", "breach_fact"],
    "missing_slots": ["time_place", "amount", "agreement", "existing_evidence"],
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
    "suggested_actions": ["回答当前这一项", "整理对应证据后再补充"]
  },
  "sidebar": {
    "evidence_slots": {
      "counterparty": "老板",
      "time_place": null,
      "amount": null,
      "agreement": null,
      "breach_fact": "拖欠工资",
      "existing_evidence": []
    },
    "action_steps": [],
    "demand_letter": null,
    "similar_cases": []
  }
}
```

### 6.5 `complete` 事件

```text
event: complete
data: {"response": {...完整 TriageResponse...}}
```

### 6.6 `error` 事件

```text
event: error
data: {"message":"流式处理过程中发生异常，请改用同步接口重试，或重新发起一次会话。","session_id":"demo-session"}
```

## 7. Next.js 客户端解析建议

推荐解析方式：

1. `fetch("/api/v1/triage/stream", { method: "POST", body: JSON.stringify(...) })`
2. 从 `response.body.getReader()` 持续读取文本块
3. 以空行 `\n\n` 为分隔切块
4. 解析每个块里的 `event:` 和 `data:`
5. 根据事件名更新本地状态

建议状态更新规则：

- `session`
  - 保存 `session_id`
- `stage_started`
  - 更新当前运行阶段，展示 loading 提示
- `stage_completed`
  - 用 `progress/frontend/sidebar` 局部刷新页面即可；聊天区建议等 `complete` 事件统一落地
- `complete`
  - 用 `response` 覆盖当前整轮最终状态
- `error`
  - 停止 loading，提示用户重试

最小示例：

```ts
const response = await fetch("/api/v1/triage/stream", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    user_input,
    scenario_hint,
    session_id: sessionId,
  }),
});

const reader = response.body?.getReader();
const decoder = new TextDecoder("utf-8");
let buffer = "";

while (reader) {
  const { value, done } = await reader.read();
  if (done) break;
  buffer += decoder.decode(value, { stream: true });

  const chunks = buffer.split("\n\n");
  buffer = chunks.pop() ?? "";

  for (const chunk of chunks) {
    const event = chunk.match(/^event: (.+)$/m)?.[1];
    const dataText = chunk.match(/^data: (.+)$/m)?.[1];
    if (!event || !dataText) continue;
    const data = JSON.parse(dataText);
    // 根据 event 更新前端状态
  }
}
```

## 8. 空值与降级说明

前端必须接受以下情况：

- `sidebar.demand_letter` 为空字符串或 `null`
- `sidebar.similar_cases` 为空数组
- `frontend.follow_up_questions` 为空数组
- `progress.next_stage` 为 `null`
- 收集轮次的 `current_stage` 可能是 `slot_filling`
- 检索失败时，仍会返回 200，但内容可能偏通用

## 9. 当前不在本轮实现范围内

以下能力当前未纳入稳定契约：

- token 级模型输出流
- WebSocket 双向长连接
- 文件上传
- 图片证据 OCR
- 会话持久化数据库
- 用户鉴权
