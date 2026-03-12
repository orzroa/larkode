
# 导入统一异常（如果可用）
try:
    from src.exceptions import BaseAppError, handle_exception
    HAS_NEW_EXCEPTIONS = True
except ImportError:
    HAS_NEW_EXCEPTIONS = False


"""
Tmux Executor Interface

This module defines the interface for executing Claude Code commands through tmux sessions.
It handles nodes N20-N25 of the architecture:
- N20: Command sending via tmux send-keys
- N21: Waiting for Claude processing
- N22: Output capture via tmux capture-pane
- N23: ANSI character cleaning
- N24: Output formatting
- N25: Restart detection and auto-start
"""

import time
import subprocess
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

from src.utils.text_utils import clean_ansi_codes_extended


@dataclass
class TmuxExecutorConfig:
    """Configuration for tmux executor"""
    session_name: str = "ai-session"
    pane_id: str = "0"
    default_wait_time: float = 10.0
    max_wait_time: float = 300.0
    send_keys_delay: float = 0.1
    capture_buffer_size: int = 10000
    auto_restart_enabled: bool = True
    max_restart_attempts: int = 3
    restart_delay: float = 5.0


class TmuxOperationError(Exception):
    """Raised when tmux operations fail"""
    pass


class TmuxExecutorInterface(ABC):
    """Abstract interface for tmux executor operations"""

    @abstractmethod
    def send_command(self, command: str, wait_time: Optional[float] = None) -> None:
        """Send a command to the tmux session"""
        pass

    @abstractmethod
    def capture_output(self, lines: int = -1) -> str:
        """Capture output from tmux pane"""
        pass

    @abstractmethod
    def clear_buffer(self) -> None:
        """Clear the tmux pane buffer"""
        pass

    @abstractmethod
    def session_exists(self) -> bool:
        """Check if tmux session exists"""
        pass

    @abstractmethod
    def restart_session(self) -> None:
        """Restart the tmux session"""
        pass

    @abstractmethod
    def get_session_info(self) -> Dict[str, Any]:
        """Get session information"""
        pass


class MockTmuxExecutor(TmuxExecutorInterface):
    """Mock implementation for testing"""

    def __init__(self, config: TmuxExecutorConfig):
        self.config = config
        self.commands_history: List[str] = []
        self.output_buffer: List[str] = []
        self.session_active = True
        self.restart_attempts = 0
        self.restart_count = 0
        self.last_output_time = time.time()
        self._original_send_command = None

    def set_send_command_override(self, override_func):
        """Override the send_command method for testing"""
        self._original_send_command = self.send_command
        self.send_command = override_func

    def restore_send_command(self):
        """Restore original send_command method"""
        if self._original_send_command:
            self.send_command = self._original_send_command

    def send_command(self, command: str, wait_time: Optional[float] = None) -> None:
        """Mock sending command to tmux"""
        self.commands_history.append(command)
        # Simulate command being typed
        time.sleep(self.config.send_keys_delay * len(command.split()))
        # Add some mock output
        self.output_buffer.append(f"$ {command}")
        self.last_output_time = time.time()

    def capture_output(self, lines: int = -1) -> str:
        """Mock capturing output from tmux pane"""
        if not self.session_active:
            raise TmuxOperationError("Session not active")

        # Return mock output
        if lines > 0:
            output = self.output_buffer[-lines:]
        else:
            output = self.output_buffer

        # Add some mock claude response
        if output:
            if not output[-1].startswith("Claude response"):
                output.append("Claude response: This is a mock response from Claude.")
                output.append("")
        else:
            # Buffer is empty, add mock response
            output = ["Claude response: This is a mock response from Claude.", ""]

        return "\n".join(output)

    def clear_buffer(self) -> None:
        """Mock clearing tmux pane buffer"""
        self.output_buffer.clear()

    def session_exists(self) -> bool:
        """Mock checking if session exists"""
        return self.session_active

    def restart_session(self) -> None:
        """Mock restarting tmux session"""
        self.session_active = True
        self.restart_attempts += 1
        self.restart_count += 1
        self.clear_buffer()
        self.commands_history.append("Session restarted")

    def get_session_info(self) -> Dict[str, Any]:
        """Mock getting session info"""
        return {
            "session_name": self.config.session_name,
            "pane_id": self.config.pane_id,
            "active": self.session_active,
            "exists": self.session_active,
            "restart_count": self.restart_count,
            "command_count": len(self.commands_history)
        }


