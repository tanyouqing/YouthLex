# Frontend Coding Agent Prompt — 法律辩论陪练 (Debate Partner) Next.js 前端

> **目标读者**：负责前端实现的 Coding Agent（Cursor / Copilot Workspace / 其他 AI 编码助手）
> **产出**：一个可运行的 Next.js 前端项目，与后端 FastAPI `/api/v1` 实时联调
> **约束**：本 Prompt 自包含，Coding Agent 无需阅读后端源码

---

## 0. 项目背景（必读）

这是一个"法律辩论陪练 Agent"项目，面向中国大陆大学生维权场景。用户扮演 **原告/维权方**，Agent 扮演 **反方/质疑者**。  
后端由 LangGraph + MiniMax LLM 驱动，已完成完整的攻防链路（解析主张→定位攻击点→检索知识→生成反驳→判断终止→生成报告）。  
**后端 FastAPI v1 已完整实现，可直接联调。**

### 核心语义：单轮交互
- 每次 API 调用只处理 **一次** 用户动作（`send` 或 `end`），然后返回完整的当前状态。
- 前端不需要维护复杂的状态机，只需：调用 API → 用响应数据刷新 UI。
- 会话结束由响应中的 `should_end: true` 确认，**不** 由前端本地判定。
- `send` 文本中即使包含"结束"等词，也不会触发提前结束；结束 **仅** 由 `action=end` 或达到 `max_rounds` 触发。

### 后端启动方式（前端开发前先确认可用）

```bash
# 在项目根目录 d:\tencentKAIWU\Debate_partner 执行
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
```

后端已配置 `CORSMiddleware`（`allow_origins=["*"]`），前端无需额外处理跨域。

---

## 1. 技术栈要求

| 层 | 技术 | 说明 |
| --- | --- | --- |
| 框架 | **Next.js 14+** (App Router) | 使用 `npx -y create-next-app@latest ./` 初始化 |
| 语言 | **TypeScript** | 全项目 strict 模式 |
| 样式 | **CSS Modules** 或 **Vanilla CSS** | 不使用 Tailwind，要求手写精致样式 |
| 状态管理 | **React Context + useReducer** | 或 Zustand 等轻量方案（不引入 Redux） |
| HTTP | **fetch API** 或 **axios** | 封装为统一 API 层 |
| 字体 | **Google Fonts**（推荐 Noto Sans SC + 一款有个性的衬线/等宽字体） | 中文场景必须选支持中文的字体 |
| 主题 | **浅色 + 深色双主题** | 提供一键切换，默认跟随系统偏好 |

**项目初始化位置**：`d:\tencentKAIWU\Debate_partner\frontend\`（在项目根目录下新建 `frontend` 子目录）

---

## 2. 页面布局（三栏结构 · 硬性要求）

```
┌─────────────────────────────────────────────────────────────────────┐
│  Debate Partner 法律辩论陪练        [轮次: 2/5]    [🌙/☀ 主题切换]   │
├──────────┬──────────────────────────────────┬───────────────────────┤
│          │                                  │                       │
│  左侧栏   │         中间主栏                  │     右侧栏             │
│ (280px   │     (flex: 1, 弹性宽度)            │   (360px 固定)        │
│  固定)    │                                  │                       │
│          │  ┌──────────────────────────┐     │                       │
│ 会话配置  │  │     消息流区域             │     │   辩论报告区            │
│          │  │  (滚动 · 自动到底)          │     │                       │
│ ─────── │  │                          │     │  report==null:         │
│ case_bg  │  │  用户气泡(右) / Agent(左)  │     │   空态占位              │
│ scenario │  │                          │     │                       │
│ max_rnds │  │                          │     │  report!=null:         │
│          │  └──────────────────────────┘     │   渲染完整报告           │
│ [新建会话]│  ┌──────────────────────────┐     │   + report_source      │
│          │  │ 输入区: textarea + 按钮   │     │   + quality_flags      │
│          │  │ [发送]  [结束辩论]         │     │                       │
│          │  └──────────────────────────┘     │                       │
│          │  ┌──────────────────────────┐     │                       │
│          │  │ 调试面板 (可折叠抽屉)     │     │                       │
│          │  └──────────────────────────┘     │                       │
├──────────┴──────────────────────────────────┴───────────────────────┤
│                         底部状态栏（可选）                            │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.1 左侧栏 — 会话配置区

固定宽度 `~280px`，背景与主区域分层。

