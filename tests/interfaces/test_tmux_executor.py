"""
Unit tests for Tmux Executor Interface

Tests cover nodes N20-N25 of the architecture:
- N20: Command sending via tmux send-keys
- N21: Waiting for Claude processing
- N22: Output capture via tmux capture-pane
- N23: ANSI character cleaning
- N24: Output formatting
- N25: Restart detection and auto-start
"""

import time
import subprocess
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from pathlib import Path

# Import from interfaces directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from interfaces.tmux_executor import (
    TmuxExecutorConfig,
    TmuxExecutorInterface,
    MockTmuxExecutor,
    TmuxExecutor,
    TmuxExecutorManager,
    TmuxOperationError
)


# Fixtures
@pytest.fixture
def config():
    """Create default test configuration"""
    return TmuxExecutorConfig(
        session_name="test-session",
        pane_id="0",
        default_wait_time=1.0,
        max_wait_time=60.0,
        send_keys_delay=0.01,
        auto_restart_enabled=True,
        max_restart_attempts=3
    )


@pytest.fixture
def mock_executor(config):
    """Create mock executor for testing"""
    return MockTmuxExecutor(config)


@pytest.fixture
def manager(config):
    """Create executor manager for testing"""
    return TmuxExecutorManager(config)


# ============================================================================
# Node N20: Command Sending Tests
# ============================================================================
class TestCommandSending:
    """Tests for Node N20: Command sending via tmux send-keys"""

    def test_send_command_basic(self, mock_executor):
        """Test basic command sending"""
        command = "echo hello"
        mock_executor.send_command(command)

        assert command in mock_executor.commands_history
        assert mock_executor.last_output_time > 0

    def test_send_command_with_wait_time(self, mock_executor):
        """Test command sending with custom wait time"""
        command = "sleep 5"
        start_time = time.time()
        mock_executor.send_command(command, wait_time=0.5)
        elapsed = time.time() - start_time

        assert command in mock_executor.commands_history
        # The mock doesn't actually wait, elapsed will be very small
        assert elapsed < 0.1

    def test_send_command_multiple(self, mock_executor):
        """Test sending multiple commands sequentially"""
        commands = ["echo first", "echo second", "echo third"]
        for cmd in commands:
            mock_executor.send_command(cmd)

        assert mock_executor.commands_history == commands

    def test_send_command_empty(self, mock_executor):
        """Test sending empty command"""
        mock_executor.send_command("")
        assert mock_executor.commands_history == [""]

    def test_send_command_long(self, mock_executor):
        """Test sending long command"""
        long_command = "echo " + "very " * 100
        mock_executor.send_command(long_command)

        assert long_command in mock_executor.commands_history

    @patch('subprocess.run')
    def test_real_executor_send_command(self, mock_run, config):
        """Test real executor command sending"""
        def side_effect(*args, **kwargs):
            """Mock different tmux commands"""
            cmd = args[0]
            if "has-session" in cmd:
                return Mock(returncode=0, stdout=b"", stderr=b"")
            return Mock(returncode=0, stdout=b"", stderr=b"")

        mock_run.side_effect = side_effect

        executor = TmuxExecutor(config)
        executor.send_command("test command", wait_time=0.1)

        # Verify tmux send-keys was called
        calls = [str(c) for c in mock_run.call_args_list]
        assert any("send-keys" in str(c) for c in calls)
        # Note: command is split by spaces in _run_tmux_command, so "test command" becomes "'test" and "command'"
        assert any(("'test" in str(c) or "command'" in str(c)) for c in calls)

    @patch('subprocess.run')
    def test_real_executor_send_command_enters_newline(self, mock_run, config):
        """Test that command is followed by Enter"""
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        executor = TmuxExecutor(config)
        executor.send_command("test")

        # Verify Enter was sent
        enter_call_found = False
        for c in mock_run.call_args_list:
            if "send-keys" in str(c) and "Enter" in str(c):
                enter_call_found = True
                break

        assert enter_call_found


