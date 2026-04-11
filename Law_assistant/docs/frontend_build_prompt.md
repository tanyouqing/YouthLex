# 青律 (QingLv) Legal Triage Agent — Next.js 前端构建 Prompt

> **本文档是一份完整的、供 AI Coding Agent 阅读并执行的前端构建指令。**
> 请严格按照下述规范创建项目结构、编写代码、对接后端接口。

---

## 0. 项目背景与目标

### 0.1 项目简介

「青律」是一个面向高校学生的法律维权智能体 (Legal Triage Agent)。后端基于 `FastAPI + LangGraph + MiniMax 2.5` 构建，已完成以下能力：

- **5 阶段 LangGraph 图流程**：情绪安抚 → 法条亮剑 → 证据填槽 → 维权 SOP → 交付物生成
- **5+1 场景自动路由**：`housing`(住房)、`labor`(劳动)、`consumer`(消费)、`debt`(借贷)、`ip_reputation`(名誉/知识产权)、`other`(其他)
- **法规检索 + 类案检索**（得理开放平台）
- **多轮会话状态管理**：基于 `session_id` 的证据补全与状态复用
- **SSE 流式接口**：按阶段推送处理进度

### 0.2 前端定位

前端不是"普通聊天页"，而是 **"聊天驱动的维权工作台"**：
- **左侧/主区域**：引导式多轮对话
- **右侧/次区域**：结构化交付物与证据链侧边栏
- **顶部**：场景标签 + 阶段进度 + 证据完成度

### 0.3 技术栈

| 层面 | 技术选型 |
|------|----------|
| 框架 | **Next.js 14+** (App Router) |
| 语言 | **TypeScript** |
| 样式 | **Tailwind CSS** |
| 状态管理 | React `useState` / `useReducer`（无需引入 Redux） |
| Markdown 渲染 | `react-markdown` + `remark-gfm` |
| HTTP 请求 | 原生 `fetch`（SSE 需要 POST，不能用 EventSource） |
| 包管理 | `npm` |

---

## 1. 后端 API 概览

后端运行在 `http://127.0.0.1:8000`，提供以下 4 个接口：

| 方法 | 路径 | 用途 |
|------|------|------|
| `GET` | `/health` | 服务可用性检查 |
| `POST` | `/api/v1/triage/run` | 同步单轮对话（备用） |
| `POST` | `/api/v1/triage/stream` | **主接口**：SSE 流式阶段级对话 |
| `GET` | `/api/v1/triage/session/{session_id}` | 会话快照恢复 |

> **说明**：后端已配置 CORS 中间件（`allow_origins=["*"]`），前端可直接跨域访问后端接口，无需额外代理。

---

## 2. TypeScript 类型定义

以下类型 **1:1 翻译自后端 Pydantic schema**（`app/schemas/triage.py`），前端必须在 `src/types/triage.ts` 中定义并全局使用。