**配置字段**：
- `case_background`：多行文本域（`<textarea>`），默认值："学生租房退租后，房东拒绝返还押金并主张维修费用。"
- `scenario_hint`：下拉选择，固定选项（值→中文标签）：
  - `rental_dispute` → 租房纠纷
  - `part_time_wage` → 兼职薪酬
  - `campus_loan` → 校园贷
  - `training_refund` → 培训退费
  - `student_rights` → 学生权益
- `max_rounds`：数字输入，范围 `1~20`，默认 `5`
- **[新建会话]** 按钮：调用 `POST /api/v1/sessions` 并重置所有状态

**交互逻辑**：
- 会话进行中（`end_reason_code === "IN_PROGRESS"` 且 `round_index > 0`）时，配置字段置灰不可编辑
- 新建会话时重置所有对话消息与报告

### 2.2 中间主栏 — 对话区

弹性宽度，占据剩余空间。

#### 消息流
- **用户消息**：靠右对齐，蓝色调气泡
- **Agent 消息**：靠左对齐，中性色气泡
  - 气泡内显示 `assistant_brief` 文本
  - 气泡 **右上角** 有"详情"按钮
  - 点击"详情"展开一个抽屉/面板，显示 `assistant_detail` 完整分段内容
  - 详情面板内还应渲染 **结构化反驳卡片**（见 §2.4）

#### 输入区
- 多行文本输入（`<textarea>`）
- **[发送]** 按钮：`POST .../turn { action: "send", user_text: "..." }`
- **[结束辩论]** 按钮：`POST .../turn { action: "end", user_text: "" }`
- 会话结束后（`should_end === true`）：禁用发送和结束按钮，仅允许左侧"新建会话"

#### 调试面板（底部可折叠抽屉）
- 默认收起，有"🔧 调试面板"按钮可展开
- 展示字段：`end_reason_code`、`retrieval_mode`、`knowledge_sufficiency`、`attack_target_category`、`attack_target_source`
- 展示 `debug` 原始 JSON 对象（可折叠）
- 仅在开发态（`NODE_ENV=development`）默认可见，生产态隐藏。或提供全局开关。

### 2.3 右侧栏 — 报告区

固定宽度 `~360px`。

**状态一：`report === null`**
- 显示空态占位：图标 + 文字"对话结束后将在此生成辩论报告"
- 底部固定位展示 `report_source` 和 `report_quality_flags`（此时为 `null` / `[]`）

**状态二：`report !== null`**
- 渲染 `DebateReport` 全字段（见 §3.3 数据模型）：
  - 背景摘要 (`debate_background`)
  - 综合评分 (`overall_score`: 0~100，推荐用环形进度或大字展示)
  - 用户主张摘要列表 (`user_claim_summary`)
  - 反方核心反驳点列表 (`defendant_rebuttal_points`)
  - 用户优势列表 (`user_strengths`)
  - 用户漏洞列表 (`user_weaknesses`)
  - 证据改进建议列表 (`evidence_improvement_suggestions`)
  - 法律论证建议列表 (`legal_argument_suggestions`)
  - 结束原因 (`end_reason`)
- 顶部固定位展示 `report_source`（标签：`llm` / `fallback`）
- 底部固定位展示 `report_quality_flags`（质量标签列表）

### 2.4 结构化反驳卡片（Agent 详情展开后内容）

当用户点击 Agent 气泡的"详情"按钮展开后，除了 `assistant_detail` 全文外，还需渲染结构化反驳区：

**数据源**：`counterargument_structured` 对象，含以下段落：

| 键名 | 中文标题 | 说明 |
| --- | --- | --- |
| `claim_summary` | 主张概括 | Agent 对用户主张的理解概括 |
| `core_rebuttal` | 核心反驳 | 反方最核心的反驳论点 |
| `legal_basis` | 法律依据 | 援引的法条与适用分析 |
| `case_strategy` | 案例策略 | 类案参考与策略建议 |
| `evidence_challenge` | 证据质疑 | 对用户证据链的挑战 |
| `logic_challenge` | 逻辑质疑 | 对用户推理逻辑的挑战 |
| `support_gap_notes` | 补强缺口 | 知识不足时的临时补强备注（数组） |

**展示方式**：按段落渲染为卡片或分段组件，每段标题 + 内容。

**引用标注**：`counterargument_citations` 对象的键与 `counterargument_structured` 一一对应，值为 `record_id[]`。在每段卡片底部以角标/标签形式展示引用 ID（如 `[CASE_CN_0001]`、`[STATUTE_CN_0001]`）。

**质量标签**：`counterargument_quality_flags` 为字符串数组，非空时在卡片区域顶部展示为警告标签。