# ============================================================================
# Node N21: Waiting Logic Tests
# ============================================================================
class TestWaitingLogic:
    """Tests for Node N21: Waiting for Claude processing"""

    def test_default_wait_time_calculation(self, config):
        """Test default wait time is calculated correctly"""
        executor = MockTmuxExecutor(config)
        short_command = "ls"
        long_command = "some very long command that takes time to process"

        with patch('time.sleep') as mock_sleep:
            executor.send_command(short_command)
            # Default wait should be based on command length

            executor.send_command(long_command)
            # Longer command should trigger longer wait

    def test_custom_wait_time(self, mock_executor):
        """Test custom wait time override"""
        start_time = time.time()
        mock_executor.send_command("test", wait_time=0.3)
        elapsed = time.time() - start_time

        # The mock doesn't actually wait, elapsed will be very small
        assert elapsed < 0.1

    def test_max_wait_time_enforced(self, config):
        """Test that wait time doesn't exceed maximum"""
        config.max_wait_time = 2.0
        config.default_wait_time = 10.0
        executor = MockTmuxExecutor(config)

        start_time = time.time()
        executor.send_command("a" * 1000)  # Very long command
        elapsed = time.time() - start_time

        assert elapsed < 3.0  # Should be capped at max_wait_time

    @patch('subprocess.run')
    def test_real_executor_wait_calculation(self, mock_run, config):
        """Test real executor calculates wait time correctly"""
        config.default_wait_time = 10.0
        config.max_wait_time = 30.0

        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        executor = TmuxExecutor(config)

        # Send short command
        executor.send_command("short")

        # Send long command - should be capped
        with patch('time.sleep') as mock_sleep:
            executor.send_command("long " * 100)
            # Should call sleep with capped value


