"""
工作空间命令处理器测试

注意：工作空间命令现在使用 WorkspaceManager，主要逻辑在 workspace_manager.py 中测试
这里只测试命令处理器的集成部分
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from src.handlers.workspace_commands import WorkspaceCommands


class TestWorkspaceCommands:
    """测试 WorkspaceCommands 类"""

    def test_init(self):
        """测试初始化"""
        ws_cmd = WorkspaceCommands()
        assert ws_cmd is not None

    @pytest.mark.asyncio
    async def test_handle_workspace_command_disabled(self):
        """测试禁用自动发现时的命令处理"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = False

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            await ws_cmd.handle_workspace_command(
                user_id="test_user",
                args="",
                send_message_func=send_message_func
            )

            # 应该发送错误消息
            assert send_message_func.called
            # 获取调用的关键字参数
            call_kwargs = send_message_func.call_args.kwargs
            card = call_kwargs.get('card')
            assert card is not None
            assert card.title == "错误"
            assert "未启用工作空间自动发现" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_no_root(self):
        """测试根目录未配置时的命令处理"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = None

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            await ws_cmd.handle_workspace_command(
                user_id="test_user",
                args="",
                send_message_func=send_message_func
            )

            # 应该发送错误消息
            assert send_message_func.called
            call_kwargs = send_message_func.call_args.kwargs
            card = call_kwargs.get('card')
            assert card is not None
            assert card.title == "错误"
            assert "工作空间根目录未配置或不存在" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_invalid_input(self):
        """测试无效输入"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'project1', 'path': '/tmp/project1', 'depth': 1, 'is_running': False, 'is_default': True, 'is_current': False}
        ]

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="abc",  # 非数字输入
                    send_message_func=send_message_func
                )

                # 应该发送错误消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert card.title == "错误"
                assert "无效输入" in card.content