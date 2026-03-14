# Claude Session Manager Interface

## Overview

The Claude Session Manager Interface (`src/interfaces/claude_session_manager.py`) provides an abstract interface for managing Claude Code sessions, including detection of running processes, session management, and tmux integration.

## Architecture Nodes Covered

This interface implements nodes N14-N19 from the architecture:

- **Node N14**: `detect_running_processes()` - 检测当前目录中的 Claude Code 进程
- **Node N15**: `find_session_from_projects()` - 从 .claude/projects/ 查找 session 文件
- **Node N16**: `check_tmux_session()` - tmux session 检查
- **Node N17**: `create_tmux_session()` - tmux session 创建
- **Node N18**: `check_process_in_tmux()` - tmux session 中进程检查
- **Node N19**: `start_claude_in_tmux()` - Claude 进程启动

## Core Components

### 1. Enums

#### SessionStatus
- `ACTIVE` - Session is active
- `INACTIVE` - Session is inactive
- `UNKNOWN` - Session status unknown

#### TmuxStatus
- `EXISTS` - Tmux session exists
- `NOT_EXISTS` - Tmux session does not exist
- `ERROR` - Error checking tmux session

### 2. Data Classes

#### ProcessInfo
Contains information about a running process:
- `pid`: Process ID
- `name`: Process name
- `cwd`: Current working directory
- `cmdline`: Command line arguments

#### SessionInfo
Contains information about a Claude session:
- `session_id`: Session identifier
- `status`: Session status
- `last_updated`: Last update timestamp
- `tmux_name`: Associated tmux session name (optional)
- `process_info`: Associated process information (optional)

### 3. Interfaces

#### ClaudeSessionManagerInterface
Main interface defining the contract for session management:

##### Core Methods
- `detect_running_processes()` - Detect running Claude processes
- `find_session_from_projects()` - Find session files in .claude/projects
- `check_tmux_session()` - Check if a tmux session exists
- `create_tmux_session()` - Create a new tmux session
- `check_process_in_tmux()` - Check for Claude processes in tmux
- `start_claude_in_tmux()` - Start Claude in a tmux session
- `get_session_info()` - Get detailed session information
- `get_or_create_session()` - Get existing or create new session
- `stop_session()` - Stop a session
- `get_active_sessions()` - Get all active sessions

##### Convenience Methods
- `stop_managed_session()` - Stop managed sessions (deprecated)

### 4. Mock Implementation

#### MockSessionManager
A mock implementation for testing:

##### Usage Example
```python
from src.interfaces.claude_session_manager import MockSessionManager

# Create mock manager
manager = MockSessionManager()

# Add mock data
manager.add_mock_process(1234, "claude", "/project/path", ["claude"])
manager.add_mock_session("session_123", "test_project")
manager.set_tmux_status("tmux_123", TmuxStatus.EXISTS)

# Test methods
session_id = manager.get_or_create_session("test_project")
print(f"Session: {session_id}")
```

## Testing

The comprehensive test suite (`tests/test_claude_session_manager.py`) includes:

### Test Categories

1. **Node Tests** - Individual node testing (N14-N19)
   - `test_node_n14_detect_running_processes`
   - `test_node_n15_find_session_from_projects`
   - `test_node_n16_check_tmux_session_exists`
   - `test_node_n17_create_tmux_session`
   - `test_node_n18_check_process_in_tmux_exists`
   - `test_node_n19_start_claude_in_tmux`

2. **Flow Tests** - Complete end-to-end scenarios
   - `test_complete_flow_success`
   - `test_complete_flow_create_new`
   - `test_complete_flow_no_create`

3. **Error Handling Tests**
   - `test_error_handling_tmux_creation_failure`

4. **Mock Tests**
   - `test_mock_basic_operations`
   - `test_mock_error_scenarios`
   - `test_mock_session_info`

5. **Utility Tests**
   - `test_get_active_sessions`
   - `test_stop_session`
   - `test_multiple_processes_same_project`
   - `test_session_timeout_simulation`

### Running Tests
```bash
python3 -m unittest tests.test_claude_session_manager
```

## Integration Guide

### Using the Interface

1. **Implement the Interface**
   ```python
   from src.interfaces.claude_session_manager import ClaudeSessionManagerInterface

   class MySessionManager(ClaudeSessionManagerInterface):
       # Implement all required methods
   ```

2. **Using in Tests**
   ```python
   from src.interfaces.claude_session_manager import MockSessionManager

   manager = MockSessionManager()
   # Use mock methods for testing
   ```

### Real Implementation Notes

- Use `psutil` for process detection
- Handle subprocess calls for tmux operations
- Implement proper error handling for file operations
- Consider session timeouts and cleanup
- Support both existing and new session scenarios

## Example Workflow

```python
# Create manager instance
manager = ClaudeSessionManager()

# 1. Try to find existing session
session_id = manager.find_session_from_projects("/home/user/my-project")
if session_id:
    print(f"Found existing session: {session_id}")
else:
    # 2. Check if tmux session exists
    if manager.check_tmux_session("claude-session-1") == TmuxStatus.NOT_EXISTS:
        # 3. Create tmux session
        manager.create_tmux_session("claude-session-1", "claude")

    # 4. Start Claude in tmux
    success = manager.start_claude_in_tmux(
        "claude-session-1",
        "/usr/local/bin/claude"
    )

    if success:
        # 5. Get new session
        session_id = manager.get_or_create_session()
        print(f"Created new session: {session_id}")
```