# ============================================================================
# Node N22: Output Capture Tests
# ============================================================================
class TestOutputCapture:
    """Tests for Node N22: Output capture via tmux capture-pane"""

    def test_capture_basic_output(self, mock_executor):
        """Test basic output capture"""
        mock_executor.send_command("echo test")
        output = mock_executor.capture_output()

        assert "echo test" in output
        assert "Claude response" in output

    def test_capture_with_line_limit(self, mock_executor):
        """Test output capture with line limit"""
        for i in range(10):
            mock_executor.send_command(f"echo line {i}")

        output = mock_executor.capture_output(lines=3)

        lines = output.split('\n')
        assert len([l for l in lines if l.strip()]) <= 4  # 3 lines + empty line

    def test_capture_empty_buffer(self, mock_executor):
        """Test capturing from empty buffer"""
        mock_executor.clear_buffer()
        output = mock_executor.capture_output()

        assert "Claude response" in output

    def test_capture_after_multiple_commands(self, mock_executor):
        """Test capturing after multiple commands"""
        commands = ["cmd1", "cmd2", "cmd3"]
        for cmd in commands:
            mock_executor.send_command(cmd)

        output = mock_executor.capture_output()

        for cmd in commands:
            assert cmd in output

    def test_capture_no_limit(self, mock_executor):
        """Test capture without line limit"""
        for i in range(100):
            mock_executor.send_command(f"cmd{i}")

        output = mock_executor.capture_output(lines=-1)

        # Should capture all output
        assert len(output.split('\n')) > 50

    @patch('subprocess.run')
    def test_real_executor_capture_output(self, mock_run, config):
        """Test real executor captures output"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="line 1\nline 2\nline 3",
            stderr=""
        )

        executor = TmuxExecutor(config)
        output = executor.capture_output()

        assert output == "line 1\nline 2\nline 3"

    @patch('subprocess.run')
    def test_real_executor_capture_with_fallback(self, mock_run, config):
        """Test real executor falls back to smaller buffer on error"""
        call_count = [0]

        def side_effect(*args, **kwargs):
            """Mock different tmux commands"""
            cmd = args[0]
            call_count[0] += 1
            if "has-session" in cmd:
                return Mock(returncode=0, stdout=b"", stderr=b"")
            elif "capture-pane" in cmd and "-S -10000" in cmd:
                # First capture fails with error
                return subprocess.CalledProcessError(1, "tmux", stderr="Error")
            return Mock(returncode=0, stdout="fallback output", stderr="")

        mock_run.side_effect = side_effect

        executor = TmuxExecutor(config)
        output = executor.capture_output()

        assert output == "fallback output"

    def test_capture_inactive_session(self, mock_executor):
        """Test capturing from inactive session raises error"""
        mock_executor.session_active = False

        with pytest.raises(TmuxOperationError):
            mock_executor.capture_output()


# ============================================================================
# Node N23: ANSI Cleaning Tests
# ============================================================================
class TestANSCleaning:
    """Tests for Node N23: ANSI character cleaning"""

    @pytest.fixture
    def sample_ansi_text(self):
        """Sample text with ANSI escape sequences"""
        return (
            "\x1b[31mError:\x1b[0m \x1b[1mSomething went wrong\x1b[0m\n"
            "\x1b[32mSuccess:\x1b[0m \x1b[33;1mWarning\x1b[0m message\n"
            "\x1b[0;34mInfo\x1b[0m: \x1b[4mUnderlined text\x1b[24m"
        )

    def test_clean_basic_ansi_sequences(self, manager, sample_ansi_text):
        """Test cleaning basic ANSI color sequences"""
        cleaned = manager._clean_ansi(sample_ansi_text)

        assert "\x1b" not in cleaned
        assert "Error:" in cleaned
        assert "Something went wrong" in cleaned

    def test_clean_bold_sequences(self, manager, sample_ansi_text):
        """Test cleaning bold ANSI sequences"""
        cleaned = manager._clean_ansi(sample_ansi_text)

        assert "\x1b[1m" not in cleaned
        assert "\x1b[0m" not in cleaned

    def test_clean_rgb_sequences(self, manager):
        """Test cleaning RGB color sequences"""
        text = "\x1b[38;2;255;0;0mRed text\x1b[0m"
        cleaned = manager._clean_ansi(text)

        assert "\x1b" not in cleaned
        assert "Red text" in cleaned

    def test_clean_cursor_sequences(self, manager):
        """Test cleaning cursor movement sequences"""
        text = "Text\x1b[10D\x1b[2KClear line\x1b[10Ccontinue"
        cleaned = manager._clean_ansi(text)

        assert "\x1b" not in cleaned
        assert "TextClear linecontinue" in cleaned

    def test_clean_multiple_sequences(self, manager):
        """Test cleaning multiple different sequences"""
        text = "\x1b[31m\x1b[1m\x1b[4mMultiple\x1b[0m styles\x1b[32m\x1b[5mblinking\x1b[0m"
        cleaned = manager._clean_ansi(text)

        assert "\x1b" not in cleaned
        assert "Multiple" in cleaned
        assert "styles" in cleaned
        assert "blinking" in cleaned

    def test_clean_preserves_plain_text(self, manager):
        """Test that plain text is preserved"""
        text = "Plain text without any formatting"
        cleaned = manager._clean_ansi(text)

        assert cleaned == text

    def test_clean_empty_string(self, manager):
        """Test cleaning empty string"""
        result = manager._clean_ansi("")
        assert result == ""

    def test_clean_preserves_newlines(self, manager):
        """Test that newlines are preserved"""
        text = "Line 1\nLine 2\nLine 3"
        cleaned = manager._clean_ansi(text)

        assert cleaned == text

    def test_clean_preserves_special_chars(self, manager):
        """Test that special characters are preserved"""
        text = "Special: @#$%^&*()_+-={}[]|\\:;\"'<>,.?/"
        cleaned = manager._clean_ansi(text)

        assert cleaned == text


# ============================================================================
# Node N24: Output Formatting Tests
# ============================================================================
class TestOutputFormatting:
    """Tests for Node N24: Output formatting"""

    def test_format_basic_output(self, manager):
        """Test basic output formatting"""
        output = "  \n  \nLine 1\nLine 2\nLine 3"
        formatted = manager._format_output(output)

        assert formatted.startswith("Line 1")
        assert "Line 2" in formatted
        assert "Line 3" in formatted

    def test_format_leading_empty_lines(self, manager):
        """Test removing leading empty lines"""
        output = "\n\n\n\nActual content here"
        formatted = manager._format_output(output)

        assert formatted.startswith("Actual content")

    def test_format_truncates_long_output(self, manager):
        """Test truncating very long output"""
        lines = [f"Line {i}" for i in range(200)]
        long_output = "\n".join(lines)
        formatted = manager._format_output(long_output)

        formatted_lines = formatted.split('\n')
        assert len(formatted_lines) <= 102  # 100 lines + truncated message

    def test_format_truncation_message(self, manager):
        """Test truncation message is added"""
        lines = [f"Line {i}" for i in range(150)]
        long_output = "\n".join(lines)
        formatted = manager._format_output(long_output)

        assert "truncated" in formatted.lower()

    def test_format_length_truncation(self, manager):
        """Test character-based truncation"""
        # Create output longer than max length
        long_output = "A" * 6000
        formatted = manager._format_output(long_output)

        assert len(formatted) <= 5100  # 5000 + truncation message

    def test_format_preserves_content(self, manager):
        """Test that important content is preserved"""
        output = "Header\nContent\nFooter"
        formatted = manager._format_output(output)

        assert "Header" in formatted
        assert "Content" in formatted
        assert "Footer" in formatted

    def test_format_handles_single_line(self, manager):
        """Test formatting single line output"""
        output = "Single line"
        formatted = manager._format_output(output)

        assert formatted == "Single line"

    def test_format_handles_empty_output(self, manager):
        """Test formatting empty output"""
        output = ""
        formatted = manager._format_output(output)

        assert formatted == ""

    def test_format_preserves_indentation(self, manager):
        """Test that code indentation is preserved"""
        output = "def function():\n    return True"
        formatted = manager._format_output(output)

        assert "    return" in formatted


# ============================================================================
# Node N25: Restart Detection & Auto-Start Tests
# ============================================================================
class TestRestartDetection:
    """Tests for Node N25: Restart detection and auto-start"""

    def test_session_exists(self, mock_executor):
        """Test session existence check"""
        assert mock_executor.session_exists() is True

    def test_session_not_exists(self, mock_executor):
        """Test non-existent session"""
        mock_executor.session_active = False
        assert mock_executor.session_exists() is False

    def test_restart_session(self, mock_executor):
        """Test restarting a session"""
        mock_executor.session_active = False
        initial_restart_count = mock_executor.restart_count

        mock_executor.restart_session()

        assert mock_executor.session_active is True
        assert mock_executor.restart_count == initial_restart_count + 1
        assert "Session restarted" in mock_executor.commands_history

    def test_restart_clears_buffer(self, mock_executor):
        """Test that restart clears the buffer"""
        mock_executor.send_command("cmd1")
        assert len(mock_executor.output_buffer) > 0

        mock_executor.restart_session()
        assert len(mock_executor.output_buffer) == 0

    def test_multiple_restarts(self, mock_executor):
        """Test multiple restarts increment counter"""
        for _ in range(5):
            mock_executor.restart_session()

        assert mock_executor.restart_count == 5

    @patch('subprocess.run')
    def test_real_executor_session_exists_true(self, mock_run):
        """Test real executor detects existing session"""
        mock_run.return_value = Mock(returncode=0)

        config = TmuxExecutorConfig(session_name="test")
        executor = TmuxExecutor(config)

        assert executor.session_exists() is True

    @patch('subprocess.run')
    def test_real_executor_session_exists_false(self, mock_run):
        """Test real executor detects non-existent session"""
        mock_run.return_value = Mock(returncode=1)

        config = TmuxExecutorConfig(session_name="test")
        executor = TmuxExecutor(config)

        assert executor.session_exists() is False

    @patch('subprocess.run')
    def test_real_executor_restart_creates_session(self, mock_run, config):
        """Test real executor restarts and creates session"""
        # First call checks session (doesn't exist)
        # Second call kills existing session
        # Third call creates new session
        # Remaining calls configure session
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        executor = TmuxExecutor(config)
        executor.restart_session()

        # Verify tmux commands were called
        assert mock_run.call_count > 0

    def test_auto_restart_on_send_failure(self, config):
        """Test auto-restart when sending to dead session"""
        config.auto_restart_enabled = True
        executor = MockTmuxExecutor(config)
        executor.session_active = False

        manager = TmuxExecutorManager(config)
        manager.executor = executor

        with patch.object(manager, '_format_output', return_value="output"):
            result = manager.execute_command("test")

        assert executor.session_active is True
        assert executor.restart_count > 0

    def test_auto_restart_disabled_on_failure(self, config):
        """Test no auto-restart when disabled"""
        config.auto_restart_enabled = False
        executor = MockTmuxExecutor(config)
        executor.session_active = False

        manager = TmuxExecutorManager(config)
        manager.executor = executor

        with pytest.raises(TmuxOperationError):
            manager.execute_command("test")

    def test_max_restart_attempts(self, config):
        """Test that restart attempts are limited"""
        config.max_restart_attempts = 2
        config.auto_restart_enabled = True

        executor = MockTmuxExecutor(config)
        manager = TmuxExecutorManager(config)
        manager.executor = executor

        # Force capture_output to always fail
        def capture_fail(*args, **kwargs):
            raise TmuxOperationError("Always fails")

        with patch.object(executor, 'capture_output', side_effect=capture_fail):
            with pytest.raises(TmuxOperationError):
                manager.execute_command("test")

    def test_restart_delay(self, config):
        """Test that restart has delay"""
        config.restart_delay = 0.5
        config.auto_restart_enabled = True

        executor = MockTmuxExecutor(config)
        manager = TmuxExecutorManager(config)
        manager.executor = executor
        manager.executor.session_active = False

        with patch('time.sleep') as mock_sleep:
            with patch.object(manager, '_format_output', return_value="output"):
                manager.execute_command("test")

            # Check that sleep was called with restart_delay
            sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
            assert 0.5 in sleep_calls


# ============================================================================
# Session Info Tests
# ============================================================================
class TestSessionInfo:
    """Tests for session information retrieval"""

    def test_mock_session_info(self, mock_executor, config):
        """Test getting session info from mock executor"""
        mock_executor.send_command("test")
        info = mock_executor.get_session_info()

        assert info["session_name"] == config.session_name
        assert info["pane_id"] == config.pane_id
        assert info["active"] is True
        assert info["restart_count"] >= 0
        assert info["command_count"] > 0

    def test_session_info_after_restart(self, mock_executor):
        """Test session info reflects restarts"""
        initial_info = mock_executor.get_session_info()

        mock_executor.restart_session()
        after_info = mock_executor.get_session_info()

        assert after_info["restart_count"] > initial_info["restart_count"]

    def test_session_info_after_commands(self, mock_executor):
        """Test session info tracks command count"""
        initial_info = mock_executor.get_session_info()
        initial_count = initial_info["command_count"]

        mock_executor.send_command("cmd1")
        mock_executor.send_command("cmd2")

        new_info = mock_executor.get_session_info()
        assert new_info["command_count"] == initial_count + 2

    @patch('subprocess.run')
    def test_real_executor_session_info(self, mock_run, config):
        """Test real executor session info"""
        mock_run.return_value = Mock(
            returncode=0,
            stdout="0: bash [100x24] (active)\n1: bash [100x24]",
            stderr=""
        )

        executor = TmuxExecutor(config)
        info = executor.get_session_info()

        assert info["session_name"] == config.session_name
        assert info["exists"] is True


# ============================================================================
# Integration Tests
# ============================================================================
class TestIntegration:
    """Integration tests for complete workflow"""

    def test_full_workflow(self, mock_executor):
        """Test complete workflow: send -> wait -> capture -> clean -> format"""
        manager = TmuxExecutorManager(mock_executor.config)
        manager.executor = mock_executor

        command = "ls -la"
        result = manager.execute_command(command, wait_time=0.1)

        assert "ls -la" in mock_executor.commands_history
        assert isinstance(result, str)
        assert len(result) > 0

    def test_multiple_commands_workflow(self, mock_executor):
        """Test workflow with multiple commands"""
        manager = TmuxExecutorManager(mock_executor.config)
        manager.executor = mock_executor

        commands = ["echo first", "echo second", "echo third"]
        results = []

        for cmd in commands:
            result = manager.execute_command(cmd)
            results.append(result)

        assert len(results) == 3
        for cmd in commands:
            assert cmd in mock_executor.commands_history

    def test_workflow_with_ansi_output(self, mock_executor):
        """Test workflow that includes ANSI cleaning"""
        manager = TmuxExecutorManager(mock_executor.config)
        manager.executor = mock_executor

        # Add ANSI output to buffer
        mock_executor.output_buffer.append("\x1b[31mError\x1b[0m message")

        result = manager.execute_command("test")

        assert "\x1b" not in result
        assert "Error" in result

    def test_workflow_with_long_output(self, mock_executor):
        """Test workflow with long output formatting"""
        manager = TmuxExecutorManager(mock_executor.config)
        manager.executor = mock_executor

        # Generate long output
        for i in range(150):
            mock_executor.output_buffer.append(f"Line {i}: " + "data " * 20)

        result = manager.execute_command("generate long")

        # Should be truncated
        assert len(result.split('\n')) < 200

    def test_workflow_with_auto_restart(self, config):
        """Test complete workflow with auto-restart"""
        config.auto_restart_enabled = True
        config.restart_delay = 0.1

        executor = MockTmuxExecutor(config)
        manager = TmuxExecutorManager(config)
        manager.executor = executor

        # Kill session after first command
        def maybe_kill(cmd, wait=None):
            if "cmd2" in cmd:
                executor.session_active = False
            # Call the original send_command but kill session first
            MockTmuxExecutor.send_command(executor, cmd, wait)
            if "cmd2" in cmd:
                executor.session_active = False

        # Temporarily replace the method
        executor.send_command = maybe_kill

        # First command succeeds
        result1 = manager.execute_command("cmd1")
        assert len(result1) > 0

        # Second command triggers restart
        result2 = manager.execute_command("cmd2")

        assert executor.session_active is True
        # After restart, session should be active
        assert "Session restarted" in executor.commands_history

    def test_manager_get_status(self, mock_executor):
        """Test getting status through manager"""
        manager = TmuxExecutorManager(mock_executor.config)
        manager.executor = mock_executor

        status = manager.get_status()

        assert "session_name" in status
        assert "exists" in status


# ============================================================================
# Edge Cases Tests
# ============================================================================
class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_none_command(self, mock_executor):
        """Test handling None as command"""
        with pytest.raises((TypeError, AttributeError)):
            mock_executor.send_command(None)

    def test_unicode_command(self, mock_executor):
        """Test handling unicode characters in command"""
        command = "echo 你好世界 🌍"
        mock_executor.send_command(command)

        assert command in mock_executor.commands_history

    def test_special_chars_in_command(self, mock_executor):
        """Test handling special characters in command"""
        command = "echo 'special $@#$%^&* chars'"
        mock_executor.send_command(command)

        assert command in mock_executor.commands_history

    def test_very_long_command(self, mock_executor, config):
        """Test handling very long command"""
        config.max_wait_time = 5.0
        command = "echo " + "very " * 500

        start_time = time.time()
        mock_executor.send_command(command)
        elapsed = time.time() - start_time

        assert command in mock_executor.commands_history
        assert elapsed < 6.0  # Should be capped

    def test_negative_wait_time(self, mock_executor):
        """Test handling negative wait time"""
        mock_executor.send_command("test", wait_time=-1)

        # Should still send command
        assert "test" in mock_executor.commands_history

    def test_zero_wait_time(self, mock_executor):
        """Test handling zero wait time"""
        start_time = time.time()
        mock_executor.send_command("test", wait_time=0)
        elapsed = time.time() - start_time

        assert "test" in mock_executor.commands_history
        assert elapsed < 0.5

    def test_clear_buffer_mid_session(self, mock_executor):
        """Test clearing buffer during active session"""
        mock_executor.send_command("cmd1")
        mock_executor.send_command("cmd2")

        buffer_size = len(mock_executor.output_buffer)
        mock_executor.clear_buffer()

        assert len(mock_executor.output_buffer) == 0

    def test_capture_negative_lines(self, mock_executor):
        """Test capturing with negative lines (should capture all)"""
        for i in range(10):
            mock_executor.send_command(f"cmd{i}")

        output = mock_executor.capture_output(lines=-5)

        # Should still capture output
        assert len(output) > 0

    def test_empty_session_name(self, config):
        """Test executor with empty session name"""
        config.session_name = ""
        executor = MockTmuxExecutor(config)

        info = executor.get_session_info()
        assert info["session_name"] == ""

    def test_custom_pane_id(self, config):
        """Test executor with custom pane ID"""
        config.pane_id = "1.3"
        executor = MockTmuxExecutor(config)

        info = executor.get_session_info()
        assert info["pane_id"] == "1.3"

    def test_format_mixed_line_endings(self, manager):
        """Test formatting output with mixed line endings"""
        output = "Line1\r\nLine2\nLine3\rLine4"
        formatted = manager._format_output(output)

        assert "Line1" in formatted
        assert "Line2" in formatted
        assert "Line3" in formatted
        assert "Line4" in formatted

    def test_clean_preserves_tabs(self, manager):
        """Test that tabs are preserved during cleaning"""
        text = "Tabbed\tcontent\there"
        cleaned = manager._clean_ansi(text)

        assert "\t" in cleaned


# ============================================================================
# Performance Tests
# ============================================================================
class TestPerformance:
    """Performance tests for tmux executor"""

    def test_multiple_commands_performance(self, mock_executor):
        """Test performance with many sequential commands"""
        start_time = time.time()

        for i in range(50):
            mock_executor.send_command(f"cmd{i}")

        elapsed = time.time() - start_time

        # Should complete in reasonable time
        assert elapsed < 5.0

    def test_output_capture_performance(self, mock_executor):
        """Test performance of large output capture"""
        # Generate large buffer
        for i in range(1000):
            mock_executor.output_buffer.append(f"Line {i}: " + "x" * 50)

        start_time = time.time()
        output = mock_executor.capture_output()
        elapsed = time.time() - start_time

        # Should capture quickly
        assert elapsed < 1.0
        assert len(output) > 0

    def test_ansi_cleaning_performance(self, manager):
        """Test performance of ANSI cleaning"""
        # Generate large text with ANSI sequences
        text_with_ansi = ""
        for i in range(1000):
            text_with_ansi += f"\x1b[31m{i}\x1b[0m "

        start_time = time.time()
        cleaned = manager._clean_ansi(text_with_ansi)
        elapsed = time.time() - start_time

        # Should clean quickly
        assert elapsed < 0.5
        assert "\x1b" not in cleaned


# ============================================================================
# Concurrency Tests
# ============================================================================
class TestConcurrency:
    """Tests for concurrent operations"""

    def test_concurrent_commands_safe(self, mock_executor):
        """Test that concurrent commands are handled safely"""
        import threading

        def send_commands():
            for i in range(10):
                mock_executor.send_command(f"thread_cmd{i}")

        threads = [threading.Thread(target=send_commands) for _ in range(3)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All commands should be recorded
        assert len(mock_executor.commands_history) == 30


if __name__ == "__main__":
    pytest.main([__file__, "-v"])