```typescript
// src/types/triage.ts

// ── 场景枚举 ──
export type TriageScenario =
  | "housing"
  | "labor"
  | "consumer"
  | "debt"
  | "ip_reputation"
  | "other";

// ── 证据六要素槽位 ──
export interface EvidenceSlots {
  counterparty: string | null;  // 相对方信息
  time_place: string | null;    // 时间地点
  amount: string | null;        // 标的金额
  agreement: string | null;     // 合同/约定
  breach_fact: string | null;   // 违约/侵权事实
  existing_evidence: string[];  // 现有证据列表
}

// ── 相似案例 ──
export interface SimilarCase {
  title: string;      // 案例标题
  summary: string;    // 【案情摘要】
  judgment: string;   // 【结果】
  takeaway: string;   // 【维权启示】
}

// ── 侧边栏 ──
export interface TriageSidebar {
  evidence_slots: EvidenceSlots;
  action_steps: string[];
  demand_letter: string | null;       // Markdown 格式催告函
  similar_cases: SimilarCase[];
}

// ── 对话消息 ──
export interface ConversationMessage {
  role: "user" | "assistant";
  content: string;
}

// ── 当前轮助手回复 ──
export interface AssistantTurn {
  role: "assistant";
  content: string;
  stage: string;  // 对应的 LangGraph 阶段键名
}

// ── 阶段进度 ──
export interface StageProgress {
  current_stage: string;
  completed_stages: string[];
  remaining_stages: string[];
  next_stage: string | null;
  collected_slots: string[];       // 已收集的槽位 key
  missing_slots: string[];         // 缺失的槽位 key
  evidence_completion_ratio: number; // 0.00 ~ 1.00
  evidence_complete: boolean;
  deliverables_ready: boolean;
}

// ── 前端引导提示 ──
export interface FrontendGuidance {
  display_mode: "slot_collection" | "action_guidance" | "deliverables_ready";
  primary_panel: "evidence_slots" | "action_steps" | "demand_letter";
  input_placeholder: string;
  follow_up_questions: string[];   // 渲染为快捷追问按钮
  suggested_actions: string[];     // 渲染为 CTA 按钮
}

// ── 主响应体（run 接口 & session 快照共用） ──
export interface TriageResponse {
  session_id: string;
  scenario: TriageScenario;
  scenario_label: string;           // 中文场景名，直接展示
  assistant_message: string;
  current_stage: string;
  assistant_turn: AssistantTurn;
  conversation_history: ConversationMessage[];
  progress: StageProgress;
  frontend: FrontendGuidance;
  sidebar: TriageSidebar;
}

// ── 请求体 ──
export interface TriageRequest {
  user_input: string;
  scenario?: TriageScenario | null;
  session_id?: string | null;
}

// ── SSE 事件类型 ──
export type SSEEventType =
  | "session"
  | "stage_started"
  | "stage_completed"
  | "complete"
  | "error";

// ── SSE 各事件 payload ──
export interface SSESessionPayload {
  session_id: string;
  scenario: TriageScenario;
}

export interface SSEStageStartedPayload {
  stage: string;
  session_id: string;
}

export interface SSEStageCompletedPayload {
  stage: string;
  session_id: string;
  assistant_turn: AssistantTurn;
  progress: StageProgress;
  frontend: FrontendGuidance;
  sidebar: TriageSidebar;
}

export interface SSECompletePayload {
  response: TriageResponse;
}

export interface SSEErrorPayload {
  message: string;
  session_id: string;
}
```

---

## 3. API 接口详细规范

### 3.1 `GET /health`

```
Response 200: { "status": "ok", "model": "MiniMax-Text-01" }
```

用途：页面加载时检测后端是否在线，如果不在线则在界面上展示连接失败提示。

### 3.2 `POST /api/v1/triage/run`（同步备用接口）

- **Request Body**：`TriageRequest`
- **Response Body**：`TriageResponse`
- 当流式接口不可用时降级使用

### 3.3 `POST /api/v1/triage/stream`（主接口）

- **Request Body**：与 `run` 完全相同的 `TriageRequest` JSON
- **Response**：`Content-Type: text/event-stream`

因为是 POST + SSE，**不能使用浏览器原生 `EventSource`**，必须用 `fetch` + `ReadableStream` + `TextDecoder` 手动解析。

#### SSE 事件流顺序

```
session → stage_started(empathy) → stage_completed(empathy)
       → stage_started(legal_grounding) → stage_completed(legal_grounding)
       → stage_started(slot_filling) → stage_completed(slot_filling)
       → stage_started(action_plan) → stage_completed(action_plan)
       → stage_started(deliverables) → stage_completed(deliverables)
       → complete
```

#### SSE 解析参考实现

