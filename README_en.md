# Larkode

English | [中文](README.md)

Integrate Feishu (Lark) with AI assistants via WebSocket long connections. The server actively connects to Feishu to receive events - no external port exposure required.

---

## 1. Key Features

| Feature | Description |
|---------|-------------|
| 🚀 **Zero Port Exposure** | Server actively connects to Feishu - no public IP, no port forwarding, no HTTPS certificate needed |
| ⚡ **Real-time Streaming** | AI responses stream to Feishu cards in real-time - no waiting for complete responses |
| 🔔 **AI Proactive Notifications** | With Hook configured, AI notifies you when tasks complete or confirmation is needed |
| 🧠 **Auto-start Session** | AI process starts automatically when you send a command - no manual startup needed |
| 🔌 **Multi-AI Support** | Supports Claude Code, iFlow - factory pattern makes adding new assistants easy |
| 📱 **Anywhere, Anytime** | Feishu App on your phone becomes your AI terminal - code even during your commute |
| ✅ **High Test Coverage** | 600+ unit tests, core modules coverage at 63%+ |

---

## 2. Installation

### 2.1 Requirements

| Component | Requirement | Notes |
|-----------|-------------|-------|
| Python | 3.11+ | |
| Node.js | 18+ | For Claude Code CLI |
| tmux | Latest | For Session management |

### 2.2 Create Feishu App

**Step 1: Go to Feishu Open Platform**

Visit [Feishu Open Platform](https://open.feishu.cn/), login and click "Create Enterprise Custom App".

**Step 2: Configure App Info**

- App Name: Custom (e.g., "AI Assistant")
- App Description: Custom
- App Icon: Upload an icon

**Step 3: Get App Credentials**

After creation, get from "Credentials & Basic Info" page:
- `App ID`
- `App Secret`

**Step 4: Configure App Permissions**

On "Permission Management" page, request these permissions:

| Permission | Description |
|------------|-------------|
| `im:message:readonly` | Get single chat, group messages |
| `im:message.p2p_msg:readonly` | Read single chat messages sent by users to bot |
| `im:message:send_as_bot` | Send messages as app |
| `im:resource` | Get and upload image or file resources |

**Step 5: Publish App**

On "Version Management & Release" page, create a version and publish. Wait for approval.

### 2.3 Install Project

**Step 1: Install uv (Python package manager)**

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip
pip install uv
```

**Step 2: Clone and install dependencies**

```bash
git clone <repository-url>
cd larkode

# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Install Claude Code CLI (separate installation required)
npm install -g @anthropic-ai/claude-code
```

**Step 3: Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` file with your Feishu app credentials:

```env
# Feishu app credentials (required)
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# AI assistant configuration (required)
AI_ASSISTANT_TYPE=claude_code
CLAUDE_CODE_WORKSPACE_DIR=/path/to/workspace
```

**Step 4: Configure AI proactive notifications (optional)**

Once configured, AI will proactively notify you when tasks complete or confirmation is needed.

4.1 Get your Feishu user ID:

1. Open the conversation with the bot in Feishu
2. Click "..." in top right → click your avatar
3. Click "Copy Member ID" (open_id, format like `ou_xxxxx`)

4.2 Configure environment variable:

```bash
# Add to .env file
FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxxxxxxxxxxxxx
```

4.3 Configure Claude Code settings:

Edit `~/.claude/settings.json`, add hooks configuration:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /your/path/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /your/path/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /your/path/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ]
  }
}
```

**Step 5: Start the service**

```bash
./start.sh
```

---

## 3. Usage Guide

### 3.1 Commands

| Command | Description |
|---------|-------------|
| `any text` or `/command` | Execute Claude Code command |
| `#help` | Show help |
| `#cancel` | Cancel current execution |
| `#history [count]` | View message history (default 10) |
| `#shot [lines]` | View screenshot (default 200, e.g., `#shot 500`) |
| `#model [index]` | View or switch model (no arg shows list) |

### 3.2 Usage Examples

```
User: Help me write a bubble sort
AI: [Executes and returns result]

User: #model
AI: [Shows available model list]

User: #model 1
AI: [Switches to model 1]

User: #history 20
AI: [Shows last 20 messages]

User: #shot 500
AI: [Shows last 500 lines screenshot]
```

---

## 4. Development Documentation

### 4.1 Architecture

```
Feishu Client
    ↓ WebSocket Event
WebSocket Client
    ↓ Event Dispatch
Message Handler → Task Manager → AI Assistant Factory → Session Manager → Tmux Executor
    ↓
Card Builder → Feishu API
```

### 4.2 Directory Structure

```
larkode/
├── src/
│   ├── ai_assistants/       # AI assistant implementations (factory pattern)
│   ├── ai_executor/         # AI command executor
│   ├── feishu/              # Feishu API
│   ├── handlers/            # Event handlers
│   ├── interfaces/          # Interface definitions
│   ├── models/              # Data models
│   ├── storage/             # Data persistence
│   ├── utils/               # Utility functions
│   ├── exceptions.py        # Unified exception hierarchy
│   ├── ai_session_manager.py
│   ├── task_manager.py
│   └── message_handler.py
├── tests/                   # Unit tests (600+ tests)
├── data/                    # SQLite database
├── logs/                    # Log files
├── docs/                    # Documentation
├── larkode.py               # Entry point
└── start.sh                 # Startup script
```

### 4.3 Running Tests

```bash
# Run all tests
./tests/run_all_tests.sh

# Run unit tests only
uv run pytest tests/ -v --ignore=tests/integration/
```

### 4.4 Log Files

| File | Description |
|------|-------------|
| `logs/app.log` | Application logs |
| `logs/stdout.log` | Process output logs |
| `logs/hook_events.log` | Hook event logs |

---

## 5. FAQ

**Q: How to choose AI assistant?**

Configure via `AI_ASSISTANT_TYPE` environment variable:
- `claude_code` - Use Claude Code (default)
- `iflow` - Use iFlow CLI

**Q: What to do if service startup fails?**

1. Check if `.env` configuration is correct
2. Confirm Feishu app credentials are valid
3. View logs: `tail -f logs/app.log`

**Q: Not receiving messages?**

1. Confirm Feishu app is published and approved
2. Confirm app permissions are configured correctly
3. Check if service is running normally

---

## License

MIT