# 青律 YouthLex

面向高校场景的双模块法律智能体系统，围绕两个真实且高频的问题展开：

- 普通大学生在遇到租房、兼职、消费、借贷等纠纷时，往往不知道如何梳理事实、保留证据并启动维权
- 法学生以及更广泛的大学生群体，在现实场景中缺少高质量、强对抗的法律辩论训练环境

青律将这两个需求拆解为两条清晰产品线：`维权小助手` 与 `辩论陪练`，分别服务行动支持和实战训练。

## 在线体验

- 公网地址：[http://118.31.125.31/](http://118.31.125.31/)

## 核心模块

### 1. 维权小助手

面向普通学生的法律维权辅助模块，负责：

- 多轮案情收集与事实梳理
- 法条定性与风险提示
- 维权步骤建议
- 催告函与投诉草稿生成
- 相似案例辅助说明

### 2. 辩论陪练

面向法学生和法律兴趣用户的对抗式训练模块，负责：

- 回合制法律辩论
- 反向论点检索与针对性反驳
- 漏洞识别与追问施压
- 辩后复盘与结构化总结

## 项目亮点

- **双模块任务路由**：不做“大而全”法律咨询，而是聚焦高校高频维权与法律训练两类场景
- **LangGraph 工作流编排**：将多轮追问、状态管理、结果整理组织成可控的智能体流程
- **RAG 法律知识增强**：结合相关法条与类案信息，提升输出的针对性与结构性
- **前后端分层协作**：后端负责智能体逻辑与检索，前端负责交互编排与结果展示
- **多端演示能力**：既支持 Web 工作台，也支持比赛展示页与训练型前端

## 技术栈

### 后端

- Python
- FastAPI
- LangGraph
- OpenAI Compatible API / MiniMax
- 法律检索服务

### 前端

- Next.js
- React
- TypeScript
- React Markdown

### 辅助能力

- RAG / 法律知识检索
- Streamlit（辩论模块基线演示）
- Markdown 文档与比赛展示页

## 仓库结构

```text
.
├── Law_assistant/        # 维权小助手后端
├── frontend/             # 维权小助手前端工作台
├── Debate_partner/       # 辩论陪练模块（后端 + 演示前端）
├── 比赛提交内容/           # 比赛展示材料（已加入 .gitignore）
├── 项目简介.md
└── README.md
```

## 快速开始

### 1. 启动维权小助手后端

```powershell
cd Law_assistant
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

默认接口：

- `GET /health`
- `POST /api/v1/triage/run`
- `POST /api/v1/triage/stream`

### 2. 启动维权小助手前端

```powershell
cd frontend
npm install
npm run dev
```

### 3. 启动辩论陪练模块

```powershell
cd Debate_partner
pip install -r requirements.txt
uvicorn app.api.app:app --reload --host 0.0.0.0 --port 8000
```

如需运行 Streamlit 基线界面：

```powershell
cd Debate_partner
streamlit run streamlit_app.py
```

## 环境变量

项目包含多个子模块，建议分别参考各目录下的 `.env.example` 配置本地环境变量。

当前仓库根目录已通过 `.gitignore` 统一忽略：

- 所有目录下的 `.env` 和 `.env.*`
- `node_modules`、`.next`、`.venv`、缓存目录
- `比赛提交内容/` 与本地工具目录

这样可以尽量避免 API Key、构建产物和本地依赖被误提交。

## 验证命令

后端测试：

```powershell
cd Law_assistant
.\.venv\Scripts\python.exe -m pytest tests/test_api.py tests/test_graph.py tests/test_frontend_adapter.py tests/test_nodes.py tests/test_legal_workflows.py tests/test_triage_planner.py -q
```

前端检查：

```powershell
cd frontend
npm run lint
```

## 文档索引

- [Law_assistant/README.md](./Law_assistant/README.md)
- [Debate_partner/README.md](./Debate_partner/README.md)
- [项目简介.md](./项目简介.md)

## 说明

本项目主要用于高校法律服务与训练场景探索，当前输出内容用于学习、演示与原型验证，不构成正式法律意见。
