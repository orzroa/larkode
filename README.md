# Larkode

[English](README_en.md) | 中文

通过 WebSocket 长连接将飞书（Lark）与 AI 助手集成。服务器主动连接到飞书接收事件，无需暴露外部端口。

---

## 一、项目特点

| 特性 | 说明 |
|------|------|
| 🚀 **零端口暴露** | 服务器主动连接飞书，无需公网 IP、无需端口映射、无需 HTTPS 证书 |
| ⚡ **实时流式输出** | AI 回答实时流式展示到飞书卡片，无需等待完整响应，体验流畅 |
| 🔔 **AI 主动通知** | 配置 Hook 后，AI 完成任务或需要确认时主动通知你 |
| 🧠 **自动拉起会话** | 发送指令后自动启动 AI 进程，无需手动启动 |
| 🔌 **多 AI 支持** | 支持 Claude Code、iFlow，工厂模式易于扩展新助手 |
| 📱 **随时随地** | 手机上的飞书 App 就是你的 AI 终端，通勤路上也能写代码 |
| ✅ **高测试覆盖** | 600+ 单元测试，核心模块覆盖率达 63%+ |

---

## 二、安装部署

### 2.1 环境要求

| 环境组件 | 要求 | 说明 |
|------|------|------|
| Python | 3.11+ | |
| Node.js | 18+ | 用于 Claude Code CLI |
| tmux | 最新版 | 用于 Session 管理 |

### 2.2 创建飞书应用

**步骤 1：进入飞书开放平台**

访问 [飞书开放平台](https://open.feishu.cn/)，登录后点击「创建企业自建应用」。

**步骤 2：配置应用信息**

- 应用名称：自定义（如「AI 助手」）
- 应用描述：自定义
- 应用图标：上传一个图标

**步骤 3：获取应用凭据**

创建完成后，在「凭证与基础信息」页面获取：
- `App ID`
- `App Secret`

**步骤 4：配置应用权限**

在「权限管理」页面，申请以下权限：

| 权限 | 说明 |
|------|------|
| `im:message:readonly` | 获取单聊、群组消息 |
| `im:message.p2p_msg:readonly` | 读取用户发给机器人的单聊消息 |
| `im:message:send_as_bot` | 以应用的身份发消息 |
| `im:resource` | 获取与上传图片或文件资源 |

**步骤 5：发布应用**

在「版本管理与发布」页面创建版本并发布，等待审核通过。

### 2.3 安装项目

**第 1 步：安装 uv（Python 包管理器）**

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# 或使用 pip
pip install uv
```

**第 2 步：克隆项目并安装依赖**

```bash
git clone <repository-url>
cd larkode

# 创建虚拟环境
uv venv

# 安装依赖
uv pip install -r requirements.txt

# 安装 Claude Code CLI（需要单独安装）
npm install -g @anthropic-ai/claude-code
```

**第 3 步：配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入飞书应用凭据：

```env
# 飞书应用凭据（必填）
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# AI 助手配置（必填）
AI_ASSISTANT_TYPE=claude_code
CLAUDE_CODE_WORKSPACE_DIR=/path/to/workspace
```

**第 4 步：配置 AI 主动通知（可选）**

配置后，AI 完成任务或需要确认时会主动通知你。

4.1 获取你的飞书用户 ID：

1. 在飞书中打开与机器人的对话
2. 点击右上角「...」→ 点击自己的头像
3. 点击「复制成员 ID」（即 open_id，格式如 `ou_xxxxx`）

4.2 配置环境变量：

```bash
# 在 .env 文件中添加
FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxxxxxxxxxxxxx
```

4.3 配置 Claude Code 设置：

编辑 `~/.claude/settings.json`，添加 hooks 配置：

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /你的路径/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /你的路径/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /你的路径/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ]
  }
}
```

**第 5 步：启动服务**

```bash
./start.sh
```

---

## 三、使用指南

### 3.1 命令列表

| 命令 | 说明 |
|------|------|
| `任意内容` 或 `/命令` | 执行 Claude Code 命令 |
| `#help` | 显示帮助信息 |
| `#cancel` | 取消当前运行 |
| `#history [数量]` | 查看历史消息（默认10条） |
| `#shot [行数]` | 查看截屏（默认200行，如 `#shot 500`） |
| `#model [序号]` | 查看或切换模型（无参数显示列表） |

### 3.2 使用示例

```
用户: 帮我写一个冒泡排序
AI: [执行并返回结果]

用户: #model
AI: [显示可用模型列表]

用户: #model 1
AI: [切换到模型1]

用户: #history 20
AI: [显示最近20条历史消息]

用户: #shot 500
AI: [显示最近500行的截屏]
```

---

## 四、开发文档

### 4.1 架构

```
飞书用户端
    ↓ WebSocket 事件
WebSocket 客户端
    ↓ 事件分发
消息处理器 → 任务管理器 → AI 助手工厂 → Session 管理 → Tmux 执行器
    ↓
卡片构建器 → 飞书 API
```

### 4.2 目录结构

```
larkode/
├── src/
│   ├── ai_assistants/       # AI 助手实现（工厂模式）
│   ├── ai_executor/         # AI 命令执行器
│   ├── feishu/              # 飞书 API
│   ├── handlers/            # 事件处理器
│   ├── interfaces/          # 接口定义
│   ├── models/              # 数据模型
│   ├── storage/             # 数据持久化
│   ├── utils/               # 工具函数
│   ├── exceptions.py        # 统一异常体系
│   ├── ai_session_manager.py
│   ├── task_manager.py
│   └── message_handler.py
├── tests/                   # 单元测试（600+ 测试）
├── data/                    # SQLite 数据库
├── logs/                    # 日志文件
├── docs/                    # 文档
├── larkode.py               # 入口
└── start.sh                 # 启动脚本
```

### 4.3 运行测试

```bash
# 运行所有测试
./tests/run_all_tests.sh

# 运行单元测试
uv run pytest tests/ -v --ignore=tests/integration/
```

### 4.4 日志文件

| 文件 | 说明 |
|------|------|
| `logs/app.log` | 应用日志 |
| `logs/stdout.log` | 进程输出日志 |
| `logs/hook_events.log` | Hook 事件日志 |

---

## 五、常见问题

**Q: 如何选择 AI 助手？**

通过 `AI_ASSISTANT_TYPE` 环境变量配置：
- `claude_code` - 使用 Claude Code（默认）
- `iflow` - 使用 iFlow CLI

**Q: 服务启动失败怎么办？**

1. 检查 `.env` 配置是否正确
2. 确认飞书应用凭据有效
3. 查看日志：`tail -f logs/app.log`

**Q: 收不到消息？**

1. 确认飞书应用已发布并审核通过
2. 确认应用权限配置正确
3. 检查服务是否正常运行

---

## License

MIT