```typescript
async function streamTriage(
  request: TriageRequest,
  handlers: {
    onSession: (data: SSESessionPayload) => void;
    onStageStarted: (data: SSEStageStartedPayload) => void;
    onStageCompleted: (data: SSEStageCompletedPayload) => void;
    onComplete: (data: SSECompletePayload) => void;
    onError: (data: SSEErrorPayload) => void;
  }
) {
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
  const response = await fetch(`${API_BASE}/api/v1/triage/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (!response.ok || !response.body) {
    throw new Error(`HTTP ${response.status}`);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const chunks = buffer.split("\n\n");
    buffer = chunks.pop() ?? "";

    for (const chunk of chunks) {
      const eventMatch = chunk.match(/^event: (.+)$/m);
      const dataMatch = chunk.match(/^data: (.+)$/m);
      if (!eventMatch || !dataMatch) continue;

      const eventType = eventMatch[1] as SSEEventType;
      const data = JSON.parse(dataMatch[1]);

      switch (eventType) {
        case "session":
          handlers.onSession(data);
          break;
        case "stage_started":
          handlers.onStageStarted(data);
          break;
        case "stage_completed":
          handlers.onStageCompleted(data);
          break;
        case "complete":
          handlers.onComplete(data);
          break;
        case "error":
          handlers.onError(data);
          break;
      }
    }
  }
}
```

### 3.4 `GET /api/v1/triage/session/{session_id}`

- **Response**：`TriageResponse`（与 `run` 接口结构完全一致）
- 用于页面刷新后恢复会话
- 404 返回 `{ "detail": "Session not found" }`

---

## 4. 后端地址与跨域

后端已配置 CORS 中间件（`allow_origins=["*"]`、`allow_methods=["*"]`、`allow_headers=["*"]`），前端可以**直接跨域调用**后端接口，无需 Next.js `rewrites` 或 Route Handler 代理。

### 4.1 API 基地址

前端通过环境变量 `NEXT_PUBLIC_API_BASE` 配置后端地址，默认值为 `http://127.0.0.1:8000`。

```env
# .env.local
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

### 4.2 推荐在 `src/lib/api.ts` 中统一管理

```typescript
// src/lib/api.ts
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";

// 使用示例
fetch(`${API_BASE}/health`);
fetch(`${API_BASE}/api/v1/triage/run`, { method: "POST", ... });
fetch(`${API_BASE}/api/v1/triage/stream`, { method: "POST", ... });
fetch(`${API_BASE}/api/v1/triage/session/${sessionId}`);
```

> 不需要配置 `next.config.js` 的 `rewrites`，所有请求直接发往后端即可。

---

## 5. 页面布局与组件结构

### 5.1 整体布局

```
┌────────────────────────────────────────────────────────────┐
│                    ProgressHeader                          │
│  [场景标签]  [阶段进度条 ●●●○○]  [证据完成度 33%]         │
├──────────────────────────────┬─────────────────────────────┤
│                              │                             │
│        ChatPanel             │       Sidebar               │
│                              │                             │
│  ┌────────────────────────┐  │  ┌───────────────────────┐  │
│  │    MessageList         │  │  │   EvidencePanel       │  │
│  │    (消息流)             │  │  │   (证据六要素)         │  │
│  │                        │  │  ├───────────────────────┤  │
│  │                        │  │  │   ActionPlanPanel     │  │
│  │                        │  │  │   (维权步骤)           │  │
│  │                        │  │  ├───────────────────────┤  │
│  │                        │  │  │   DeliverablePanel    │  │
│  │                        │  │  │   ├ DemandLetterCard  │  │
│  │                        │  │  │   └ SimilarCasesCard  │  │
│  └────────────────────────┘  │  └───────────────────────┘  │
│  ┌────────────────────────┐  │                             │
│  │ QuickActions (追问按钮) │  │                             │
│  ├────────────────────────┤  │                             │
│  │ MessageInput (输入框)   │  │                             │
│  └────────────────────────┘  │                             │
└──────────────────────────────┴─────────────────────────────┘
```

### 5.2 推荐组件树

```
src/
├── app/
│   ├── layout.tsx              # 全局布局、字体、meta
│   ├── page.tsx                # 主页面入口
│   └── globals.css             # Tailwind 全局样式
├── components/
│   ├── ChatPanel.tsx           # 对话主面板
│   ├── MessageList.tsx         # 消息列表（用户+助手气泡）
│   ├── MessageBubble.tsx       # 单条消息气泡
│   ├── MessageInput.tsx        # 输入框 + 发送按钮
│   ├── QuickActions.tsx        # 快捷追问 + 建议动作按钮
│   ├── ScenarioSelector.tsx    # 场景选择器（首页入口）
│   ├── ProgressHeader.tsx      # 页面头：场景标签 + 进度 + 完成度
│   ├── Sidebar.tsx             # 侧边栏容器
│   ├── EvidencePanel.tsx       # 证据六要素面板
│   ├── ActionPlanPanel.tsx     # 行动步骤面板
│   ├── DemandLetterCard.tsx    # 催告函卡片（Markdown 渲染 + 复制）
│   ├── SimilarCasesCard.tsx    # 相似案例卡片
│   ├── StageIndicator.tsx      # 当前执行阶段动画指示器
│   └── EmptyState.tsx          # 空白首页引导
├── hooks/
│   ├── useTriageStream.ts      # SSE 流式请求 hook
│   └── useSessionRestore.ts    # 会话恢复 hook
├── lib/
│   ├── api.ts                  # API 调用封装
│   └── sse-parser.ts           # SSE 事件解析工具
├── types/
│   └── triage.ts               # 上述 TypeScript 类型定义
└── constants/
    └── stages.ts               # 阶段名映射 + 场景配置