---

## 3. API 契约（完整定义 · 后端已实现可直接联调）

### 3.0 基础信息

```
BASE_URL = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000"
API_PREFIX = "/api/v1"
```

后端已配置 CORS `allow_origins=["*"]`，前端直连即可。

### 3.1 `GET /api/v1/health` — 服务探活

**用途**：前端首屏加载时调用，检测后端可达性。

**响应 200**：
```json
{
  "status": "ok",
  "service": "debate-agent",
  "version": "v1",
  "timestamp": "2026-04-09T10:20:00+08:00"
}
```

### 3.2 `POST /api/v1/sessions` — 创建会话

**请求体**（可为空 `{}`，所有字段有默认值）：
```json
{
  "case_background": "学生租房退租后，房东拒绝返还押金并主张维修费用。",
  "scenario_hint": "rental_dispute",
  "max_rounds": 5
}
```

**字段约束**（后端 Pydantic 校验，前端应提前校验避免 400）：
- `case_background`: string, `max_length=4000`
- `scenario_hint`: string, `max_length=128`
- `max_rounds`: integer, `1 ≤ x ≤ 20`, 默认 `5`

**响应 201**：
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
    "attack_target_category": null,
    "attack_target_reason": "",
    "attack_target_source": null,
    "retrieval_mode": null,
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

### 3.3 `POST /api/v1/sessions/{session_id}/turn` — 单轮动作

#### action=send（发送用户消息）

**请求**：
```json
{
  "action": "send",
  "user_text": "我主张房东应退还押金。"
}
```

**字段约束**：
- `action`: `"send" | "end"`（必填）
- `user_text`: string, `max_length=4000`（`send` 时不可为空，`end` 时可为空）

**响应 200**：
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
    "assistant_brief": "【核心反驳】现有证据不足以支持你的结论。\n【进一步追问】请补充入住与退租时的对比证据。",
    "assistant_detail": "【主张概括】...\n【反方核心反驳】...\n【法律依据】...\n【进一步追问】...",
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

#### action=end（结束辩论）

**请求**：
```json
{
  "action": "end",
  "user_text": ""
}
```

**响应 200** — `should_end: true`，`report` 非空：
```json
{
  "session": {
    "session_id": "session_01HXYZ...",
    "round_index": 1,
    "ui_action": "end",
    "should_end": true,
    "end_reason": "用户点击结束辩论",
    "end_reason_code": "USER_ENDED",
    "assistant_brief": "【核心反驳】本轮不再追加新的攻防观点，辩论已结束。\n【进一步追问】请查看右侧的"辩论总结报告"区域。",
    "assistant_detail": "【核心反驳】...\n【进一步追问】...\n【系统说明】结束原因：用户点击结束辩论；报告生成方式：标准模式。",
    "report_source": "llm",
    "report_quality_flags": [],
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

> 注：`end` 响应中省略了与 `send` 重复的字段以节省篇幅，实际响应包含 `SessionStateSummary` 全部字段。

### 3.4 `GET /api/v1/sessions/{session_id}` — 查询会话状态

**用途**：页面刷新后恢复状态。响应结构与 `turn` 相同。

**响应 200**：`SessionEnvelope`（同上结构）

### 3.5 错误响应（统一格式 · 所有 4xx/5xx）

```json
{
  "error": {
    "code": "INVALID_ARGUMENT",
    "message": "send action requires non-empty user_text",
    "details": { "field": "user_text" }
  },
  "trace_id": "trace_01abc2def345"
}
```

**后端已实现的错误码及对应 HTTP Status**：

| 错误码 | HTTP Status | 触发场景 | 前端处理 |
| --- | --- | --- | --- |
| `INVALID_ARGUMENT` | 400 | `action` 非法、`max_rounds` 越界、`send` 时 `user_text` 为空、请求体校验失败 | 输入区下方提示错误信息，保留草稿 |
| `SESSION_NOT_FOUND` | 404 | `session_id` 不存在或已过期（TTL 24h） | 弹窗"会话已失效"，引导新建会话 |
| `SESSION_ALREADY_ENDED` | 409 | 会话已结束仍尝试 `send` | 禁用发送，toast 提示已结束 |
| `INTERNAL_ERROR` | 500 | 服务端未预期异常 | 通用错误 + 重试按钮 + 展示 `trace_id` |

---

## 4. TypeScript 类型定义（供 API 层使用）

在 `frontend/src/types/api.ts` 中定义（这些类型严格对应后端 Pydantic Models）：

```typescript
// ─── 枚举 / 字面量 ─────────────────────────────────

