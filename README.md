# Nix - 多智能体AI协作平台

## 项目概述

Nix 是一个多智能体AI协作平台，通过多个智能体的协同工作，为用户提供智能化的服务和解决方案。系统采用前后端分离架构，支持Web平台，具有高度的可扩展性和灵活性。

平台核心亮点包括AI工具箱（支持文件操作、终端命令、浏览器操控、MCP工具集成和数据库连接管理）、多模型AI对话、智能体管理与调度、全链路任务管理、Skills文件管理以及多厂商API Key配置等高级功能。

## 技术栈

| 层级 | 技术 | 版本 |
|------|------|------|
| 前端 | React + TypeScript | React 18 + TypeScript 5.3 |
| 路由 | React Router | v6 |
| 后端 | Python + FastAPI | Python 3.10+ + FastAPI 0.104 |
| ORM | SQLAlchemy | 2.0 |
| 数据验证 | Pydantic | 2.5 |
| 数据库 | SQLite | 3.40+ |
| AI框架 | LangChain + langchain-openai | - |
| 浏览器自动化 | Playwright | - |
| 部署 | Docker Compose | - |

## 核心功能

- **AI 对话**：支持多模型配置切换，工作目录绑定，环境感知命令生成
- **智能体管理**：创建/配置智能体，绑定AI模型，智能体间互相调度
- **任务管理**：全链路任务创建/执行/监控，实时WebSocket状态同步
- **AI 工具箱**：文件操作（搜索/读取/创建/编辑/删除）、终端命令执行、Browser-Use浏览器操控、MCP工具集成、数据库连接管理
- **Skills 管理**：Markdown文件目录树管理，按功能分类组织技能定义
- **系统设置**：多厂商API Key管理（支持多模型列表）、数据库连接配置、环境检测与持久化、用户头像管理

## 快速开始

### 前提条件

- Docker 和 Docker Compose 已安装
- OpenAI API 密钥（可选，用于聊天智能体）

### 启动服务

1. **克隆项目**
   ```bash
   git clone <repository-url>
   cd Nix
   ```

2. **配置环境变量**
   创建 `.env` 文件，添加以下内容：
   ```
   OPENAI_API_KEY=your-openai-api-key
   ```

3. **启动服务**
   ```bash
   docker-compose up --build
   ```

4. **访问应用**
   - 前端: http://localhost:3000
   - 后端API文档: http://localhost:8000/docs

## 项目结构

```
Nix/
├── frontend/src/
│   ├── components/
│   │   ├── AIToolbox.tsx        # AI工具箱（文件/终端/浏览器/MCP/数据库）
│   │   ├── AgentDashboard.tsx   # 智能体管理与调度
│   │   ├── AuthComponent.tsx    # 用户认证
│   │   ├── ChatPanel.tsx        # AI对话面板
│   │   ├── MermaidDiagram.tsx   # 图表渲染
│   │   ├── SettingsPanel.tsx    # 系统设置（API Key/数据库/环境）
│   │   ├── SkillsManager.tsx    # Skills文件管理
│   │   ├── TaskFlow.tsx         # 任务流程可视化
│   │   └── TaskManager.tsx      # 任务管理
│   ├── services/api.ts          # API服务层
│   ├── styles/globals.css       # 全局毛玻璃风格样式
│   ├── App.tsx                  # 路由与导航
│   └── App.css                  # 组件样式
├── backend/
│   ├── models/                  # SQLAlchemy数据模型
│   │   ├── agent.py             # 智能体模型
│   │   ├── api_key_config.py    # API密钥配置
│   │   ├── db_connection.py     # 数据库连接配置
│   │   ├── environment.py       # 环境信息
│   │   ├── task.py              # 任务模型
│   │   ├── user.py              # 用户模型
│   │   └── workflow.py          # 工作流模型
│   ├── routes/                  # API路由
│   │   ├── agents.py            # 智能体CRUD + 调度
│   │   ├── auth.py              # 认证 + 用户资料
│   │   ├── chat.py              # AI对话
│   │   ├── db_connections.py    # 数据库连接管理
│   │   ├── environment.py       # 环境检测与存储
│   │   ├── settings.py          # API Key配置
│   │   ├── skills.py            # Skills文件管理
│   │   ├── tasks.py             # 任务管理
│   │   ├── toolbox.py           # AI工具箱（文件/终端/浏览器/MCP）
│   │   └── workflow.py          # 工作流管理
│   ├── services/                # 业务逻辑层
│   ├── schemas/                 # Pydantic验证模型
│   ├── agents/                  # 智能体实现
│   └── main.py                  # FastAPI应用入口
├── skills/                      # Skills Markdown文件存储
├── docker-compose.yml
└── .gitignore
```

## API文档

后端API文档可通过访问 http://localhost:8000/docs 查看，包含所有可用的API端点和参数说明。

## 智能体类型

- **默认智能体**: 基础的智能体实现，提供基本的任务处理能力
- **聊天智能体**: 基于LLM的智能体，能够处理自然语言任务和对话

## 部署

系统采用Docker Compose进行部署，支持开发、测试和生产环境。

## 开发指南

### 前端开发

```bash
cd frontend
npm install
npm start
```

### 后端开发

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## 贡献

欢迎贡献代码和提出问题！

## 许可证

[MIT License](LICENSE)
