# Larkode

Integrate Feishu (Lark) with AI assistants via WebSocket long connections. The server actively connects to Feishu to receive events - no external port exposure required.

## Quick Start

### Install uv

```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or use pip
pip install uv
```

### Install Project Dependencies

```bash
# 1. Clone the project
git clone <repository-url>
cd larkode

# 2. Create virtual environment (creates .venv folder automatically)
uv venv

# 3. Install dependencies
uv pip install -r requirements.txt

# Claude Code CLI needs to be installed separately
npm install -g @anthropic-ai/claude-code

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your Feishu app credentials

# 5. Start the service
./start.sh
# Or run directly
uv run python main.py
```

## Requirements

| Component | Requirement | Notes |
|-----------|-------------|-------|
| Python | 3.11+ | |
| Node.js | 18+ | For Claude Code CLI |
| tmux | Latest | For Session management |

## Features

- WebSocket long connections, server actively connects to Feishu
- Real-time responses, command execution results returned in real-time
- Task queue management, supports async execution and cancellation
- SQLite data persistence
- Rich Feishu interactive card display
- Intelligent Session management, auto-detects or creates AI assistant sessions
- Multiple AI assistant support (Claude Code, iFlow)
- Unified exception handling and logging system

## Architecture

```
Feishu Client
    ↓ WebSocket Event
WebSocket Client
    ↓ Event Dispatch
Message Handler → Task Manager → AI Assistant Factory → Session Manager → Tmux Executor
    ↓
Card Builder → Feishu API
```

## Directory Structure

```
larkode/
├── claude_settings.example.json  # Claude Code Hook configuration example
├── src/config/                   # Configuration management
│   └── settings.py              # Pydantic Settings
├── data/                         # SQLite database
├── docs/                         # Documentation
│   ├── todo/                     # TODO items
│   └── tasks/                    # Completed tasks
├── logs/                         # Log files
├── src/                          # Source code
│   ├── ai_assistants/           # AI assistant implementations (factory pattern)
│   │   └── default/             # Default implementation
│   ├── ai_executor/             # AI command executor
│   ├── feishu/                  # Feishu API
│   ├── handlers/                # Event handlers
│   │   ├── event_handlers.py   # Event handling
│   │   ├── platform_commands.py # Platform commands
│   │   ├── attachment_handler.py # Attachment handling
│   │   └── interaction_monitor.py # Interaction monitoring
│   ├── interfaces/              # Interface definitions
│   ├── factories/               # Factory classes
│   ├── models/                  # Data models
│   ├── storage/                  # Data persistence
│   ├── utils/                   # Utility functions
│   │   ├── tmux_utils.py        # Tmux utilities
│   │   └── message_number.py   # Message numbering
│   ├── exceptions.py            # Unified exception hierarchy
│   ├── logging_utils.py         # Logging utilities
│   ├── ai_session_manager.py    # Session management
│   ├── task_manager.py          # Task queue
│   └── message_handler.py       # Message handling
├── tests/                        # Unit tests (505+ tests)
├── main.py                       # Entry point
├── start.sh                      # Startup script
└── requirements.txt              # Python dependencies
```

## Commands

| Command | Description |
|---------|-------------|
| Any command | Execute AI assistant command |
| #help | Show help |
| #cancel | Cancel current execution |
| #history | View message history |
| #shot | View tmux screenshot |
| #model | View or switch model |

## Configuration

### Environment Variables

Main `.env` file configuration:

```env
# Feishu app (used when IM_PLATFORM=feishu)
FEISHU_APP_ID=cli_xxxxx
FEISHU_APP_SECRET=xxxxx
FEISHU_MESSAGE_DOMAIN=FEISHU_DOMAIN

# AI assistant configuration
AI_ASSISTANT_TYPE=claude_code  # or iflow
CLAUDE_CODE_WORKSPACE_DIR=/path/to/workspace
CLAUDE_CODE_SESSION_ID=         # Optional, auto-detect
CLAUDE_CODE_CLI_PATH=           # Optional, default claude

# Message configuration
CARD_MAX_LENGTH=1500
USE_SAFE_CARD_FORMATTING=true

# Hook configuration
HOOK_ENABLED=true
AI_HOOK_SCRIPT=src/hook_handler.py

# Hook notification user ID (optional)
# When set, AI key events will notify the specified user
# Get it: Right-click your avatar in Feishu -> Copy ID -> open_id
FEISHU_HOOK_NOTIFICATION_USER_ID=
```

### Configure Claude Code Hook (Important!)

To enable AI proactive notifications, configure Claude Code Hook:

**Step 1: Get your Feishu user ID**
1. Open the conversation with the bot in Feishu
2. Right-click your avatar
3. Select "Copy Member ID" (open_id)

**Step 2: Configure environment variables**
Add to `.env` file:
```bash
# Replace with your Feishu user ID
FEISHU_HOOK_NOTIFICATION_USER_ID=ou_xxxxxxxxxxxxxxxx
```

**Step 3: Configure Claude Code settings**
1. Create or edit `~/.claude/settings.json` in your system home directory:
```bash
# For first-time configuration:
mkdir -p ~/.claude
cp /path/to/larkode/claude_settings.example.json ~/.claude/settings.json
```

2. Edit `~/.claude/settings.json`, add hooks configuration, replace paths with actual paths:
```json
{
  # Existing configuration items
  ...
  # New hooks configuration
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

**Step 4: Restart Claude Code**
After configuration, restart Claude Code service for changes to take effect.

### Feishu App Permissions

Ensure your Feishu app has the following permissions:

**Required Permissions (5):**
| Permission | Description |
|------------|-------------|
| `im:message:readonly` | Get single chat, group messages |
| `im:message.p2p_msg:readonly` | Read single chat messages sent by users to bot |
| `im:message:send_as_bot` | Send messages as app |
| `im:resource` | Get and upload image or file resources |
| `cardkit:card:write` | Create and update cards (required for streaming output) |

**API Call List:**
1. `im.v1.message.create` - Send text/card/file messages
2. `im.v1.message_resource.get` - Download images in messages
3. `im.v1.file.create` - Upload files/images return file_key
4. `cardkit.v1.card.create` - Create card entities (streaming output)
5. `cardkit.v1.card.update` - Update card content (streaming output)
6. WebSocket (`wss://open.feishu.cn/open-apis/ws/v4/app/...`) - Receive message events

**Permission Application Location:** Feishu Open Platform → App Details → Permission Management

## Logs

- `logs/app.log` - Application logs
- `logs/stdout.log` - Process output logs
- `logs/hook_events.log` - Hook event logs

## Testing

```bash
# Run all tests
uv run pytest tests/ -v

# Or use test script
./tests/run_all_tests.sh
```

## FAQ

### Q: How to choose AI assistant?

Configure via `AI_ASSISTANT_TYPE` environment variable:
- `claude_code` - Use Claude Code (default)
- `iflow` - Use iFlow CLI

### Q: How to view service logs?

```bash
tail -f logs/app.log
```

### Q: What to do if service startup fails?

1. Check if `.env` configuration is correct
2. Confirm Feishu app credentials are valid
3. Check error messages in logs

## License

MIT