export type TurnAction = "send" | "end";
export type EndReasonCode = "IN_PROGRESS" | "USER_ENDED" | "MAX_ROUNDS_REACHED";
export type AttackTargetCategory =
  | "法律依据不足"
  | "证据链薄弱"
  | "因果链不完整"
  | "损失计算不充分"
  | "规则适用错误"
  | "程序或主体适格瑕疵"
  | "论点信息不足";
export type AttackTargetSource = "llm" | "fallback" | "reranked";
export type RetrievalMode = "vector" | "keyword_fallback";
export type ReportSource = "llm" | "fallback";

export const SCENARIO_OPTIONS = [
  { value: "rental_dispute", label: "租房纠纷" },
  { value: "part_time_wage", label: "兼职薪酬" },
  { value: "campus_loan", label: "校园贷" },
  { value: "training_refund", label: "培训退费" },
  { value: "student_rights", label: "学生权益" },
] as const;

// ─── 请求 ─────────────────────────────────────────

export interface CreateSessionRequest {
  case_background?: string;   // max 4000 chars
  scenario_hint?: string;     // max 128 chars
  max_rounds?: number;        // 1~20, default 5
}

export interface TurnRequest {
  action: TurnAction;
  user_text?: string;         // max 4000 chars; send 时必填非空, end 时可空
}

// ─── 响应：核心模型 ───────────────────────────────

export interface CounterargumentStructured {
  claim_summary?: string;
  core_rebuttal?: string;
  legal_basis?: string;
  case_strategy?: string;
  evidence_challenge?: string;
  logic_challenge?: string;
  support_gap_notes?: string[];
}

export interface CounterargumentCitations {
  claim_summary?: string[];
  core_rebuttal?: string[];
  legal_basis?: string[];
  case_strategy?: string[];
  evidence_challenge?: string[];
  logic_challenge?: string[];
}

export interface DebateReport {
  debate_background: string;
  user_claim_summary: string[];
  defendant_rebuttal_points: string[];
  user_strengths: string[];
  user_weaknesses: string[];
  evidence_improvement_suggestions: string[];
  legal_argument_suggestions: string[];
  overall_score: number;        // 0~100
  end_reason: string;
}

export interface SessionStateSummary {
  session_id: string;
  case_background: string;
  scenario_hint: string;
  max_rounds: number;
  round_index: number;
  ui_action: TurnAction;
  should_end: boolean;
  end_reason: string;
  end_reason_code: EndReasonCode;
  assistant_brief: string;
  assistant_detail: string;
  attack_target: string;
  attack_target_category: AttackTargetCategory | string | null;
  attack_target_reason: string;
  attack_target_source: AttackTargetSource | null;
  retrieval_mode: RetrievalMode | null;
  knowledge_sufficiency: boolean;
  knowledge_missing_aspects: string[];
  counterargument_structured: CounterargumentStructured;
  counterargument_citations: CounterargumentCitations;
  counterargument_quality_flags: string[];
  report_source: ReportSource | null;
  report_quality_flags: string[];
  history_count: number;
  updated_at: string;           // ISO 8601
  report: DebateReport | null;
}

export interface SessionEnvelope {
  session: SessionStateSummary;
}

// ─── 响应：错误 ───────────────────────────────────

export interface ErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ErrorResponse {
  error: ErrorBody;
  trace_id: string;
}

// ─── 响应：健康检查 ───────────────────────────────

