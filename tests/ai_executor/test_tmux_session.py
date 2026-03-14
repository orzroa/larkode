"""
测试 Tmux 会话管理器
"""
import pytest
import asyncio
import subprocess
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestTmuxSessionManagerInit:
    """测试 TmuxSessionManager 初始化"""

    @pytest.fixture
    def mock_settings(self):
        """创建模拟的 settings"""
        settings = Mock()
        settings.AI_ASSISTANT_TYPE = "claude_code"
        settings.CLAUDE_CODE_CLI_PATH = "claude"
        settings.CLAUDE_CODE_WORKSPACE_DIR = Path("/test/workspace")
        settings.TMUX_SESSION_NAME = "cc"
        settings.IFLOW_CLI = "iflow"
        settings.IFLOW_DIR = Path("/test/iflow")
        settings.get_process_name = Mock(return_value="claude")
        return settings

    def test_init_claude_code(self, mock_settings):
        """测试 Claude Code 模式初始化"""
        from src.ai_executor.tmux_session import TmuxSessionManager
        with patch('src.ai_executor.tmux_session.get_settings', return_value=mock_settings):
            with patch.object(TmuxSessionManager, '_log_debug_info', return_value=None):
                manager = TmuxSessionManager()

                assert manager._cli_path == "claude"
                assert manager.workspace == Path("/test/workspace")
                assert manager._tmux_session == "cc"

    def test_init_iflow_mode(self, mock_settings):
        """测试 iFlow 模式初始化"""
        mock_settings.AI_ASSISTANT_TYPE = "iflow"

        from src.ai_executor.tmux_session import TmuxSessionManager
        with patch('src.ai_executor.tmux_session.get_settings', return_value=mock_settings):
            with patch.object(TmuxSessionManager, '_log_debug_info', return_value=None):
                manager = TmuxSessionManager()

                assert manager._cli_path == "iflow"
                assert manager.workspace == Path("/test/iflow")

    def test_init_with_custom_workspace(self, mock_settings):
        """测试自定义工作目录"""
        custom_workspace = Path("/custom/workspace")

        from src.ai_executor.tmux_session import TmuxSessionManager
        with patch('src.ai_executor.tmux_session.get_settings', return_value=mock_settings):
            with patch.object(TmuxSessionManager, '_log_debug_info', return_value=None):
                manager = TmuxSessionManager(workspace=custom_workspace)

                assert manager.workspace == custom_workspace


class TestCheckTmuxSession:
    """测试 _check_tmux_session 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    def test_session_exists(self, manager):
        """测试 session 存在"""
        mock_result = Mock()
        mock_result.stdout = "cc\nother_session"

        with patch('subprocess.run', return_value=mock_result):
            result = manager._check_tmux_session()
            assert result is True

    def test_session_not_exists(self, manager):
        """测试 session 不存在"""
        mock_result = Mock()
        mock_result.stdout = "other_session"

        with patch('subprocess.run', return_value=mock_result):
            result = manager._check_tmux_session()
            assert result is False

    def test_check_session_exception(self, manager):
        """测试检查 session 异常"""
        with patch('subprocess.run', side_effect=Exception("tmux error")):
            result = manager._check_tmux_session()
            assert result is False


class TestCheckAIRunningInSession:
    """测试 _check_ai_running_in_session 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    def test_ai_running_found(self, manager):
        """测试找到运行中的 AI 进程"""
        mock_result = Mock()
        mock_result.stdout = "12345\n"
        mock_result.returncode = 0

        mock_proc = Mock()
        mock_proc.children.return_value = []
        mock_proc.pid = 12345

        with patch('subprocess.run', return_value=mock_result):
            with patch('psutil.Process', return_value=mock_proc):
                result = manager._check_ai_running_in_session()
                # 没有子进程，返回 False
                assert result is False

    def test_ai_running_no_pane(self, manager):
        """测试没有 pane"""
        mock_result = Mock()
        mock_result.stdout = ""

        with patch('subprocess.run', return_value=mock_result):
            result = manager._check_ai_running_in_session()
            assert result is False

    def test_ai_running_subprocess_error(self, manager):
        """测试 subprocess 错误"""
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "tmux")):
            result = manager._check_ai_running_in_session()
            assert result is False

    def test_ai_running_exception(self, manager):
        """测试异常处理"""
        with patch('subprocess.run', side_effect=Exception("error")):
            result = manager._check_ai_running_in_session()
            assert result is False


