# Tmux Executor Implementation

## Overview

The tmux executor implementation provides a complete interface for executing Claude Code commands through tmux sessions. It handles nodes N20-N25 of the architecture as specified in the requirements.

## Files Created

### 1. `/src/interfaces/tmux_executor.py`

The main interface file containing:
- **TmuxExecutorConfig**: Configuration class for tmux executor settings
- **TmuxExecutorInterface**: Abstract interface defining all tmux operations
- **MockTmuxExecutor**: Mock implementation for testing
- **TmuxExecutor**: Real implementation using subprocess calls to tmux
- **TmuxExecutorManager**: High-level manager with auto-restart capabilities

### 2. `/tests/test_tmux_executor.py`

Comprehensive unit tests covering:
- **Command sending (Node N20)**
- **Waiting logic (Node N21)**
- **Output capture (Node N22)**
- **ANSI cleaning (Node N23)**
- **Output formatting (Node N24)**
- **Restart detection (Node N25)**
- **Integration tests**
- **Edge cases**
- **Performance tests**
- **Concurrency tests**

### 3. `/tests/test_data.py`

Test data constants including:
- Sample commands
- ANSI sequences
- Realistic tmux output examples

### 4. `/run_tmux_tests.sh`

Test runner script for executing the test suite.

## Architecture Implementation

### Node N20: Command Sending
- **Method**: `send_command()` in TmuxExecutor
- **Implementation**: Uses `tmux send-keys` to send commands to the session
- **Features**:
  - Automatic Enter key sending
  - Command history tracking
  - Line delay calculation based on command length

### Node N21: Waiting Logic
- **Implementation**:
  - Default wait time: 10 seconds + 0.5s per command word
  - Maximum wait time: 300 seconds (configurable)
  - Custom wait time override option
- **Features**:
  - Calculates appropriate wait time based on command complexity
  - Ensures commands have time to process before capturing output

### Node N22: Output Capture
- **Method**: `capture_output()` in TmuxExecutor
- **Implementation**: Uses `tmux capture-pane` to get pane content
- **Features**:
  - Line limit support for efficient capture
  - Fallback mechanism for capture errors
  - Buffer clearing support

### Node N23: ANSI Cleaning
- **Method**: `_clean_ansi()` in TmuxExecutorManager
- **Implementation**: Regex-based removal of ANSI escape sequences
- **Handles**:
  - Color codes (32m, 33m, 1m, etc.)
  - Style codes (bold, italic, underline)
  - Cursor movements
  - RGB color codes
  - All preserving the underlying text content

### Node N24: Output Formatting
- **Method**: `_format_output()` in TmuxExecutorManager
- **Features**:
  - Removes leading empty lines
  - Truncates long output (100 lines or 5000 characters)
  - Preserves indentation and formatting
  - Adds truncation message when needed

### Node N25: Restart Detection & Auto-Start
- **Features**:
  - Automatic session detection (`tmux has-session`)
  - Session restart with `tmux new-session`
  - Configuration-controlled auto-restart
  - Maximum restart attempts limit
  - Restart delay to prevent rapid cycling

## Key Classes

### TmuxExecutorConfig
```python
@dataclass
class TmuxExecutorConfig:
    session_name: str = "claude-session"
    pane_id: str = "0"
    default_wait_time: float = 10.0
    max_wait_time: float = 300.0
    send_keys_delay: float = 0.1
    capture_buffer_size: int = 10000
    auto_restart_enabled: bool = True
    max_restart_attempts: int = 3
    restart_delay: float = 5.0
```

### TmuxExecutorManager (Main Interface)
```python
class TmuxExecutorManager:
    def execute_command(command: str, wait_time: Optional[float] = None) -> str:
        """Execute a complete command through tmux"""

    def get_status() -> Dict[str, Any]:
        """Get current session status"""
```

## Testing

The test suite includes:
- **66 tests** covering all aspects of the implementation
- **Mock implementations** for isolated testing
- **Integration tests** for complete workflow validation
- **Performance tests** for high load scenarios
- **Edge case tests** for robust error handling

## Usage Example

```python
from interfaces.tmux_executor import TmuxExecutorConfig, TmuxExecutorManager

# Configuration
config = TmuxExecutorConfig(
    session_name="my-claude-session",
    auto_restart_enabled=True
)

# Create manager
manager = TmuxExecutorManager(config)

# Execute command
result = manager.execute_command("ls -la", wait_time=5.0)

# Get status
status = manager.get_status()
```

## Run Tests

```bash
# Run all tests
./run_tmux_tests.sh

# Or directly with pytest
python3 -m pytest tests/test_tmux_executor.py -v
```

## Mock Testing

The MockTmuxExecutor provides a testing environment that:
- Tracks command history
- Simulates realistic output
- Allows session state manipulation
- Supports test-specific method overrides

## Security Considerations

- Uses subprocess with direct command execution
- No shell interpolation for command parameters
- Input validation through type hints
- Safe ANSI sequence removal
- Configurable timeouts prevent hanging

## Performance

- Minimal overhead for command execution
- Efficient ANSI cleaning using compiled regex
- Smart output truncation for large responses
- Concurrent command support for multi-threaded environments