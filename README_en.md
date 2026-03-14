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

### 2.2 Installation Steps

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
# Edit .env with your Feishu app credentials
```

Main configuration items:

```env
# Feishu app credentials
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx

# AI assistant configuration
AI_ASSISTANT_TYPE=claude_code  # or iflow
CLAUDE_CODE_WORKSPACE_DIR=/path/to/workspace
```

**Step 4: Configure Claude Code Hook (optional, for AI proactive notifications)**

See [3.3 Configure Hook Notifications](#33-configure-hook-notifications-optional)

**Step 5: Start the service**

```bash
./start.sh
# Or run directly
uv run python main.py
```

---

## 3. Usage Guide

### 3.1 Commands

| Command | Description |
|---------|-------------|
| Any command | Execute AI assistant command |
| #help | Show help |
| #cancel | Cancel current execution |
| #history | View message history |
| #shot | View tmux screenshot |
| #model | View or switch model |

### 3.2 Feishu App Configuration

**Required permissions (4):**

| Permission | Description |
|------------|-------------|
| `im:message:readonly` | Get single chat, group messages |
| `im:message.p2p_msg:readonly` | Read single chat messages sent by users to bot |
| `im:message:send_as_bot` | Send messages as app |
| `im:resource` | Get and upload image or file resources |

**Permission Application Location:** Feishu Open Platform → App Details → Permission Management

### 3.3 Configure Hook Notifications (Optional)

Once configured, AI will proactively notify you when tasks complete or confirmation is needed.

**Step 1: Get your Feishu user ID**

1. Open the conversation with the bot in Feishu
2. Right-click your avatar
3. Select "Copy Member ID" (open_id)

**Step 2: Configure environment variables**

```bash
# Add to .env file
FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxxxxxxxxxxxxx
```

**Step 3: Configure Claude Code settings**

Edit `~/.claude/settings.json`, add hooks configuration:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /path/to/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /path/to/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [{ "type": "command", "command": "uv run --no-project /path/to/larkode/src/hook_handler.py", "timeout": 5 }]
      }
    ]
  }
}
```

**Step 4: Restart Claude Code service**

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
├── main.py                  # Entry point
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

---

## License

MIT