export interface HealthResponse {
  status: "ok";
  service: string;
  version: string;
  timestamp: string;
}
```

---

## 5. 推荐组件层级与文件结构

```
frontend/
├── .env.local                  # NEXT_PUBLIC_API_BASE=http://localhost:8000
├── src/
│   ├── app/
│   │   ├── layout.tsx              # 根布局（引入字体、全局样式、ThemeProvider）
│   │   ├── page.tsx                # 首页（组装三栏）
│   │   └── globals.css             # 全局样式变量 + Reset + 主题变量
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Sidebar.tsx             # 左侧配置栏
│   │   │   ├── ChatPanel.tsx           # 中间主栏容器
│   │   │   ├── ReportPanel.tsx         # 右侧报告栏
│   │   │   └── Header.tsx              # 顶部栏（标题 + 轮次 + 主题切换）
│   │   ├── chat/
│   │   │   ├── MessageList.tsx         # 消息流容器（自动滚动到底）
│   │   │   ├── UserBubble.tsx          # 用户消息气泡
│   │   │   ├── AgentBubble.tsx         # Agent 消息气泡（含"详情"按钮）
│   │   │   ├── AgentDetailDrawer.tsx   # 详情展开区（assistant_detail + 结构化反驳）
│   │   │   ├── CounterargumentCard.tsx # 单段结构化反驳卡片
│   │   │   └── ChatInput.tsx           # 文本输入 + 发送/结束按钮
│   │   ├── report/
│   │   │   ├── ReportEmpty.tsx         # 报告空态占位
│   │   │   ├── ReportContent.tsx       # 报告正文渲染
│   │   │   └── ScoreBadge.tsx          # 评分展示组件（环形进度）
│   │   ├── debug/
│   │   │   └── DebugDrawer.tsx         # 调试面板（可折叠）
│   │   ├── theme/
│   │   │   └── ThemeToggle.tsx         # 主题切换按钮
│   │   └── common/
│   │       ├── ErrorToast.tsx          # 错误提示
│   │       └── LoadingIndicator.tsx    # typing indicator / 加载动画
│   ├── context/
│   │   ├── DebateContext.tsx        # 全局状态管理（session + messages + error）
│   │   └── ThemeContext.tsx         # 主题状态管理
│   ├── services/
│   │   └── api.ts                  # API 封装层（统一错误处理）
│   ├── types/
│   │   └── api.ts                  # 上文定义的 TypeScript 类型
│   ├── hooks/
│   │   ├── useDebate.ts            # 封装 send/end/createSession 逻辑
│   │   └── useAutoScroll.ts        # 消息列表自动滚动
│   └── styles/
│       ├── variables.css           # CSS 变量：颜色、间距、字体
│       ├── sidebar.module.css
│       ├── chat.module.css
│       ├── report.module.css
│       └── debug.module.css
```

---

## 6. 状态管理设计

### 6.1 全局状态

```typescript
interface DebateState {
  // 会话
  sessionId: string | null;
  sessionData: SessionStateSummary | null;

  // 消息列表（前端自行维护，用于渲染历史）
  messages: ChatMessage[];

  // UI 状态
  isLoading: boolean;
  draftText: string;              // 输入草稿，失败后不丢失
  detailOpenIndex: Set<number>;   // 哪些消息的"详情"是展开的

  // 配置（新建会话前可编辑）
  config: {
    caseBackground: string;
    scenarioHint: string;
    maxRounds: number;
  };

  // 错误
  error: ErrorResponse | null;

  // 服务状态
  backendHealthy: boolean | null; // null=未检测, true=可用, false=不可用
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;               // user: 原文; assistant: assistant_brief
  detail?: string;               // assistant_detail
  counterargumentStructured?: CounterargumentStructured;
  counterargumentCitations?: CounterargumentCitations;
  counterargumentQualityFlags?: string[];
  attackTarget?: string;
  attackTargetCategory?: string;
}
```

### 6.2 关键动作

| 动作 | 触发 | API 调用 | 状态变更 |
| --- | --- | --- | --- |
| 健康检查 | 页面首次加载 | `GET /health` | 设置 `backendHealthy` |
| 新建会话 | 点击"新建会话" | `POST /sessions` | 重置全部状态，保存 sessionId |
| 发送消息 | 点击"发送" | `POST /sessions/{id}/turn` (send) | 追加 user + assistant message，更新 sessionData |
| 结束辩论 | 点击"结束辩论" | `POST /sessions/{id}/turn` (end) | 追加最后一条消息，更新 report，禁用输入 |
| 恢复会话 | 页面加载（如有 sessionId） | `GET /sessions/{id}` | 恢复 sessionData |
| 切换详情 | 点击"详情"按钮 | 无 | 切换 detailOpenIndex |
| 切换主题 | 点击主题切换 | 无 | 切换 `data-theme` |

---

## 7. 交互与状态控制（硬性要求）

### 7.1 按钮状态矩阵

```
if (sessionData === null):
    [发送] disabled, [结束辩论] disabled  → 需要先"新建会话"

if (sessionData.end_reason_code === "IN_PROGRESS"):
    [发送] enabled, [结束辩论] enabled

if (sessionData.end_reason_code in ["USER_ENDED", "MAX_ROUNDS_REACHED"]):
    [发送] disabled, [结束辩论] disabled
    左侧栏 [新建会话] 高亮闪烁提示
