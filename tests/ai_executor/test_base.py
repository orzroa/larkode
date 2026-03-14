"""
测试 AI 执行器基础类
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestAIExecutorInit:
    """测试 AIExecutor 初始化"""

    def test_init_default_workspace(self):
        """测试默认工作目录初始化"""
        from src.ai_executor.base import AIExecutor

        with patch('src.ai_executor.base.get_settings') as mock_settings:
            mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = Path("/test/workspace")

            executor = AIExecutor()

            assert executor.workspace == Path("/test/workspace")
            assert executor._running_process is None

    def test_init_custom_workspace(self):
        """测试自定义工作目录初始化"""
        from src.ai_executor.base import AIExecutor

        custom_workspace = Path("/custom/workspace")

        executor = AIExecutor(workspace=custom_workspace)

        assert executor.workspace == custom_workspace
        assert executor._running_process is None


class TestExecuteCommand:
    """测试 execute_command 方法"""

    @pytest.fixture
    def executor(self):
        """创建执行器实例"""
        from src.ai_executor.base import AIExecutor
        executor = AIExecutor.__new__(AIExecutor)
        executor.workspace = Path("/test/workspace")
        executor._running_process = None
        return executor

    @pytest.mark.asyncio
    async def test_execute_command_workspace_not_exists(self, executor):
        """测试工作目录不存在"""
        executor.workspace = Path("/nonexistent/path")

        results = []
        async for result in executor.execute_command("test command"):
            results.append(result)

        assert len(results) == 1
        assert "错误" in results[0]
        assert "工作目录不存在" in results[0]

    @pytest.mark.asyncio
    async def test_execute_command_cli_not_found(self, executor):
        """测试 CLI 未找到"""
        mock_workspace = MagicMock()
        mock_workspace.exists.return_value = True
        executor.workspace = mock_workspace

        with patch('src.ai_executor.base.get_settings') as mock_settings:
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "/nonexistent/claude"

            with patch('pathlib.Path.exists', return_value=False):
                results = []
                async for result in executor.execute_command("test command"):
                    results.append(result)

                assert len(results) == 1
                assert "错误" in results[0]
                assert "AI CLI 未找到" in results[0]

    @pytest.mark.asyncio
    async def test_execute_command_success(self, executor):
        """测试成功执行命令"""
        mock_workspace = MagicMock()
        mock_workspace.exists.return_value = True
        mock_workspace.__str__ = lambda self: "/test/workspace"
        executor.workspace = mock_workspace

        # 模拟进程
        mock_process = AsyncMock()
        mock_process.stdout.readline = AsyncMock()
        mock_process.stdout.readline.side_effect = [b"output line 1\n", b"output line 2\n", b""]
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=0)

        with patch('src.ai_executor.base.get_settings') as mock_settings:
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "/usr/bin/claude"

            with patch('pathlib.Path.exists', return_value=True):
                with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                    results = []
                    async for result in executor.execute_command("test command"):
                        results.append(result)

                    assert len(results) == 2
                    assert results[0] == "output line 1"
                    assert results[1] == "output line 2"
                    assert executor._running_process is None

    @pytest.mark.asyncio
    async def test_execute_command_with_stderr(self, executor):
        """测试执行命令包含错误输出"""
        mock_workspace = MagicMock()
        mock_workspace.exists.return_value = True
        mock_workspace.__str__ = lambda self: "/test/workspace"
        executor.workspace = mock_workspace

        mock_process = AsyncMock()
        mock_process.stdout.readline = AsyncMock()
        mock_process.stdout.readline.side_effect = [b"output\n", b""]
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"stderr output")
        mock_process.wait = AsyncMock(return_value=0)

        with patch('src.ai_executor.base.get_settings') as mock_settings:
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "/usr/bin/claude"

            with patch('pathlib.Path.exists', return_value=True):
                with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                    results = []
                    async for result in executor.execute_command("test command"):
                        results.append(result)

                    assert len(results) == 2
                    assert "stderr output" in results[1]

    @pytest.mark.asyncio
    async def test_execute_command_nonzero_return(self, executor):
        """测试非零返回码"""
        mock_workspace = MagicMock()
        mock_workspace.exists.return_value = True
        mock_workspace.__str__ = lambda self: "/test/workspace"
        executor.workspace = mock_workspace

        mock_process = AsyncMock()
        mock_process.stdout.readline = AsyncMock()
        mock_process.stdout.readline.side_effect = [b"output\n", b""]
        mock_process.stderr = AsyncMock()
        mock_process.stderr.read = AsyncMock(return_value=b"")
        mock_process.wait = AsyncMock(return_value=1)

        with patch('src.ai_executor.base.get_settings') as mock_settings:
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "/usr/bin/claude"

            with patch('pathlib.Path.exists', return_value=True):
                with patch('asyncio.create_subprocess_exec', return_value=mock_process):
                    results = []
                    async for result in executor.execute_command("test command"):
                        results.append(result)

                    assert any("返回码: 1" in r for r in results)

    @pytest.mark.asyncio
    async def test_execute_command_exception(self, executor):
        """测试执行命令异常"""
        mock_workspace = MagicMock()
        mock_workspace.exists.return_value = True
        mock_workspace.__str__ = lambda self: "/test/workspace"
        executor.workspace = mock_workspace

        with patch('src.ai_executor.base.get_settings') as mock_settings:
            mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "/usr/bin/claude"

            with patch('pathlib.Path.exists', return_value=True):
                with patch('asyncio.create_subprocess_exec', side_effect=Exception("Process error")):
                    results = []
                    async for result in executor.execute_command("test command"):
                        results.append(result)

                    assert len(results) == 1
                    assert "执行出错" in results[0]
                    assert executor._running_process is None


class TestCancelTask:
    """测试 cancel_task 方法"""

    @pytest.fixture
    def executor(self):
        """创建执行器实例"""
        from src.ai_executor.base import AIExecutor
        executor = AIExecutor.__new__(AIExecutor)
        executor.workspace = Path("/test/workspace")
        executor._running_process = None
        return executor

    def test_cancel_task_no_process(self, executor):
        """测试没有运行中的进程"""
        result = executor.cancel_task("task_123")
        assert result is False

    def test_cancel_task_with_process(self, executor):
        """测试有运行中的进程"""
        mock_process = Mock()
        mock_process.terminate = Mock()
        executor._running_process = mock_process

        result = executor.cancel_task("task_123")

        assert result is True
        mock_process.terminate.assert_called_once()


class TestIsTaskRunning:
    """测试 is_task_running 方法"""

    @pytest.fixture
    def executor(self):
        """创建执行器实例"""
        from src.ai_executor.base import AIExecutor
        executor = AIExecutor.__new__(AIExecutor)
        executor.workspace = Path("/test/workspace")
        executor._running_process = None
        return executor

    def test_is_task_running_no_process(self, executor):
        """测试没有运行中的进程"""
        result = executor.is_task_running("task_123")
        assert result is False

    def test_is_task_running_with_process(self, executor):
        """测试有运行中的进程"""
        executor._running_process = Mock()
        result = executor.is_task_running("task_123")
        assert result is True