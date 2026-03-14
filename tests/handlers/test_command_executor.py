"""
测试命令执行器
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCommandExecutor:
    """测试命令执行器"""

    @pytest.fixture
    def mock_task_manager(self):
        """创建模拟的任务管理器"""
        tm = Mock()
        tm.execute_command = AsyncMock(return_value=iter([]))
        return tm

    @pytest.fixture
    def mock_message_sender(self):
        """创建模拟的消息发送器"""
        sender = Mock()
        sender.send = AsyncMock(return_value=True)
        sender.send_error = AsyncMock(return_value=True)
        return sender

    @pytest.fixture
    def mock_card_dispatcher(self):
        """创建模拟的卡片分发器"""
        dispatcher = Mock()
        dispatcher.send_card = AsyncMock(return_value=True)
        return dispatcher

    @pytest.fixture
    def mock_platform(self):
        """创建模拟的 IM 平台"""
        platform = Mock()
        platform.is_platform_command = Mock(return_value=False)
        return platform

    @pytest.fixture
    def mock_platform_commands(self):
        """创建模拟的平台命令处理器"""
        commands = Mock()
        commands.handle_command = AsyncMock(return_value=True)
        return commands

    @pytest.fixture
    def command_executor(self, mock_task_manager, mock_message_sender, mock_card_dispatcher, mock_platform):
        """创建命令执行器实例"""
        from src.handlers.command_executor import CommandExecutor
        executor = CommandExecutor(
            task_manager=mock_task_manager,
            platform=mock_platform,
            message_sender=mock_message_sender,
            card_dispatcher=mock_card_dispatcher
        )
        return executor

    def test_set_message_sender(self, command_executor):
        """测试设置消息发送器"""
        sender = Mock()
        command_executor.set_message_sender(sender)
        assert command_executor._message_sender == sender

    def test_set_card_builder(self, command_executor):
        """测试设置卡片构建器"""
        builder = Mock()
        command_executor.set_card_builder(builder)
        assert command_executor.card_builder == builder

    def test_set_platform_commands(self, command_executor):
        """测试设置平台命令处理器"""
        commands = Mock()
        command_executor.set_platform_commands(commands)
        assert command_executor._platform_commands == commands

    def test_set_current_platform(self, command_executor):
        """测试设置当前平台"""
        command_executor.set_current_platform("feishu")
        assert command_executor._current_platform == "feishu"

    def test_is_test_user_true(self, command_executor):
        """测试测试用户判断 - 包含 test"""
        assert command_executor._is_test_user("test_user_123") is True

    def test_is_test_user_false(self, command_executor):
        """测试测试用户判断 - 不包含 test"""
        assert command_executor._is_test_user("real_user_123") is False

    @pytest.mark.asyncio
    async def test_process_command_platform_command(self, command_executor, mock_platform_commands):
        """测试处理平台命令"""
        command_executor._platform_commands = mock_platform_commands
        # 设置平台返回 True，表示是平台命令
        command_executor.platform.is_platform_command = Mock(return_value=True)

        await command_executor.process_command("user_123", "#help")

        mock_platform_commands.handle_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_command_ai_command(self, command_executor, mock_task_manager):
        """测试处理 AI 命令"""
        with patch('src.handlers.command_executor.db') as mock_db:
            mock_db.save_message.return_value = 123

            await command_executor.process_command("user_123", "Hello AI")

        mock_task_manager.execute_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_command_saves_to_database(self, command_executor, mock_task_manager):
        """测试处理命令时保存到数据库"""
        with patch('src.handlers.command_executor.db') as mock_db:
            mock_db.save_message.return_value = 456

            await command_executor.process_command("user_123", "test command", "msg_123")

        mock_db.save_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_command_handles_exception(self, command_executor, mock_task_manager):
        """测试处理命令时捕获异常"""
        mock_task_manager.execute_command.side_effect = Exception("Task error")

        with patch.object(command_executor, 'send_error', new_callable=AsyncMock) as mock_send_error:
            await command_executor.process_command("user_123", "test command")

        mock_send_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_with_confirmation_card(self, command_executor, mock_card_dispatcher):
        """测试执行命令时显示确认卡片"""
        with patch('src.handlers.command_executor.get_settings') as mock_settings:
            mock_settings.return_value.SHOW_COMMAND_CONFIRMATION_CARD = True

            await command_executor.execute_command("user_123", "test command")

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_execute_command_without_confirmation_card(self, command_executor, mock_task_manager):
        """测试执行命令时不显示确认卡片"""
        with patch('src.handlers.command_executor.get_settings') as mock_settings:
            mock_settings.return_value.SHOW_COMMAND_CONFIRMATION_CARD = False

            await command_executor.execute_command("user_123", "test command")

        mock_task_manager.execute_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_fallback_to_card_builder(self, command_executor):
        """测试执行命令时回退到卡片构建器"""
        command_executor.card_builder = Mock()
        command_executor.card_builder.create_command_card = Mock(return_value=Mock())
        command_executor.card_dispatcher = None

        with patch('src.handlers.command_executor.get_settings') as mock_settings:
            mock_settings.return_value.SHOW_COMMAND_CONFIRMATION_CARD = True

            await command_executor.execute_command("user_123", "test command")

        command_executor.card_builder.create_command_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_command_handles_error(self, command_executor, mock_task_manager):
        """测试执行命令时处理错误"""
        mock_task_manager.execute_command.side_effect = Exception("Execution failed")

        with patch.object(command_executor, 'send_error', new_callable=AsyncMock) as mock_send_error:
            await command_executor.execute_command("user_123", "test command")

        mock_send_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_error_with_message_sender(self, command_executor, mock_message_sender):
        """测试发送错误消息"""
        command_executor._message_sender = mock_message_sender

        await command_executor.send_error("user_123", "Error occurred")

        mock_message_sender.send_error.assert_called_once_with("user_123", "Error occurred")

    @pytest.mark.asyncio
    async def test_send_error_without_message_sender(self, command_executor):
        """测试没有消息发送器时发送错误"""
        command_executor._message_sender = None

        # 不应该抛出异常
        await command_executor.send_error("user_123", "Error occurred")