```

### 7.2 防重复提交

- 发送/结束请求期间，按钮显示 loading 状态并 `disabled`
- `isLoading === true` 时禁止所有操作

### 7.3 草稿保留

- 请求失败后，`draftText` **不清空**，用户可修改后重试
- 只有请求 **成功** 才清空输入框

### 7.4 轮次指示

- 在顶部栏或输入区附近展示 `round_index / max_rounds`（如"第 2/5 轮"）

---

## 8. 错误处理（硬性要求 · 必须实现）

### API 层封装

```typescript
// services/api.ts 核心逻辑

const BASE_URL = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const API_PREFIX = "/api/v1";

class ApiError extends Error {
  code: string;
  traceId: string;
  details?: Record<string, unknown>;

  constructor(response: ErrorResponse) {
    super(response.error.message);
    this.code = response.error.code;
    this.traceId = response.trace_id;
    this.details = response.error.details;
  }
}

async function apiCall<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${API_PREFIX}${url}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!res.ok) {
    const errorData: ErrorResponse = await res.json();
    throw new ApiError(errorData);
  }

  return res.json();
}

// ── 具体接口 ──────────────────────────────────

export async function checkHealth(): Promise<HealthResponse> {
  return apiCall<HealthResponse>("/health");
}

export async function createSession(req?: CreateSessionRequest): Promise<SessionEnvelope> {
  return apiCall<SessionEnvelope>("/sessions", {
    method: "POST",
    body: JSON.stringify(req || {}),
  });
}

export async function sendTurn(sessionId: string, req: TurnRequest): Promise<SessionEnvelope> {
  return apiCall<SessionEnvelope>(`/sessions/${sessionId}/turn`, {
    method: "POST",
    body: JSON.stringify(req),
  });
}

export async function getSession(sessionId: string): Promise<SessionEnvelope> {
  return apiCall<SessionEnvelope>(`/sessions/${sessionId}`);
}
```

### 前端错误分支

```typescript
try {
  const data = await sendTurn(sessionId, { action: "send", user_text: text });
  // 更新状态...
} catch (err) {
  if (err instanceof ApiError) {
    switch (err.code) {
      case "INVALID_ARGUMENT":
        // 在输入区下方显示错误提示，保留草稿
        break;
      case "SESSION_NOT_FOUND":
        // 弹窗："会话已失效，请新建会话"
        break;
      case "SESSION_ALREADY_ENDED":
        // 禁用发送，toast："辩论已结束"
        break;
      case "INTERNAL_ERROR":
        // 通用错误 + 重试按钮
        // 在错误提示中展示 trace_id（供排障）
        break;
    }
  }
}
```

---

## 9. 调试面板（硬性要求）

放在中间主栏底部，默认折叠为一行按钮"🔧 调试面板"。

展开后显示以下字段（JSON 查看器或表格均可）：

| 分组 | 字段 |
| --- | --- |
| 会话控制 | `end_reason_code`, `should_end`, `round_index` |
| 攻击点 | `attack_target_category`, `attack_target_source`, `attack_target_reason` |
| 检索状态 | `retrieval_mode`, `knowledge_sufficiency`, `knowledge_missing_aspects` |
| 报告 | `report_source`, `report_quality_flags` |
| 原始 debug | `debug` 完整对象（可折叠 JSON 树） |

> 对应 Streamlit 页面底部"节点观测（测试用）"面板，用于一致性回归。

---

## 10. 视觉设计要求（双主题）

### 10.1 整体风格

- **法律/专业感**：稳重清晰，信息密度高但不杂乱
- **双主题**：浅色 + 深色，提供一键切换，默认跟随 `prefers-color-scheme`
- **中文友好**：字体必须支持中文（推荐 Noto Sans SC / 思源黑体），行高 1.6+
- **三栏布局在 1440px+ 屏幕上清晰可用**

### 10.2 色彩体系（CSS Variables · 双主题）

```css
/* ── 浅色主题 ──────────────────────────── */
[data-theme="light"] {
  --bg-primary: #f8f9fa;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f0f2f5;
  --bg-sidebar: #fafbfc;
  --text-primary: #1a1a2e;
  --text-secondary: #5a5a7a;
  --text-tertiary: #8e8ea0;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --accent-light: #dbeafe;
  --user-bubble: #2563eb;
  --user-bubble-text: #ffffff;
  --agent-bubble: #f0f2f5;
  --agent-bubble-text: #1a1a2e;
  --border: #e5e7eb;
  --border-light: #f0f0f0;
  --error: #dc2626;
  --warning: #f59e0b;
  --success: #16a34a;
  --shadow: 0 1px 3px rgba(0,0,0,0.08);
}

