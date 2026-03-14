"""
TaskManager 单元测试
"""
import pytest
import asyncio
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from typing import AsyncGenerator

from src.task_manager import TaskManager
from src.interfaces.ai_assistant import IAIAssistantInterface


class MockAIAssistant(IAIAssistantInterface):
    """模拟 AI 助手"""

    def __init__(self):
        self._cancelled = False
        self._status = {"status": "idle"}
        self._execute_calls = []

    async def execute_command(self, command: str, user_id: str = None) -> AsyncGenerator[str, None]:
        """模拟执行命令"""
        self._execute_calls.append((command, user_id))
        yield f"Output for: {command}"

    def cancel(self) -> bool:
        """模拟取消"""
        self._cancelled = True
        return True

    def get_status(self) -> dict:
        """模拟获取状态"""
        return self._status


class TestTaskManagerInit:
    """测试 TaskManager 初始化"""

    def test_init_with_assistant(self):
        """测试使用传入的 AI 助手初始化"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        assert manager.ai_assistant is mock_assistant

    def test_init_without_assistant(self):
        """测试不传入 AI 助手时的初始化"""
        with patch('src.task_manager.TaskManager._create_default_assistant') as mock_create:
            mock_assistant = MockAIAssistant()
            mock_create.return_value = mock_assistant

            manager = TaskManager()
            assert manager.ai_assistant is mock_assistant
            mock_create.assert_called_once()


class TestStartStop:
    """测试 start 和 stop 方法"""

    @pytest.mark.asyncio
    async def test_start(self):
        """测试启动"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        # start 应该不抛出异常
        await manager.start()

    @pytest.mark.asyncio
    async def test_stop(self):
        """测试停止"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        # stop 应该不抛出异常
        await manager.stop()


class TestCreateDefaultAssistant:
    """测试 _create_default_assistant 方法"""

    def test_create_default_assistant_success(self):
        """测试成功创建默认助手"""
        mock_assistant = MockAIAssistant()

        with patch('src.factories.assistant_factory.AIAssistantFactory.is_assistant_registered', return_value=False):
            with patch('src.ai_assistants.register_default_assistant'):
                with patch('src.factories.assistant_factory.AIAssistantFactory.create_assistant', return_value=mock_assistant):
                    with patch('src.config.settings.get_settings') as mock_settings:
                        mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = "/workspace"
                        mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"
                        mock_settings.return_value.CLAUDE_CODE_SESSION_ID = "session123"

                        manager = TaskManager()
                        assistant = manager._create_default_assistant()
                        assert assistant is mock_assistant

    def test_create_default_assistant_factory_fails(self):
        """测试工厂创建失败时的回退"""
        with patch('src.factories.assistant_factory.AIAssistantFactory.is_assistant_registered', return_value=False):
            with patch('src.ai_assistants.register_default_assistant'):
                with patch('src.factories.assistant_factory.AIAssistantFactory.create_assistant', return_value=None):
                    with patch('src.config.settings.get_settings') as mock_settings:
                        mock_settings.return_value.CLAUDE_CODE_WORKSPACE_DIR = "/workspace"
                        mock_settings.return_value.CLAUDE_CODE_CLI_PATH = "claude"

                        manager = TaskManager()
                        # 应该创建回退的 AIInterface
                        assistant = manager._create_default_assistant()
                        assert assistant is not None


class TestExecuteCommand:
    """测试 execute_command 方法"""

    @pytest.mark.asyncio
    async def test_execute_command_basic(self):
        """测试基本命令执行"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        outputs = []
        async for output in manager.execute_command("test_user", "echo hello"):
            outputs.append(output)

        assert len(outputs) == 1
        assert "echo hello" in outputs[0]
        assert ("echo hello", "test_user") in mock_assistant._execute_calls

    @pytest.mark.asyncio
    async def test_execute_command_streaming(self):
        """测试流式输出"""
        class StreamingMockAssistant(IAIAssistantInterface):
            async def execute_command(self, command: str, user_id: str = None):
                for i in range(3):
                    yield f"Line {i}: {command}"

            def cancel(self):
                return True

            def get_status(self):
                return {"status": "running"}

        manager = TaskManager(ai_assistant=StreamingMockAssistant())

        outputs = []
        async for output in manager.execute_command("user", "test command"):
            outputs.append(output)

        assert len(outputs) == 3
        assert outputs[0] == "Line 0: test command"

    @pytest.mark.asyncio
    async def test_execute_command_empty(self):
        """测试空命令"""
        class EmptyMockAssistant(IAIAssistantInterface):
            async def execute_command(self, command: str, user_id: str = None):
                if not command:
                    yield "Error: Empty command"
                else:
                    yield f"Executed: {command}"

            def cancel(self):
                return True

            def get_status(self):
                return {"status": "idle"}

        manager = TaskManager(ai_assistant=EmptyMockAssistant())

        outputs = []
        async for output in manager.execute_command("user", ""):
            outputs.append(output)

        assert len(outputs) == 1
        assert "Error" in outputs[0]

    @pytest.mark.asyncio
    async def test_execute_command_with_special_characters(self):
        """测试特殊字符命令"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        special_command = "echo 'hello \"world\"' && ls -la"
        outputs = []
        async for output in manager.execute_command("user", special_command):
            outputs.append(output)

        assert len(outputs) == 1


class TestCancel:
    """测试 cancel 方法"""

    def test_cancel_success(self):
        """测试成功取消"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        result = manager.cancel()

        assert result is True
        assert mock_assistant._cancelled is True

    def test_cancel_delegates_to_assistant(self):
        """测试取消委托给助手"""
        mock_assistant = MagicMock()
        mock_assistant.cancel.return_value = True
        manager = TaskManager(ai_assistant=mock_assistant)

        result = manager.cancel()

        mock_assistant.cancel.assert_called_once()
        assert result is True


