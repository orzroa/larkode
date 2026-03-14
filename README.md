# Larkode

[English](README_en.md) | 中文

通过 WebSocket 长连接将飞书（Lark）与 AI 助手集成。服务器主动连接到飞书接收事件，无需暴露外部端口。

## 快速开始

### 安装 uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

### 安装项目依赖

```bash
# 1. 克隆项目
git clone <repository-url>
cd larkode

# 2. 创建虚拟环境（自动创建 .venv 文件夹）
uv venv

# 3. 安装依赖
uv pip install -r requirements.txt

# Claude Code CLI 需要单独安装
npm install -g @anthropic-ai/claude-code

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入飞书应用凭据

# 5. 启动服务
./start.sh
# 或直接运行
uv run python main.py
```

## 环境要求

| 环境组件 | 要求 | 说明 |
|------|------|------|
| Python | 3.11+ | |
| Node.js | 18+ | 用于 Claude Code CLI |
| tmux | 最新版 | 用于 Session 管理 |

## 功能特性

- WebSocket 长连接，服务器主动连接飞书
- 实时响应，命令执行结果实时返回
- 任务队列管理，支持异步执行和取消
- SQLite 数据持久化
- 飞书富交互卡片展示
- 智能 Session 管理，自动检测或创建 AI 助手 Session
- 多种 AI 助手支持（Claude Code、iFlow）
- 统一的异常处理和日志系统

## 架构

```
飞书用户端
    ↓ WebSocket 事件
WebSocket 客户端
    ↓ 事件分发
消息处理器 → 任务管理器 → AI 助手工厂 → Session 管理 → Tmux 执行器
    ↓
卡片构建器 → 飞书 API
```

## 目录结构

```
larkode/
├── claude_settings.example.json  # Claude Code Hook 配置示例
├── src/config/                   # 配置管理
│   └── settings.py              # Pydantic Settings
├── data/                         # SQLite 数据库
├── docs/                         # 文档
│   ├── todo/                     # 待办事项
│   └── tasks/                    # 已完成任务
├── logs/                         # 日志文件
├── src/                          # 源代码
│   ├── ai_assistants/           # AI 助手实现（工厂模式）
│   │   └── default/             # 默认实现
│   ├── ai_executor/             # AI 命令执行器
│   ├── feishu/                  # 飞书 API
│   ├── handlers/                # 事件处理器
│   │   ├── event_handlers.py   # 事件处理
│   │   ├── platform_commands.py # 平台命令
│   │   ├── attachment_handler.py # 附件处理
│   │   └── interaction_monitor.py # 交互监控
│   ├── interfaces/              # 接口定义
│   ├── factories/               # 工厂类
│   ├── models/                  # 数据模型
│   ├── storage/                  # 数据持久化
│   ├── utils/                   # 工具函数
│   │   ├── tmux_utils.py        # Tmux 工具
│   │   └── message_number.py   # 消息编号
│   ├── exceptions.py            # 统一异常体系
│   ├── logging_utils.py         # 日志工具
│   ├── ai_session_manager.py    # Session 管理
│   ├── task_manager.py          # 任务队列
│   └── message_handler.py       # 消息处理
├── tests/                        # 单元测试（284+ 测试）
├── main.py                       # 入口
├── start.sh                      # 启动脚本
└── requirements.txt              # Python 依赖
```

## 命令

| 命令 | 说明 |
|------|------|
| 任意命令 | 执行 AI 助手命令 |
| #help | 显示帮助 |
| #cancel | 取消当前运行 |
| #history | 查看历史消息 |
| #shot | 查看 tmux 截屏 |
| #model | 查看或切换模型 |

## 配置

### 环境变量

`.env` 文件主要配置：

```env
# 飞书应用（IM_PLATFORM=feishu 时使用）
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_MESSAGE_DOMAIN=FEISHU_DOMAIN

# AI 助手配置
AI_ASSISTANT_TYPE=claude_code  # 或 iflow
CLAUDE_CODE_WORKSPACE_DIR=/path/to/workspace
CLAUDE_CODE_SESSION_ID=         # 可选，自动检测
CLAUDE_CODE_CLI_PATH=           # 可选，默认 claude

# 消息配置
CARD_MAX_LENGTH=1500
USE_SAFE_CARD_FORMATTING=true

# Hook 配置
HOOK_ENABLED=true
AI_HOOK_SCRIPT=src/hook_handler.py

# Hook 通知用户 ID（可选）
# 设置后，AI 的关键事件会通知到指定用户
# 获取方式：飞书中右键点击自己头像 -> 复制 ID -> open_id
FEISHU_HOOK_NOTIFICATION_USER_ID=
```

### 配置 Claude Code Hook（重要！）

为了让 AI 主动通知你，需要配置 Claude Code 的 Hook：

**步骤 1：获取你的飞书用户 ID**
1. 在飞书中打开与机器人的对话
2. 右键点击自己的头像
3. 选择"复制成员 ID"（open_id）

**步骤 2：配置环境变量**
在 `.env` 文件中添加：
```bash
# 替换为你的飞书用户 ID
FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxxxxxxxxxxxxx
```

**步骤 3：配置 Claude Code 设置**
1. 在系统主目录创建或编辑 `~/.claude/settings.json`：
```bash
# 如果是首次配置：
mkdir -p ~/.claude
cp /path/to/larkode/claude_settings.example.json ~/.claude/settings.json
```

2. 编辑 `~/.claude/settings.json`，增加hooks 配置项，将路径替换为实际路径：
```json
{
  # 原有配置项
  ...
  # 新增 hooks 配置项
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project /path/to/larkode/src/hook_handler.py",
            "timeout": 5
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project /path/to/larkode/src/hook_handler.py",
            "timeout": 5
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run --no-project /path/to/larkode/src/hook_handler.py",
            "timeout": 5
          }
        ]
      }
    ]
  }
}
```

**步骤 4：重启 Claude Code**
配置完成后，重启 Claude Code 服务使配置生效。

### 飞书应用权限

确保飞书应用具有以下权限：

**需要申请的权限（4个）：**
| 权限 | 说明 |
|------|------|
| `im:message:readonly` | 获取单聊、群组消息 |
| `im:message.p2p_msg:readonly` | 读取用户发给机器人的单聊消息 |
| `im:message:send_as_bot` | 以应用的身份发消息 |
| `im:resource` | 获取与上传图片或文件资源 |

**API 调用清单：**
1. `im.v1.message.create` - 发送文本/卡片/文件消息
2. `im.v1.message_resource.get` - 下载消息中的图片
3. `im.v1.file.create` - 上传文件/图片返回 file_key
4. WebSocket (`wss://open.feishu.cn/open-apis/ws/v4/app/...`) - 接收消息事件

**权限申请位置：** 飞书开放平台 → 应用详情 → 权限管理

## 日志

- `logs/app.log` - 应用日志
- `logs/stdout.log` - 进程输出日志
- `logs/hook_events.log` - Hook 事件日志

## 测试

```bash
# 运行所有测试
uv run pytest tests/ -v

# 或使用测试脚本
./tests/run_all_tests.sh
```

## 常见问题

### Q: 如何选择 AI 助手？

通过 `AI_ASSISTANT_TYPE` 环境变量配置：
- `claude_code` - 使用 Claude Code（默认）
- `iflow` - 使用 iFlow CLI

### Q: 如何查看服务日志？

```bash
tail -f logs/app.log
```

### Q: 服务启动失败怎么办？

1. 检查 `.env` 配置是否正确
2. 确认飞书应用凭据有效
3. 查看日志中的错误信息

## License

MIT
