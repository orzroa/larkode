"""
测试平台命令处理器
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestPlatformCommands:
    """测试平台命令处理器"""

    @pytest.fixture
    def mock_task_manager(self):
        """创建模拟的任务管理器"""
        tm = Mock()
        return tm

    @pytest.fixture
    def mock_card_dispatcher(self):
        """创建模拟的卡片分发器"""
        dispatcher = Mock()
        dispatcher.send_card = AsyncMock(return_value=True)
        return dispatcher

    @pytest.fixture
    def platform_commands(self, mock_task_manager, mock_card_dispatcher):
        """创建平台命令处理器实例"""
        from src.handlers.platform_commands import PlatformCommands
        return PlatformCommands(
            task_manager=mock_task_manager,
            card_dispatcher=mock_card_dispatcher
        )

    def test_set_send_callback(self, platform_commands):
        """测试设置发送回调函数"""
        callback = Mock()
        platform_commands.set_send_callback(callback)
        assert platform_commands._send_via_sender == callback

    @pytest.mark.asyncio
    async def test_handle_command_help(self, platform_commands):
        """测试处理 #help 命令"""
        await platform_commands.handle_command("user_123", "#help")
        # 应该调用 send_card

    @pytest.mark.asyncio
    async def test_handle_command_cancel(self, platform_commands, mock_card_dispatcher):
        """测试处理 #cancel 命令"""
        with patch('subprocess.run') as mock_run:
            await platform_commands.handle_command("user_123", "#cancel")

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_handle_command_cancel_subprocess_error(self, platform_commands):
        """测试 #cancel 命令执行失败"""
        import subprocess
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "tmux")):
            with patch.object(platform_commands, '_send_error', new_callable=AsyncMock) as mock_error:
                await platform_commands.handle_command("user_123", "#cancel")

                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_handle_command_history(self, platform_commands):
        """测试处理 #history 命令"""
        with patch('src.storage.db') as mock_db:
            mock_db.get_messages_by_direction.return_value = []

            await platform_commands.handle_command("user_123", "#history")

    @pytest.mark.asyncio
    async def test_handle_command_history_with_limit(self, platform_commands):
        """测试处理 #history 命令带参数"""
        with patch('src.storage.db') as mock_db:
            mock_msg = Mock()
            mock_msg.created_at = Mock()
            mock_msg.created_at.strftime.return_value = "2024-01-01 12:00"
            mock_msg.content = "test message"
            mock_db.get_messages_by_direction.return_value = [mock_msg]

            await platform_commands.handle_command("user_123", "#history 5")

    @pytest.mark.asyncio
    async def test_handle_command_shot(self, platform_commands):
        """测试处理 #shot 命令"""
        with patch('src.utils.tmux_utils.get_tmux_last_lines', return_value="screen output"):
            await platform_commands.handle_command("user_123", "#shot")

    @pytest.mark.asyncio
    async def test_handle_command_shot_with_lines(self, platform_commands):
        """测试处理 #shot 命令带参数"""
        with patch('src.utils.tmux_utils.get_tmux_last_lines', return_value="screen output"):
            await platform_commands.handle_command("user_123", "#shot 500")

    @pytest.mark.asyncio
    async def test_handle_command_model(self, platform_commands):
        """测试处理 #model 命令"""
        with patch('src.handlers.platform_commands.CCRCommands') as mock_ccr:
            mock_ccr_instance = Mock()
            mock_ccr_instance.handle_model_command = AsyncMock()
            mock_ccr.return_value = mock_ccr_instance

            await platform_commands.handle_command("user_123", "#model")

    @pytest.mark.asyncio
    async def test_handle_command_unknown(self, platform_commands):
        """测试处理未知命令"""
        with patch.object(platform_commands, '_send_error', new_callable=AsyncMock) as mock_error:
            await platform_commands.handle_command("user_123", "#unknown")

            mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_help_with_card_dispatcher(self, platform_commands, mock_card_dispatcher):
        """测试帮助命令使用卡片分发器"""
        await platform_commands._cmd_help("user_123")
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_help_with_card_builder(self, platform_commands):
        """测试帮助命令使用卡片构建器"""
        platform_commands.card_builder = Mock()
        platform_commands.card_dispatcher = None
        platform_commands._send_via_sender = AsyncMock()

        await platform_commands._cmd_help("user_123")

    @pytest.mark.asyncio
    async def test_cmd_history_empty(self, platform_commands):
        """测试历史命令无消息"""
        with patch('src.storage.db') as mock_db:
            mock_db.get_messages_by_direction.return_value = []

            await platform_commands._cmd_history("user_123")

    @pytest.mark.asyncio
    async def test_cmd_history_with_messages(self, platform_commands):
        """测试历史命令有消息"""
        with patch('src.storage.db') as mock_db:
            mock_msg = Mock()
            mock_msg.created_at = Mock()
            mock_msg.created_at.strftime.return_value = "2024-01-01 12:00"
            mock_msg.content = "test message"
            mock_db.get_messages_by_direction.return_value = [mock_msg]

            await platform_commands._cmd_history("user_123")

    @pytest.mark.asyncio
    async def test_cmd_shot_with_builder(self, platform_commands, mock_card_dispatcher):
        """测试截屏命令使用分发器"""
        await platform_commands._cmd_shot_with_builder("user_123", "screen output")
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_shot_with_card_builder_fallback(self, platform_commands):
        """测试截屏命令回退到卡片构建器"""
        platform_commands.card_builder = Mock()
        platform_commands._send_via_sender = AsyncMock()
        mock_card = Mock()
        platform_commands.card_builder.send_card = AsyncMock()

        await platform_commands._cmd_shot_with_builder("user_123", "screen output")

    @pytest.mark.asyncio
    async def test_cmd_shot_legacy(self, platform_commands):
        """测试废弃的截屏方法"""
        with patch('src.handlers.platform_commands.logger') as mock_logger:
            await platform_commands._cmd_shot_legacy("user_123", "output")

    @pytest.mark.asyncio
    async def test_cmd_cancel_success(self, platform_commands, mock_card_dispatcher):
        """测试取消命令成功"""
        with patch('subprocess.run') as mock_run:
            await platform_commands._cmd_cancel("user_123", "")

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_cmd_cancel_error(self, platform_commands):
        """测试取消命令错误"""
        import subprocess
        with patch('subprocess.run', side_effect=subprocess.CalledProcessError(1, "tmux")):
            with patch.object(platform_commands, '_send_error', new_callable=AsyncMock) as mock_error:
                await platform_commands._cmd_cancel("user_123", "")

                mock_error.assert_called()

    @pytest.mark.asyncio
    async def test_send_error_with_card_builder(self, platform_commands):
        """测试发送错误使用卡片构建器"""
        platform_commands.card_builder = Mock()
        platform_commands._send_via_sender = AsyncMock()

        await platform_commands._send_error("user_123", "error message")

    @pytest.mark.asyncio
    async def test_cmd_model(self, platform_commands):
        """测试模型命令"""
        with patch('src.handlers.platform_commands.CCRCommands') as mock_ccr:
            mock_instance = Mock()
            mock_instance.handle_model_command = AsyncMock()
            mock_ccr.return_value = mock_instance

            await platform_commands._cmd_model("user_123", "")