```

---

## 6. 五阶段 (Stage) 元数据

后端图固定的 5 个阶段，前端需要展示对应的中文名、图标和颜色：

```typescript
// src/constants/stages.ts

export const STAGE_META: Record<string, { label: string; icon: string; order: number }> = {
  empathy:          { label: "情绪安抚", icon: "💙", order: 1 },
  legal_grounding:  { label: "法律定性", icon: "⚖️", order: 2 },
  slot_filling:     { label: "证据补全", icon: "📋", order: 3 },
  action_plan:      { label: "维权指导", icon: "🗺️", order: 4 },
  deliverables:     { label: "交付生成", icon: "📄", order: 5 },
};

// 六要素槽位的中文标签映射
export const SLOT_LABELS: Record<string, string> = {
  counterparty:     "相对方",
  time_place:       "时间地点",
  amount:           "标的金额",
  agreement:        "合同/约定",
  breach_fact:      "违约事实",
  existing_evidence: "现有证据",
};

// 场景选择器配置
export const SCENARIO_OPTIONS: Array<{
  value: string;
  label: string;
  icon: string;
  example: string;
}> = [
  { value: "housing",       label: "住房租赁纠纷", icon: "🏠", example: "房东不退押金" },
  { value: "labor",         label: "劳动与兼职纠纷", icon: "💼", example: "老板拖欠兼职工资" },
  { value: "consumer",      label: "消费者维权",   icon: "🛒", example: "教培机构拒绝退费" },
  { value: "debt",          label: "民间借贷纠纷", icon: "💰", example: "同学借钱不还" },
  { value: "ip_reputation", label: "名誉与知识产权", icon: "🛡️", example: "校园论坛造谣网暴" },
];
```

---

## 7. 前端状态管理

### 7.1 核心状态

```typescript
interface AppState {
  // 会话
  sessionId: string | null;
  scenario: TriageScenario | null;
  scenarioLabel: string | null;

  // 对话
  messages: ConversationMessage[];

  // 进度
  progress: StageProgress | null;
  currentRunningStage: string | null;  // 来自 stage_started，用于 loading 指示

  // 侧边栏
  sidebar: TriageSidebar | null;

  // 前端引导
  frontendGuidance: FrontendGuidance | null;

