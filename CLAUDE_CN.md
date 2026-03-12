# CLAUDE_CN.md

Claude Code (claude.ai/code) 在此仓库中工作的指南。

## 项目概述

Python 项目，通过 WebSocket 长连接集成飞书（Lark）与 AI 助手（Claude Code、iFlow）。服务端主动连接飞书 - 无需暴露外部端口。用户通过飞书发送命令，触发 AI 助手执行并接收实时响应。

## 目录结构

```
larkode/
├── src/
│   ├── config/              # 配置管理（Pydantic Settings）
│   ├── ai_assistants/       # AI 助手实现（工厂模式）
│   ├── ai_executor/         # AI 命令执行器（tmux）
│   ├── feishu/              # 飞书 API 客户端
│   ├── handlers/            # 事件处理器
│   ├── interfaces/          # 接口定义
│   ├── factories/           # 工厂类
│   ├── storage/             # 数据持久化（SQLite）
│   └── utils/               # 工具函数
├── tests/                   # 单元测试（284+ tests）
├── data/                    # SQLite 数据库
├── docs/                    # 文档
│   ├── todo/                # 未来改进
│   └── tasks/               # 已完成任务
└── logs/                    # 应用日志
```

## 开发命令

### 安装
```bash
# 创建虚拟环境
uv venv

# 安装依赖
uv pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入飞书应用凭证

# 启动服务
./start.sh
```

### 测试
```bash
# 运行所有测试
./tests/run_all_tests.sh

# 仅运行单元测试
uv run pytest tests/ -v --ignore=tests/integration/

# 低配服务器（1核2GB）：单线程模式
uv run pytest tests/ -v -n0 --ignore=tests/integration/
```

## 配置

### 主要环境变量 (.env)

**飞书配置**
- `FEISHU_APP_ID` - 飞书应用 ID
- `FEISHU_APP_SECRET` - 飞书应用密钥
- `FEISHU_MESSAGE_RECEIVE_ID_TYPE` - 消息 ID 类型（`open_id` 或 `user_id`）
- `FEISHU_MESSAGE_DOMAIN` - 飞书 API 域名

**AI 助手配置**
- `AI_ASSISTANT_TYPE` - AI 助手类型（`claude_code`, `iflow`）
- `CLAUDE_CODE_WORKSPACE_DIR` - Claude Code 工作目录（必需）
- `CLAUDE_CODE_SESSION_ID` - 固定会话 ID（可选，自动检测）
- `CLAUDE_CODE_CLI_PATH` - Claude Code CLI 路径（默认 `claude`）
- `AI_HOOK_SCRIPT` - Hook 脚本路径（默认 `src/hook_handler.py`）

**消息配置**
- `CARD_MAX_LENGTH` - 卡片消息最大长度（默认 1500）
- `TASK_TIMEOUT` - 任务超时时间（秒，默认 300）
- `DB_PATH` - SQLite 数据库路径（默认 `./data/larkode.db`）

### 飞书机器人权限
- `im:message:readonly` - 获取消息
- `im:message.p2p_msg:readonly` - 读取私信
- `im:message:send_as_bot` - 以机器人发送消息
- `im:resource` - 上传/下载文件

## 核心组件

1. **`src/feishu/`** - 飞书 API 集成
   - `FeishuAPI` - 认证、消息发送
   - `FeishuWebSocketClient` - WebSocket 事件推送（自动重连）

2. **`src/ai_assistants/`** - AI 助手实现（工厂模式）
   - `DefaultAIInterface` - 默认实现（使用 TmuxAIExecutor）
   - `DefaultSessionManager` - Tmux 会话管理

3. **`src/handlers/`** - 事件处理器
   - `event_handlers.py` - 事件处理
   - `platform_commands.py` - 平台命令
   - `attachment_handler.py` - 附件处理
   - `interaction_monitor.py` - 交互监控

4. **`src/ai_executor/`** - AI 命令执行器
   - `TmuxAIExecutor` - 在 tmux 会话中执行命令（流式输出）

5. **`src/ai_session_manager.py`** - 会话管理
   - `AISessionManager` - 自动检测、查找或创建 tmux 会话

6. **`src/task_manager.py`** - 任务队列管理
   - `TaskManager` - 任务队列、执行、状态跟踪

7. **`src/storage/`** - 数据持久化（SQLite）
   - `Database` - 用户、任务、消息的 CRUD 操作

8. **`src/exceptions.py`** - 统一异常体系
   - `BaseAppError` - 基础异常（code, message, details）
   - 子类：ConfigError, TaskError, AIError, StorageError, PlatformError

9. **`src/logging_utils.py`** - 上下文日志
   - `get_logger()` - 返回 ContextLogger（追踪 user_id/task_id/request_id）

10. **`src/hook_handler.py`** - Claude Code Hooks
    - 捕获 `UserPromptSubmit`, `Stop`, `Notification` 事件
    - 在关键事件时发送飞书通知

## 消息流程

1. 服务启动，建立 WebSocket 连接到飞书
2. 用户在飞书发送消息 → 飞书通过 WebSocket 推送事件
3. MessageHandler 验证并解析命令
4. TaskManager 创建任务并加入队列
5. AIAssistantFactory 创建合适的 AI 助手实例
6. SessionManager 确保有可用会话
7. TmuxAIExecutor 在会话上下文中运行命令
8. 结果通过飞书卡片消息返回
9. 所有交互存储到 SQLite 数据库

## 可用命令

| 命令 | 说明 |
|------|------|
| `#help` | 显示帮助信息 |
| `#cancel` | 取消当前运行的任务 |
| `#history` | 显示消息历史 |
| `#shot` | 查看 tmux 截图 |
| `#model` | 查看或切换 CCR 模型 |

或直接输入任何命令执行 AI 助手。

## Hooks 配置

启用 AI 主动通知，配置 Claude Code Hook：

1. 复制 `claude_settings.example.json` 到 `~/.claude/settings.json`
2. 更新路径指向项目的 `src/hook_handler.py`
3. 配置 hooks：`UserPromptSubmit`, `Stop`, `PermissionRequest`, `PreToolUse`, `SubagentStop`

详细步骤见 README.md。

## 重要说明

- 使用 WebSocket 长连接：服务端连接到飞书，不是 webhook 回调
- 无需暴露任何端口到互联网
- WebSocket 自动重连（指数退避）
- 任务执行异步，可取消
- 所有用户任务和消息持久化
- 消息使用飞书交互卡片（富文本）
- 长输出（>1500 字符）在卡片消息中截断
- **会话管理**：自动检测运行中的 AI 进程，查找/重用会话，或在 tmux 中创建新会话
- **多 AI 支持**：通过 `AI_ASSISTANT_TYPE` 支持 Claude Code、iFlow

## 主要依赖

- `uv` - Python 包管理器（推荐）
- `lark-oapi>=1.2.24` - 飞书官方 SDK
- `python-dotenv>=1.0.0` - 环境变量管理
- `pydantic>=2.5.3` - 数据验证
- `pydantic-settings>=2.0.0` - Pydantic Settings
- `psutil>=5.9.0` - 进程和系统工具
- `pytest>=7.0.0` - 测试框架

**注意**：Claude Code CLI 需要单独安装：`npm install -g @anthropic-ai/claude-code`