class TestCreateTmuxSession:
    """测试 _create_tmux_session 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    def test_create_session_success(self, manager):
        """测试成功创建 session"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            with patch('time.sleep'):
                result = manager._create_tmux_session()
                assert result is True

    def test_create_session_failure(self, manager):
        """测试创建 session 失败"""
        with patch('subprocess.run', side_effect=Exception("tmux error")):
            result = manager._create_tmux_session()
            assert result is False


class TestEnsureTmuxSession:
    """测试 _ensure_tmux_session 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    def test_ensure_session_exists_and_running(self, manager):
        """测试 session 存在且 AI 运行中"""
        with patch.object(manager, '_check_tmux_session', return_value=True):
            with patch.object(manager, '_check_ai_running_in_session', return_value=True):
                success, just_started = manager._ensure_tmux_session()
                assert success is True
                assert just_started is False

    def test_ensure_session_not_exists(self, manager):
        """测试 session 不存在"""
        with patch.object(manager, '_check_tmux_session', return_value=False):
            with patch.object(manager, '_create_tmux_session', return_value=True):
                success, just_started = manager._ensure_tmux_session()
                assert success is True
                assert just_started is True

    def test_ensure_session_exists_but_ai_not_running(self, manager):
        """测试 session 存在但 AI 未运行"""
        with patch.object(manager, '_check_tmux_session', return_value=True):
            with patch.object(manager, '_check_ai_running_in_session', return_value=False):
                with patch.object(manager, '_start_ai_in_existing_session', return_value=True):
                    success, just_started = manager._ensure_tmux_session()
                    assert success is True
                    assert just_started is True


class TestStartAIInExistingSession:
    """测试 _start_ai_in_existing_session 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    def test_start_ai_success(self, manager):
        """测试成功启动 AI"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            with patch('time.sleep'):
                result = manager._start_ai_in_existing_session()
                assert result is True

    def test_start_ai_failure(self, manager):
        """测试启动 AI 失败"""
        with patch('subprocess.run', side_effect=Exception("error")):
            result = manager._start_ai_in_existing_session()
            assert result is False


class TestSendCommand:
    """测试 send_command 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    @pytest.mark.asyncio
    async def test_send_command_success(self, manager):
        """测试成功发送命令"""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            with patch('time.sleep'):
                results = []
                async for result in manager.send_command("test command", skip_ensure=True):
                    results.append(result)

                assert len(results) == 1
                assert "命令已发送" in results[0]

    @pytest.mark.asyncio
    async def test_send_command_with_ensure(self, manager):
        """测试发送命令时检查 session"""
        with patch.object(manager, '_ensure_tmux_session', return_value=(True, False)):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                with patch('time.sleep'):
                    results = []
                    async for result in manager.send_command("test command"):
                        results.append(result)

                    assert len(results) == 1

    @pytest.mark.asyncio
    async def test_send_command_just_started(self, manager):
        """测试刚启动 AI 时发送命令"""
        with patch.object(manager, '_ensure_tmux_session', return_value=(True, True)):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0)
                with patch('time.sleep'):
                    results = []
                    async for result in manager.send_command("test command"):
                        results.append(result)

                    assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_send_command_ensure_failed(self, manager):
        """测试 session 检查失败"""
        with patch.object(manager, '_ensure_tmux_session', return_value=(False, False)):
            results = []
            async for result in manager.send_command("test command"):
                results.append(result)

            assert len(results) == 1
            assert "错误" in results[0]

    @pytest.mark.asyncio
    async def test_send_command_exception(self, manager):
        """测试发送命令异常"""
        with patch('subprocess.run', side_effect=Exception("error")):
            results = []
            async for result in manager.send_command("test command", skip_ensure=True):
                results.append(result)

            assert len(results) == 1
            assert "出错" in results[0]