  // UI 状态
  loading: boolean;
  error: string | null;
  backendOnline: boolean;
}
```

### 7.2 状态更新规则

| SSE 事件 | 更新内容 |
|----------|----------|
| `session` | 保存 `sessionId` 和 `scenario` |
| `stage_started` | 设置 `currentRunningStage`，显示阶段 loading 动画 |
| `stage_completed` | 用 `assistant_turn` 追加消息；用 `progress`/`frontend`/`sidebar` 更新对应状态；清除 `currentRunningStage` |
| `complete` | 用完整 `response` 覆盖所有状态为最终值；`loading = false` |
| `error` | `loading = false`；`error = message`；保留已有阶段数据 |

### 7.3 会话生命周期

```
用户打开页面
  ├─ 检查 localStorage 是否存有 sessionId
  │   ├─ 有 → GET /session/{id} 恢复状态
  │   │       ├─ 200 → 用 TriageResponse 还原全部状态
  │   │       └─ 404 → 清除 localStorage，展示空白首页
  │   └─ 无 → 展示空白首页（EmptyState + ScenarioSelector）
  │
用户发送消息
  ├─ 首轮：不传 session_id
  ├─ 续轮：传已保存的 session_id
  ├─ 调用 POST /stream（主）或 POST /run（降级）
  └─ 收到 session 事件后将 session_id 存入 localStorage