/* ── 深色主题 ──────────────────────────── */
[data-theme="dark"] {
  --bg-primary: #0f1117;
  --bg-secondary: #161922;
  --bg-tertiary: #1e2230;
  --bg-sidebar: #131620;
  --text-primary: #e8eaed;
  --text-secondary: #9aa0a6;
  --text-tertiary: #6b7280;
  --accent: #4a9eff;
  --accent-hover: #3a88e0;
  --accent-light: #1a2f4a;
  --user-bubble: #1a3a5c;
  --user-bubble-text: #e8eaed;
  --agent-bubble: #1e2230;
  --agent-bubble-text: #e8eaed;
  --border: #2e3440;
  --border-light: #252830;
  --error: #f44336;
  --warning: #ff9800;
  --success: #4caf50;
  --shadow: 0 1px 3px rgba(0,0,0,0.3);
}

/* ── 通用变量 ──────────────────────────── */
:root {
  --font-sans: "Noto Sans SC", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", "Fira Code", monospace;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 16px;
  --transition: 200ms ease;

  /* 报告评分色（两个主题通用） */
  --score-high: #16a34a;   /* 80+ */
  --score-mid: #f59e0b;    /* 60~79 */
  --score-low: #dc2626;    /* <60 */
}
```

### 10.3 主题切换实现

```typescript
// context/ThemeContext.tsx 核心逻辑
type Theme = "light" | "dark";

