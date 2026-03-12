# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working with this repository.

## Project Overview

Python project integrating Feishu (Lark) with AI assistants (Claude Code, iFlow) via WebSocket long connections. The server actively connects to Feishu - no external port exposure required. Users send commands through Feishu to trigger AI assistant execution and receive real-time responses.

## Directory Structure

```
larkode/
├── src/
│   ├── config/              # Configuration management (Pydantic Settings)
│   ├── ai_assistants/       # AI assistant implementations (factory pattern)
│   ├── ai_executor/         # AI command executor (tmux)
│   ├── feishu/              # Feishu API client
│   ├── handlers/            # Event handlers
│   ├── interfaces/          # Interface definitions
│   ├── factories/           # Factory classes
│   ├── storage/             # Data persistence (SQLite)
│   └── utils/               # Utility functions
├── tests/                   # Unit tests (284+ tests)
├── data/                    # SQLite database
├── docs/                         # Documentation
│   ├── todo/                     # Future improvements
│   └── tasks/                    # Completed tasks
└── logs/                    # Application logs
```

## Development Commands

### Setup
```bash
# Create virtual environment
uv venv

# Install dependencies
uv pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your Feishu app credentials

# Start the service
./start.sh
```

### Testing
```bash
# Run all tests
./tests/run_all_tests.sh

# Run unit tests only
uv run pytest tests/ -v --ignore=tests/integration/

# Low-spec servers (1-core 2GB): single-threaded mode
uv run pytest tests/ -v -n0 --ignore=tests/integration/
```

## Configuration

### Main Environment Variables (.env)

**Feishu Configuration**
- `FEISHU_APP_ID` - Feishu app ID
- `FEISHU_APP_SECRET` - Feishu app secret
- `FEISHU_MESSAGE_RECEIVE_ID_TYPE` - Message ID type (`open_id` or `user_id`)
- `FEISHU_MESSAGE_DOMAIN` - Feishu API domain

**AI Assistant Configuration**
- `AI_ASSISTANT_TYPE` - AI assistant type (`claude_code`, `iflow`)
- `CLAUDE_CODE_WORKSPACE_DIR` - Claude Code workspace directory (required)
- `CLAUDE_CODE_SESSION_ID` - Fixed session ID (optional, auto-detect)
- `CLAUDE_CODE_CLI_PATH` - Claude Code CLI path (default `claude`)
- `AI_HOOK_SCRIPT` - Hook script path (default `src/hook_handler.py`)

**Message Configuration**
- `CARD_MAX_LENGTH` - Max card message length (default 1500)
- `TASK_TIMEOUT` - Task timeout in seconds (default 300)
- `DB_PATH` - SQLite database path (default `./data/larkode.db`)

### Feishu Bot Permissions
- `im:message:readonly` - Get messages
- `im:message.p2p_msg:readonly` - Read p2p messages
- `im:message:send_as_bot` - Send messages as bot
- `im:resource` - Upload/download files

## Core Components

1. **`src/feishu/`** - Feishu API integration
   - `FeishuAPI` - Authentication, message sending
   - `FeishuWebSocketClient` - WebSocket event push (auto-reconnect)

2. **`src/ai_assistants/`** - AI assistant implementations (factory pattern)
   - `DefaultAIInterface` - Default implementation (using TmuxAIExecutor)
   - `DefaultSessionManager` - Tmux session management

3. **`src/handlers/`** - Event handlers
   - `event_handlers.py` - Event handling
   - `platform_commands.py` - Platform commands
   - `attachment_handler.py` - Attachment handling
   - `interaction_monitor.py` - Interaction monitoring

4. **`src/ai_executor/`** - AI command executor
   - `TmuxAIExecutor` - Execute commands in tmux session (streaming output)

5. **`src/ai_session_manager.py`** - Session management
   - `AISessionManager` - Auto-detect, find, or create tmux sessions

6. **`src/task_manager.py`** - Task queue management
   - `TaskManager` - Task queue, execution, status tracking

7. **`src/storage/`** - Data persistence (SQLite)
   - `Database` - CRUD operations for users, tasks, messages

8. **`src/exceptions.py`** - Unified exception hierarchy
   - `BaseAppError` - Base exception (code, message, details)
   - Subclasses: ConfigError, TaskError, AIError, StorageError, PlatformError

9. **`src/logging_utils.py`** - Context logging
   - `get_logger()` - Returns ContextLogger (tracks user_id/task_id/request_id)

10. **`src/hook_handler.py`** - Claude Code Hooks
    - Captures `UserPromptSubmit`, `Stop`, `Notification` events
    - Sends Feishu notifications on key events

## Message Flow

1. Service starts, establishes WebSocket connection to Feishu
2. User sends message in Feishu → Feishu pushes event via WebSocket
3. MessageHandler validates and parses the command
4. TaskManager creates a task and adds to queue
5. AIAssistantFactory creates appropriate AI assistant instance
6. SessionManager ensures there's an available session
7. TmuxAIExecutor runs the command in the session context
8. Results are sent back via Feishu card messages
9. All interactions are stored in SQLite database

## Available Commands

| Command | Description |
|---------|-------------|
| `#help` | Show help information |
| `#cancel` | Cancel current running task |
| `#history` | Show message history |
| `#shot` | View tmux screenshot |
| `#model` | View or switch CCR model |

Or simply type any command directly to execute it in AI assistant.

## Hooks Configuration

To enable AI active notifications, configure Claude Code Hook:

1. Copy `claude_settings.example.json` to `~/.claude/settings.json`
2. Update the paths to point to your project's `src/hook_handler.py`
3. Configure the hooks: `UserPromptSubmit`, `Stop`, `PermissionRequest`, `PreToolUse`, `SubagentStop`

See README.md for detailed Hook configuration steps.

## Important Notes

- Uses WebSocket long connections: server connects TO Feishu, not webhook callbacks
- No need to expose any ports to the internet
- WebSocket includes automatic reconnection with exponential backoff
- Task execution is asynchronous and can be canceled
- All user tasks and messages are persisted for history queries
- Messages use Feishu interactive cards for rich display
- Long outputs (>1500 chars) are truncated in card messages
- **Session Management**: Auto-detects running AI processes, finds/reuses sessions, or creates new ones in tmux
- **Multiple AI Support**: Supports Claude Code, iFlow via `AI_ASSISTANT_TYPE`

## Main Dependencies

- `uv` - Python package manager (recommended)
- `lark-oapi>=1.2.24` - Feishu/Lark official SDK
- `python-dotenv>=1.0.0` - Environment variable management
- `pydantic>=2.5.3` - Data validation
- `pydantic-settings>=2.0.0` - Pydantic Settings
- `psutil>=5.9.0` - Process and system utilities
- `pytest>=7.0.0` - Testing framework

**Note**: Claude Code CLI needs to be installed separately via `npm install -g @anthropic-ai/claude-code`