```

---

## 8. 各组件具体要求

### 8.1 EmptyState（空白首页）

当没有活跃会话时展示：

- 项目 Logo 与标题「青律 · 高校学生维权助手」
- 简明的功能说明文字
- **ScenarioSelector**：5 个场景卡片（图标 + 标题 + 示例问题），点击后自动填入示例问题并设置 `scenario`
- 输入框，允许用户直接描述问题（此时 `scenario` 由后端自动路由）

### 8.2 MessageList + MessageBubble

- 用户消息右对齐，助手消息左对齐
- 助手消息支持 Markdown 渲染（段落、加粗、列表、标题）
- 当 `stage_started` 激活时，在消息列表末尾展示一个带当前阶段名的 loading skeleton（例如 "⚖️ 正在进行法律定性..."）
- 新消息出现时自动滚动到底部

### 8.3 MessageInput

- 多行 `textarea`，支持 `Shift+Enter` 换行、`Enter` 发送
- 发送按钮在 `loading` 时禁用
- `placeholder` 文字从 `frontend.input_placeholder` 动态读取，如果没有则使用默认值"请描述您遇到的问题..."
- 发送后清空输入框，用户消息立即追加到 `messages`

### 8.4 QuickActions

- 渲染 `frontend.follow_up_questions` 为可点击的快捷追问按钮
- 渲染 `frontend.suggested_actions` 为 CTA 按钮
- 点击快捷追问按钮时，直接将内容作为 `user_input` 发送
- 没有内容时该区域隐藏

### 8.5 ProgressHeader

- 显示当前场景标签 `scenario_label`
- 5 个阶段的步进条，已完成用实心圈、进行中用动画脉冲、未完成用空心圈
- 证据完成度百分比进度条 `progress.evidence_completion_ratio`（百分比 + 进度条动画）
- 可选：新会话按钮（清除所有状态并刷新为 EmptyState）

### 8.6 Sidebar（侧边栏）

由 `frontend.primary_panel` 控制默认展开哪个面板。三个面板均可折叠/展开。

#### 8.6.1 EvidencePanel（证据六要素面板）

- 逐条展示 6 个证据槽位
- **已填充**的槽位：绿色/实心标识 + 显示值
- **缺失**的槽位：红色/橙色高亮 + "待补充" 标签
- `existing_evidence` 数组如果非空则展示列表，空则显示"暂无证据"
- 顶部展示证据完成度进度条

#### 8.6.2 ActionPlanPanel（行动步骤面板）

- 将 `sidebar.action_steps` 按列表展示，自动编号
- 提供"一键复制所有步骤"按钮

#### 8.6.3 DeliverablePanel（交付物面板）

**DemandLetterCard（催告函卡片）**：
- 以 Markdown 渲染 `sidebar.demand_letter`
- 为空或 `null` 时展示占位提示"催告函将在分析完成后生成"
- 提供"复制催告函"按钮

**SimilarCasesCard（相似案例卡片）**：
- 展示 1~2 条 `sidebar.similar_cases`
- 每条案例以折叠卡片展示：标题 → 点击展开显示 summary / judgment / takeaway
- 为空数组时展示占位提示"相似案例将在分析完成后生成"

---

## 9. 加载与错误状态

### 9.1 加载状态

| 场景 | 行为 |
|------|------|
| 正在请求中 | 禁用发送按钮；在消息列表末尾展示 StageIndicator |
| StageIndicator 内容 | 显示当前阶段中文名（如"⚖️ 正在进行法律定性..."），阶段切换时更新 |
| 侧边栏 | **保留上一轮的内容**，避免页面跳空白 |

### 9.2 错误状态

| 错误类型 | 展示方式 |
|----------|----------|
| 后端离线 (`/health` 失败) | 页面顶部黄色 banner："后端服务未连接，请检查后端是否启动" |
| 网络错误 (fetch 失败) | Toast 提示 + 重试按钮 |
| SSE `error` 事件 | 消息列表展示错误消息 + "重试" / "切换同步模式" 按钮 |
| 会话恢复 404 | 清除本地 sessionId，回到 EmptyState |

### 9.3 降级状态

- 当后端检索失败时仍返回 200，前端**不需要**额外报错
- `sidebar.demand_letter` 可能为空 → 展示占位
- `sidebar.similar_cases` 可能为空数组 → 展示占位
- `frontend.follow_up_questions` 可能为空 → 隐藏快捷按钮区域
- SSE 流中断后：保留已收到的数据，停止 loading，提示可重试

---

## 10. 复制功能

提供以下复制按钮：

| 位置 | 复制内容 |
|------|----------|
| 催告函卡片 | `sidebar.demand_letter` 的纯文本/Markdown |
| 行动步骤面板 | 所有 `sidebar.action_steps` 拼接为带编号文本 |
| 消息气泡（可选） | 单条助手回复 |

使用 `navigator.clipboard.writeText()` 实现，复制成功后展示短暂 Toast 提示。

---

## 11. 移动端响应式

最低要求：
- 桌面端 (≥1024px)：左右双栏布局
- 平板/移动端 (<1024px)：侧边栏折叠为底部抽屉或 Tab 切换
- 输入框始终可见

---

## 12. 视觉设计要求

### 12.1 整体风格

- **深色法律风**：深蓝/深灰主色调，白色/浅灰文字
- 现代极简、专业可信赖的设计感
- 支持 **深色模式**为默认，浅色模式可选

### 12.2 推荐色板

```css
--color-primary: #3B82F6;      /* 主色：冷蓝 */
--color-primary-dark: #1E40AF; /* 深蓝 */
--color-accent: #10B981;       /* 强调/成功色：翡翠绿 */
--color-warning: #F59E0B;      /* 警告/缺失：琥珀 */
--color-danger: #EF4444;       /* 错误/危险 */
--color-bg-dark: #0F172A;      /* 深色背景 */
--color-bg-card: #1E293B;      /* 卡片/面板背景 */
--color-text: #F1F5F9;         /* 主文字 */
--color-text-muted: #94A3B8;   /* 次要文字 */
```

### 12.3 动画与交互

- 侧边栏面板展开/折叠使用 `transition` 动画
- 进度条增长使用平滑过渡
- 消息气泡进入使用 `fade-in` + `slide-up`
- StageIndicator 使用脉冲动画
- 按钮 hover 使用轻微缩放 + 颜色变化

### 12.4 字体

使用 Google Fonts **Inter** 或 **Noto Sans SC**（中文场景），在 `layout.tsx` 引入。

---

## 13. 演示数据与测试场景

前端联调时，以下 5 个 demo 输入应可正常走通全流程：

| 场景 | 示例输入 |
|------|----------|
| 住房 (`housing`) | "房东不退押金，合同还没到期就让我搬走" |
| 劳动 (`labor`) | "老板拖欠我兼职工资，还把我拉黑了" |
| 消费 (`consumer`) | "教培机构拒绝退费，说合同上写了不退" |
| 借贷 (`debt`) | "同学借了我3000块钱一直不还" |
| 名誉 (`ip_reputation`) | "有人在校园论坛发帖造谣我作弊" |

空白首页的 ScenarioSelector 应预置这些示例。

---

## 14. 推荐实现顺序

严格按以下顺序逐步实现：

1. **项目初始化**
   - `npx create-next-app@latest ./ --typescript --tailwind --eslint --app --src-dir`
   - 创建 `.env.local`，写入 `NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000`
   - 创建 `src/types/triage.ts`
   - 创建 `src/constants/stages.ts`

2. **API 层**
   - 实现 `src/lib/api.ts`（health check, run, session restore）
   - 实现 `src/lib/sse-parser.ts`（SSE 流解析）
   - 实现 `src/hooks/useTriageStream.ts`

3. **聊天区**（先跑通同步 `run` 接口）
   - `MessageList` + `MessageBubble` + `MessageInput`
   - 能发消息并展示返回

4. **切换到流式接口**
   - 接入 `useTriageStream`
   - 实现 `StageIndicator` 加载动画

5. **侧边栏**
   - `EvidencePanel` + `ActionPlanPanel` + `DeliverablePanel`

6. **ProgressHeader**
   - 阶段进度条 + 证据完成度

7. **空白首页**
   - `EmptyState` + `ScenarioSelector`

8. **会话恢复**
   - `useSessionRestore` + localStorage

9. **QuickActions**
   - 快捷追问 + 建议动作

10. **样式打磨**
    - 动画、响应式、复制功能、错误提示

---

## 15. 验收标准

完成后，前端必须满足以下标准：

- [ ] 页面加载时检测后端在线状态
- [ ] 空白首页展示 5 个场景入口 + 示例问题
- [ ] 可发送消息并通过 SSE 接收分阶段响应
- [ ] 消息列表正确展示用户/助手对话
- [ ] 阶段进度条实时更新
- [ ] 证据槽位面板区分已填充/缺失
- [ ] 行动步骤按编号展示
- [ ] 催告函以 Markdown 渲染
- [ ] 相似案例以卡片展示
- [ ] 快捷追问按钮可点击发送
- [ ] 复制按钮可用
- [ ] 页面刷新后可恢复会话
- [ ] 多轮对话证据递增补全正常
- [ ] 流式中断时保留已有数据并展示重试
- [ ] 移动端布局不会崩坏
- [ ] 整体视觉效果专业、现代、可用于比赛演示

---

## 16. 注意事项与约束

1. **不要实现**以下未列入本轮范围的功能：
   - 用户登录/注册
   - 文件上传与 OCR
   - token 级流式输出
   - 多会话列表页
   - 数据库持久化
   - WebSocket

2. **后端已固定的接口结构不可修改**，前端必须适配后端已有的字段命名和数据格式。

3. **Next.js 前端项目应创建在 `d:\tencentKAIWU\Law_assistant\frontend\` 目录下**，与后端目录平级。

4. **后端已开启 CORS（`allow_origins=["*"]`）**，前端直接调用即可，无需额外代理配置。后端地址统一通过 `NEXT_PUBLIC_API_BASE` 环境变量管理。

5. 所有中文界面文字直接硬编码在组件中即可，不需要 i18n。

6. 确保页面 `<title>` 为 "青律 · 高校学生维权助手"。