// 1. 初始化：读取 localStorage 或跟随系统
const getInitialTheme = (): Theme => {
  const saved = localStorage.getItem("theme");
  if (saved === "light" || saved === "dark") return saved;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

// 2. 切换时设置 data-theme 属性
document.documentElement.setAttribute("data-theme", theme);
localStorage.setItem("theme", theme);
```

### 10.4 关键视觉元素

- **Agent 气泡**：左侧有细色条（accent 色），增加辨识度
- **"详情"按钮**：半透明小按钮，hover 时高亮，图标使用展开箭头
- **结构化反驳卡片**：每段用左侧色条 + 标题 + 内容格式，引用 ID 以小标签展示
- **报告区评分**：环形进度条或大字 + 颜色（根据分数分档变色）
- **加载状态**：Agent 气泡处显示 typing indicator（三个跳动圆点动画）
- **过渡动画**：消息出现和详情展开使用 CSS transition（300ms ease）
- **主题切换**：切换时所有颜色变量平滑过渡（`transition: background-color var(--transition), color var(--transition)`）

### 10.5 响应式（推荐实现）

- `≥ 1440px`：三栏全部展示
- `1024px ~ 1440px`：右侧报告栏可折叠为侧边抽屉
- `< 1024px`：左侧配置也折叠，仅保留中间对话

---

## 11. 完整交互流程（Coding Agent 请按此实现）

```
1. 页面加载
   ├─ 初始化主题（localStorage / 系统偏好）
   └─ GET /api/v1/health
       ├─ 成功 → 显示主界面
       └─ 失败 → 显示"后端服务不可用，请确认已启动 API"提示

2. 用户填写配置（或使用默认值），点击 [新建会话]
   └─ POST /api/v1/sessions { case_background, scenario_hint, max_rounds }
   └─ 保存 session_id（写入 state + localStorage）
   └─ 清空消息列表
   └─ 右侧报告区显示空态占位
   └─ 左侧配置区锁定（round_index > 0 后）

3. 用户输入文本，点击 [发送]
   ├─ 前端校验：文本非空、长度 ≤ 4000
   ├─ 追加用户消息到消息列表（立即渲染）
   ├─ 显示 Agent typing indicator
   ├─ POST /api/v1/sessions/{id}/turn { action: "send", user_text }
   ├─ 成功后：
   │   ├─ 用 response.session.assistant_brief 追加 Agent 消息
   │   ├─ 保存 counterargument_structured / citations / quality_flags 到该消息
   │   ├─ 更新 sessionData（含 round_index 等）
   │   ├─ 清空输入框
   │   ├─ 检查 should_end：如果 true，禁用发送/结束按钮
   │   └─ 检查 report：如果非空，右侧渲染报告
   └─ 失败后：
       ├─ 移除刚追加的用户消息（或标记为失败）
       ├─ 移除 typing indicator
       ├─ 保留输入草稿
       └─ 按错误码分支处理

4. 用户点击 [结束辩论]
   ├─ 确认对话框："确定要结束辩论吗？"
   ├─ POST /api/v1/sessions/{id}/turn { action: "end", user_text: "" }
   ├─ 追加最后一条 Agent 消息
   ├─ 禁用 发送/结束 按钮
   ├─ 右侧渲染完整报告
   └─ 左侧 [新建会话] 高亮提示

5. 用户点击 Agent 气泡 右上角 [详情]
   ├─ 展开/折叠详情区（toggle）
   ├─ 详情区渲染 assistant_detail 全文
   └─ 下方渲染 counterargument_structured 结构化卡片（含引用标注）

6. 页面刷新恢复
   ├─ 从 localStorage 读取 session_id
   ├─ GET /api/v1/sessions/{id}
   ├─ 恢复 sessionData
   └─ 注意：消息列表需要前端持久化到 localStorage 或从状态重建

7. 主题切换
   └─ 点击 ☀/🌙 按钮 → 切换 data-theme → 所有颜色平滑过渡
```

---

## 12. 环境变量

在 `frontend/.env.local` 中配置：

```env
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

---

## 13. 交付检查清单（Coding Agent 完成后需逐条确认）

### 基础
- [ ] 项目可通过 `npm run dev` 正常运行（无编译错误）
- [ ] 三栏布局已实现（左=配置 280px、中=对话 flex、右=报告 360px）
- [ ] 浅色 + 深色双主题可切换，默认跟随系统偏好

### API 集成
- [ ] 已按 `/api/v1` 契约封装 API 层（含 TypeScript 类型定义）
- [ ] 首屏调用 `GET /health` 检测后端状态
- [ ] `POST /sessions` 创建会话功能正常
- [ ] `POST /sessions/{id}/turn` (send) 发送消息功能正常
- [ ] `POST /sessions/{id}/turn` (end) 结束辩论功能正常
- [ ] `GET /sessions/{id}` 页面恢复功能正常

### 对话展示
- [ ] Agent 气泡显示 `assistant_brief`
- [ ] "详情"按钮展开 `assistant_detail` 完整内容
- [ ] 详情展开后包含 `counterargument_structured` 结构化反驳卡片
- [ ] 结构化反驳卡片展示 `counterargument_citations` 引用角标
- [ ] `counterargument_quality_flags` 非空时有警告标签展示
- [ ] Agent 回复等待期间显示 typing indicator

### 报告区
- [ ] 右侧报告区空态占位正常（report === null）
- [ ] 右侧报告区在 `report` 非空时渲染完整报告（全部 9 个字段）
- [ ] 报告区展示 `report_source` 和 `report_quality_flags`
- [ ] 评分展示分档变色（高/中/低）

### 交互与状态
- [ ] 按 `end_reason_code` 正确控制按钮可用状态
- [ ] 发送期间防重复提交（loading + disabled）
- [ ] 请求失败后保留输入草稿
- [ ] 会话进行中配置区锁定
- [ ] 结束后高亮提示"新建会话"

### 错误处理
- [ ] 错误码分支处理已实现（`INVALID_ARGUMENT` / `SESSION_NOT_FOUND` / `SESSION_ALREADY_ENDED` / `INTERNAL_ERROR`）
- [ ] 错误提示中展示 `trace_id`
- [ ] 后端不可用时显示友好提示

### 调试
- [ ] 调试面板已实现（可折叠抽屉，展示关键字段 + debug 原始对象）

### 视觉
- [ ] 页面视觉具有法律/专业感
- [ ] 中文字体清晰（Noto Sans SC 或等效）
- [ ] 消息出现和详情展开有过渡动画
- [ ] 主题切换有颜色过渡效果

---

## 14. 重要注意事项（避免踩坑）

1. **`send` 文本中包含"结束"不会触发结束**：结束 **仅** 由 `action=end` 或服务端达到 `max_rounds` 触发。前端不要在文本中检测关键词。
2. **`report` 仅在 `should_end === true` 后才可能非空**：对话进行中 `report` 始终为 `null`。
3. **`round_index` 是 0-based**：创建会话后为 `0`，第一次 `send` 后为 `1`。
4. **所有 API 响应都包裹在 `{ session: { ... } }` 信封中** — 别忘了解包。
5. **`counterargument_structured` 在创建会话时为空对象 `{}`** — 渲染前做空值判断。
6. **后端 CORS 已开放**（`allow_origins=["*"]`），前端直连 `http://localhost:8000` 即可。
7. **会话有 TTL（24小时）**：超时后 `GET /sessions/{id}` 会返回 `SESSION_NOT_FOUND`，前端应handle。
8. **`send` 时 `user_text` 不可为空**：后端会返回 400 `INVALID_ARGUMENT`。前端应在调用前校验。
9. **`attack_target_category` 和 `attack_target_source` 可为 `null`**（创建会话时）— 展示时做空值判断。