class TestGetAssistantStatus:
    """测试 get_assistant_status 方法"""

    def test_get_status(self):
        """测试获取助手状态"""
        mock_assistant = MockAIAssistant()
        mock_assistant._status = {"status": "running", "pid": 12345}
        manager = TaskManager(ai_assistant=mock_assistant)

        status = manager.get_assistant_status()

        assert status["status"] == "running"
        assert status["pid"] == 12345

    def test_get_status_delegates_to_assistant(self):
        """测试状态获取委托给助手"""
        mock_assistant = MagicMock()
        mock_assistant.get_status.return_value = {"status": "idle"}
        manager = TaskManager(ai_assistant=mock_assistant)

        status = manager.get_assistant_status()

        mock_assistant.get_status.assert_called_once()
        assert status == {"status": "idle"}


class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from src.task_manager import task_manager

        assert task_manager is not None
        assert isinstance(task_manager, TaskManager)


class TestEdgeCases:
    """测试边界情况"""

    @pytest.mark.asyncio
    async def test_execute_command_with_none_user_id(self):
        """测试 None user_id"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        outputs = []
        async for output in manager.execute_command(None, "test"):
            outputs.append(output)

        assert len(outputs) == 1

    @pytest.mark.asyncio
    async def test_execute_command_with_long_command(self):
        """测试长命令"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        long_command = "echo " + "a" * 10000
        outputs = []
        async for output in manager.execute_command("user", long_command):
            outputs.append(output)

        assert len(outputs) == 1

    @pytest.mark.asyncio
    async def test_execute_command_with_unicode(self):
        """测试 Unicode 命令"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        unicode_command = "echo '你好世界 🎉'"
        outputs = []
        async for output in manager.execute_command("user", unicode_command):
            outputs.append(output)

        assert len(outputs) == 1

    @pytest.mark.asyncio
    async def test_execute_command_with_multiline(self):
        """测试多行命令"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        multiline = "line1\nline2\nline3"
        outputs = []
        async for output in manager.execute_command("user", multiline):
            outputs.append(output)

        assert len(outputs) == 1

    def test_cancel_multiple_times(self):
        """测试多次取消"""
        mock_assistant = MockAIAssistant()
        manager = TaskManager(ai_assistant=mock_assistant)

        # 多次取消应该不会出错
        manager.cancel()
        manager.cancel()
        manager.cancel()

        assert mock_assistant._cancelled is True


class TestErrorHandling:
    """测试错误处理"""

    @pytest.mark.asyncio
    async def test_execute_command_with_error(self):
        """测试执行命令时的错误"""
        class ErrorMockAssistant(IAIAssistantInterface):
            async def execute_command(self, command: str, user_id: str = None):
                raise RuntimeError("Test error")
                yield  # 使其成为生成器

            def cancel(self):
                return True

            def get_status(self):
                return {"status": "error"}

        manager = TaskManager(ai_assistant=ErrorMockAssistant())

        with pytest.raises(RuntimeError):
            async for _ in manager.execute_command("user", "test"):
                pass

    def test_cancel_with_error(self):
        """测试取消时的错误"""
        mock_assistant = MagicMock()
        mock_assistant.cancel.side_effect = Exception("Cancel error")
        manager = TaskManager(ai_assistant=mock_assistant)

        with pytest.raises(Exception):
            manager.cancel()