class TestCleanTmuxOutput:
    """测试 _clean_tmux_output 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    def test_clean_ansi_codes(self, manager):
        """测试清理 ANSI 代码"""
        output = "\x1b[32mGreen text\x1b[0m"
        result = manager._clean_tmux_output(output)
        assert "\x1b[32m" not in result
        assert "Green text" in result

    def test_clean_long_dashes(self, manager):
        """测试缩短长分割线"""
        output = "-" * 100
        result = manager._clean_tmux_output(output)
        # 应该缩短到约 14 个字符 (100 // 7)
        assert len(result) < 50

    def test_clean_long_equals(self, manager):
        """测试缩短长等号"""
        output = "=" * 100
        result = manager._clean_tmux_output(output)
        assert len(result) < 50

    def test_clean_comment_lines(self, manager):
        """测试转义注释行"""
        output = "# This is a comment"
        result = manager._clean_tmux_output(output)
        assert result.startswith("\\#")

    def test_clean_normal_text(self, manager):
        """测试普通文本"""
        output = "Normal text without special characters"
        result = manager._clean_tmux_output(output)
        assert result == output


class TestMonitorOutput:
    """测试 monitor_output 方法"""

    @pytest.fixture
    def manager(self):
        """创建 TmuxSessionManager 实例"""
        with patch('src.ai_executor.tmux_session.get_settings') as mock_settings:
            mock_settings.return_value.AI_ASSISTANT_TYPE = "claude_code"
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test")
            mock_settings.return_value.TMUX_SESSION_NAME = "cc"
            mock_settings.return_value.get_process_name = Mock(return_value="claude")

            from src.ai_executor.tmux_session import TmuxSessionManager
            manager = TmuxSessionManager.__new__(TmuxSessionManager)
            manager._cli_path = "claude"
            manager.workspace = Path("/test")
            manager._tmux_session = "cc"
            manager._log_debug_info = Mock()
            return manager

    @pytest.mark.asyncio
    async def test_monitor_output_stable(self, manager):
        """测试输出稳定后停止"""
        callback_results = []

        def callback(content, is_last):
            callback_results.append((content, is_last))

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Test output"

        with patch('subprocess.run', return_value=mock_result):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                result = await manager.monitor_output(callback, stable_threshold=2)

                assert result == "Test output"

    @pytest.mark.asyncio
    async def test_monitor_output_timeout(self, manager):
        """测试监控超时"""
        callback = Mock()

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Test output"

        # 模拟时间达到超时
        time_values = [0, 100, 100, 100]  # 第一次检查 elapsed=100 > timeout=100

        with patch('subprocess.run', return_value=mock_result):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                with patch('time.time', side_effect=time_values):
                    result = await manager.monitor_output(callback, timeout=100)

                    # 应该在超时时返回
                    assert result is not None

    @pytest.mark.asyncio
    async def test_monitor_output_capture_error(self, manager):
        """测试捕获输出错误"""
        callback = Mock()

        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stderr = "Error"

        with patch('subprocess.run', return_value=mock_result):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                # 让循环在几次后退出
                mock_sleep.side_effect = [None, None, asyncio.CancelledError()]
                try:
                    await manager.monitor_output(callback, stable_threshold=10)
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_monitor_output_callback_error(self, manager):
        """测试回调函数错误"""
        def error_callback(content, is_last):
            raise Exception("Callback error")

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "Test output"

        with patch('subprocess.run', return_value=mock_result):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                # 不应该抛出异常
                result = await manager.monitor_output(error_callback, stable_threshold=2)
                assert result is not None

    @pytest.mark.asyncio
    async def test_monitor_output_exception(self, manager):
        """测试监控异常"""
        callback = Mock()

        with patch('subprocess.run', side_effect=Exception("error")):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                mock_sleep.side_effect = asyncio.CancelledError()
                try:
                    await manager.monitor_output(callback)
                except asyncio.CancelledError:
                    pass