class TmuxExecutor(TmuxExecutorInterface):
    """Real tmux executor implementation"""

    def __init__(self, config: TmuxExecutorConfig):
        self.config = config
        self.restart_attempts = 0

    def _run_tmux_command(self, command: str, check: bool = True) -> subprocess.CompletedProcess:
        """Run a tmux command"""
        full_command = ["tmux", *command.split()]
        try:
            return subprocess.run(
                full_command,
                check=check,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e:
            raise TmuxOperationError(f"Tmux command failed: {e.stderr or e.stdout}")

    def send_command(self, command: str, wait_time: Optional[float] = None) -> None:
        """Send a command to the tmux session"""
        if not self.session_exists():
            if self.config.auto_restart_enabled:
                self.restart_session()
                self.restart_attempts += 1
            else:
                raise TmuxOperationError("Tmux session not found and auto-restart disabled")

        # Calculate wait time based on command length
        if wait_time is None:
            wait_time = min(
                self.config.default_wait_time + len(command) * 0.5,
                self.config.max_wait_time
            )

        # Send the command
        self._run_tmux_command(f"send-keys -t {self.config.session_name}:{self.config.pane_id} '{command}'")

        # Press Enter
        self._run_tmux_command(f"send-keys -t {self.config.session_name}:{self.config.pane_id} Enter")

        # Wait for processing
        time.sleep(wait_time)

    def capture_output(self, lines: int = -1) -> str:
        """Capture output from tmux pane"""
        if not self.session_exists():
            raise TmuxOperationError("Tmux session not found")

        try:
            # Capture pane content
            result = self._run_tmux_command(
                f"capture-pane -p -t {self.config.session_name}:{self.config.pane_id} -S -{lines if lines > 0 else self.config.capture_buffer_size}"
            )

            return result.stdout
        except TmuxOperationError:
            # If capture fails, try to get a smaller buffer
            try:
                result = self._run_tmux_command(
                    f"capture-pane -p -t {self.config.session_name}:{self.config.pane_id} -S -100"
                )
                return result.stdout
            except TmuxOperationError:
                raise

    def clear_buffer(self) -> None:
        """Clear the tmux pane buffer"""
        if not self.session_exists():
            return

        self._run_tmux_command(
            f"send-keys -t {self.config.session_name}:{self.config.pane_id} -R C-l"
        )
        time.sleep(0.5)  # Wait for clear to take effect

    def session_exists(self) -> bool:
        """Check if tmux session exists"""
        try:
            result = subprocess.run(
                ["tmux", "has-session", "-t", self.config.session_name],
                capture_output=True
            )
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    def restart_session(self) -> None:
        """Restart the tmux session"""
        # Kill existing session if it exists
        if self.session_exists():
            self._run_tmux_command(f"kill-session -t {self.config.session_name}")

        # Create new session
        self._run_tmux_command(f"new-session -d -s {self.config.session_name} -c $CLAUDE_CODE_DIR")

        # Wait for session to start
        time.sleep(1.0)

        # Split window if needed
        self._run_tmux_command(f"split-window -h -t {self.config.session_name}")

        # Select the first pane
        self._run_tmux_command(f"select-pane -t {self.config.session_name}:0.1")

        # Start claude in the session
        self._run_tmux_command(
            f"send-keys -t {self.config.session_name}:{self.config.pane_id} 'claude' Enter"
        )

        self.restart_attempts = 0

    def get_session_info(self) -> Dict[str, Any]:
        """Get session information"""
        try:
            if not self.session_exists():
                return {"session_name": self.config.session_name, "exists": False}

            # Get session windows and panes
            result = self._run_tmux_command("list-panes -t {session_name} -a")
            panes = result.stdout.strip().split('\n')

            # Get current pane content size
            result = self._run_tmux_command(
                f"display-message -t {self.config.session_name}:{self.config.pane_id} -p '#{{pane_width}}x#{{pane_height}}'"
            )
            size = result.stdout.strip()

            return {
                "session_name": self.config.session_name,
                "exists": True,
                "panes": len(panes),
                "current_pane_size": size,
                "restart_attempts": self.restart_attempts
            }
        except TmuxOperationError:
            return {"session_name": self.config.session_name, "exists": False}


class TmuxExecutorManager:
    """Manager for tmux executor with auto-restart capabilities"""

    def __init__(self, config: TmuxExecutorConfig):
        self.config = config
        self.executor = TmuxExecutor(config)
        self.restart_attempts = 0

    def execute_command(self, command: str, wait_time: Optional[float] = None) -> str:
        """Execute a command through tmux and return output"""
        return self._execute_command_internal(command, wait_time)

    def _execute_command_internal(self, command: str, wait_time: Optional[float] = None) -> str:
        """Internal execute command method"""
        try:
            # Send command
            self.executor.send_command(command, wait_time)

            # Capture output
            output = self.executor.capture_output()

            # Clean ANSI characters
            cleaned_output = self._clean_ansi(output)

            # Format output
            formatted_output = self._format_output(cleaned_output)

            return formatted_output

        except TmuxOperationError as e:
            if self.config.auto_restart_enabled and self.restart_attempts < self.config.max_restart_attempts:
                # Try to restart session and retry
                time.sleep(self.config.restart_delay)
                self.executor.restart_session()
                self.restart_attempts += 1
                # Try to capture output again
                try:
                    output = self.executor.capture_output()
                    cleaned_output = self._clean_ansi(output)
                    return self._format_output(cleaned_output)
                except TmuxOperationError:
                    # If it still fails, raise
                    raise
            else:
                raise

    def _clean_ansi(self, text: str) -> str:
        """Remove ANSI escape sequences from text"""
        return clean_ansi_codes_extended(text)

    def _format_output(self, output: str) -> str:
        """Format output for display"""
        # Remove empty lines at the beginning
        lines = output.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)

        # Truncate if too long
        max_lines = 100
        if len(lines) > max_lines:
            lines = lines[-max_lines:]
            lines.append("\n... (output truncated)")

        # Join back
        formatted = '\n'.join(lines)

        # Limit length
        max_length = 5000
        if len(formatted) > max_length:
            formatted = formatted[:max_length] + "\n... (output truncated)"

        return formatted

    def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        info = self.executor.get_session_info()
        info["restart_attempts"] = self.restart_attempts
        return info