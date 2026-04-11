# 青律前端实现清单

本文不涉及具体前端技术实现，只定义后续 `Next.js` 前端需要具备的页面能力、状态管理要求和展示要点。

## 1. 页面目标

前端页面需要同时承载两类信息：

- 左侧或主区域：引导式多轮对话
- 右侧或次区域：结构化交付物与证据链

整体目标不是“普通聊天页”，而是“聊天驱动的维权工作台”。

## 2. 最低可用页面结构

建议至少包含以下区域：

### 2.1 对话区

必备内容：

- 用户消息列表
- 助手消息列表
- 当前输入框
- 发送按钮
- 加载状态

建议增强：

- 场景标签展示
- 快捷追问按钮
- 重新开始会话按钮

### 2.2 侧边栏

至少拆成 3 个面板：

- 证据链面板
  - 展示 `sidebar.evidence_slots`
  - 对缺失字段做高亮
- 行动方案面板
  - 展示 `sidebar.action_steps`
  - 按步骤编号
- 交付物面板
  - 展示 `sidebar.demand_letter`
  - 展示 `sidebar.similar_cases`

### 2.3 顶部状态区

建议展示：

- 当前场景 `scenario_label`
- 当前阶段 `current_stage`
- 证据完成度 `progress.evidence_completion_ratio`
- 会话状态提示

## 3. 必须支持的交互能力

### 3.1 会话创建与续聊

- 首轮不传 `session_id`
- 如果使用同步接口，首轮响应后保存 `session_id`
- 如果使用流式接口，收到 `session` 事件后保存 `session_id`
- 后续轮次继续传同一个 `session_id`
- 页面刷新后可用 `GET /api/v1/triage/session/{session_id}` 恢复

### 3.2 流式体验支持

建议优先接入 `POST /api/v1/triage/stream`，因为它更适合比赛演示和工作台式交互。

前端需要支持：

- 发起 `POST` 流式请求
- 按 `SSE` 事件分块解析
- 根据 `stage_started` 展示当前执行阶段
- 根据 `stage_completed` 增量更新：
  - 当前助手回复
  - 进度条
  - 证据链面板
  - 行动方案面板
  - 交付物面板
- 收到 `complete` 后写入最终整轮状态
- 收到 `error` 后提示用户重试

### 3.3 多轮补证据

前端需要允许用户持续补充：

- 时间地点
- 金额
- 约定
- 聊天截图说明
- 转账记录说明
- 对方身份信息

不要假设一轮就能收集全。

### 3.4 快捷追问与快捷动作

建议把以下字段渲染成可点击元素：

- `frontend.follow_up_questions`
  - 可直接作为快捷补充提示
- `frontend.suggested_actions`
  - 可作为按钮或提示卡片

### 3.5 Markdown 渲染

`sidebar.demand_letter` 需要支持 Markdown 渲染，至少支持：

- 标题
- 粗体
- 列表
- 段落

### 3.6 复制能力

建议提供以下复制按钮：

- 复制催告函
- 复制行动步骤
- 复制完整会话摘要

## 4. 前端状态管理建议

建议前端至少管理以下状态：

- `sessionId`
- `messages`
- `sidebar`
- `progress`
- `frontendGuidance`
- `scenario`
- `loading`
- `error`

推荐原则：

- 聊天区以 `conversation_history` 为准
- 当前轮展示以 `assistant_turn` 为准
- 侧边栏更新以 `sidebar` 为准
- 引导文案和交互建议以 `frontend` 为准

## 5. 必须处理的页面状态

### 5.1 初始空状态

页面刚打开时应至少提供：

- 标题说明
- 5+1 场景入口
- 示例问题

### 5.2 加载中状态

发送请求后建议：

- 禁用发送按钮
- 显示“正在分析案情”
- 如果走流式接口，显示当前阶段名
- 保留上一轮侧边栏内容，避免页面跳空

### 5.3 错误状态

至少区分：

- 网络错误
- 404 会话不存在
- 后端异常

### 5.4 降级状态

当后端检索失败时，前端不需要特殊报错，但应允许以下内容正常展示：

- 通用型法律定性
- 通用型行动步骤
- 占位或简化版案例结果

当流式接口中断时，建议：

- 保留已收到的阶段数据
- 停止 loading
- 提示用户“可点击重试，或切换同步接口重新生成”

## 6. 建议的组件拆分

推荐但不强制的组件粒度：

- `ChatPanel`
- `MessageList`
- `MessageInput`
- `ScenarioSelector`
- `ProgressHeader`
- `EvidenceSidebar`
- `ActionPlanSidebar`
- `DemandLetterCard`
- `SimilarCasesCard`

## 7. 建议的演示场景

前端联调时，建议至少准备以下 5 个案例作为固定 demo：

- 房东不退押金
- 兼职工资被拖欠
- 同学借钱不还
- 教培机构拒绝退费
- 校园论坛造谣 / 网暴

## 8. 非本轮必须实现项

以下内容适合作为后续增强，不属于当前阶段五必做：

- token 级流式输出
- 文件上传和截图上传
- 富文本编辑催告函
- 多会话列表页
- 用户登录
- 数据库存档

## 9. 推荐联调流程

后续前后端联调建议按这个顺序进行：

1. 先接通 `GET /health`
2. 接通 `POST /api/v1/triage/run`
3. 渲染聊天区和侧边栏
4. 接入 `session_id` 续聊
5. 接入 `GET /api/v1/triage/session/{session_id}` 恢复
6. 接入 `POST /api/v1/triage/stream` 做阶段级流式更新
7. 最后再做样式、动画和交互优化
