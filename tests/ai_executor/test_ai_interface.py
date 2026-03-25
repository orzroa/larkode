"""
测试 AIInterface 类
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


class TestAIInterface:
    """测试 AIInterface 类"""

    @pytest.fixture
    def mock_executor(self):
        """模拟 AIExecutor"""
        mock = MagicMock()
        mock._session_id = "old_session"
        mock._formatted_results = {"key": "formatted result"}
        mock.cancel_task = MagicMock(return_value=True)
        mock.is_task_running = MagicMock(return_value=False)
        # 模拟 execute_command 异步生成器
        async def gen(cmd):
            yield "line1"
            yield "line2"
        mock.execute_command = gen
        return mock

    def test_init(self, mock_executor):
        """测试初始化"""
        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface(workspace=Path("/tmp/test"))
            assert interface.executor == mock_executor

    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_executor):
        """测试执行命令成功"""
        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface()
            success, result = await interface.execute_command("test command")
            assert success is True
            assert result == "formatted result"

    @pytest.mark.asyncio
    async def test_execute_command_with_session_id(self, mock_executor):
        """测试带 session_id 执行命令"""
        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface()
            success, result = await interface.execute_command("test command", session_id="new_session")
            assert success is True
            assert mock_executor._session_id == "new_session"

    @pytest.mark.asyncio
    async def test_execute_command_no_formatted_results(self, mock_executor):
        """测试没有格式化结果"""
        mock_executor._formatted_results = {}
        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface()
            success, result = await interface.execute_command("test command")
            assert success is True
            assert result == "line1\nline2"

    @pytest.mark.asyncio
    async def test_execute_command_exception(self, mock_executor):
        """测试执行命令异常"""
        async def gen_fail(cmd):
            raise Exception("Execution failed")
            yield  # unreachable
        mock_executor.execute_command = gen_fail
        mock_executor._formatted_results = {}

        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface()
            success, result = await interface.execute_command("test command")
            assert success is False
            assert "Execution failed" in result

    def test_cancel(self, mock_executor):
        """测试取消命令"""
        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface()
            result = interface.cancel()
            assert result is True
            mock_executor.cancel_task.assert_called_once_with("current")

    def test_is_running(self, mock_executor):
        """测试检查是否在运行"""
        with patch('src.ai_executor.base.AIExecutor', return_value=mock_executor):
            from src.ai_executor.interface import AIInterface
            interface = AIInterface()
            result = interface.is_running()
            assert result is False
            mock_executor.is_task_running.assert_called_once_with("current")


def test_logging_import_fallback():
    """测试 logging 导入 fallback"""
    import sys
    import importlib
    for mod in ['src.ai_executor.interface', 'src.logging_utils']:
        if mod in sys.modules:
            del sys.modules[mod]
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == 'src.logging_utils':
            raise ImportError("logging_utils not available")
        return original_import(name, *args, **kwargs)
    with patch('builtins.__import__', side_effect=mock_import):
        import src.ai_executor.interface
        importlib.reload(src.ai_executor.interface)
        assert hasattr(src.ai_executor.interface, 'logger')