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
    async def test_handle_workspace_command_empty_list(self):
        """测试空工作空间列表"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = []

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
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
                assert "未发现任何工作空间" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_show_list(self):
        """测试显示工作空间列表（无参数）"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")
        mock_settings.workspace_default_dir = Path("/tmp/project1")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'project1', 'path': '/tmp/project1', 'depth': 1, 'is_running': True, 'is_default': True, 'is_current': True},
            {'name': 'project2', 'path': '/tmp/project2', 'depth': 1, 'is_running': False, 'is_default': False, 'is_current': False}
        ]

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="",  # 无参数
                    send_message_func=send_message_func
                )

                # 应该发送工作空间列表
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert card.title == "工作空间"
                assert "project1" in card.content
                assert "project2" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_switch_success(self):
        """测试切换工作空间成功"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'project1', 'path': '/tmp/project1', 'depth': 1, 'is_running': False, 'is_default': True, 'is_current': False},
            {'name': 'project2', 'path': '/tmp/project2', 'depth': 1, 'is_running': False, 'is_default': False, 'is_current': False}
        ]
        mock_manager.switch_workspace.return_value = (True, "切换成功")

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="2",  # 切换到第二个工作空间
                    send_message_func=send_message_func
                )

                # 应该发送成功消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert "成功" in card.title
                assert card.template_color == "green"

    @pytest.mark.asyncio
    async def test_handle_workspace_command_switch_failed(self):
        """测试切换工作空间失败"""
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
        mock_manager.switch_workspace.return_value = (False, "切换失败：路径不存在")

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="1",
                    send_message_func=send_message_func
                )

                # 应该发送错误消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert card.title == "错误"
                assert "切换失败" in card.content

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
                assert "未找到匹配的工作空间" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_out_of_range(self):
        """测试序号超出范围"""
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
                    args="10",  # 超出范围的序号
                    send_message_func=send_message_func
                )

                # 应该发送错误消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert card.title == "错误"
                assert "无效序号" in card.content

    @pytest.mark.asyncio
    async def test_show_workspace_list_with_warning(self):
        """测试默认工作空间不在列表中的警告"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")
        mock_settings.workspace_default_dir = Path("/tmp/not_in_list")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'project1', 'path': '/tmp/project1', 'depth': 1, 'is_running': False, 'is_default': False, 'is_current': False}
        ]

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="",
                    send_message_func=send_message_func
                )

                # 应该包含警告信息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert "警告" in card.content

    @pytest.mark.asyncio
    async def test_send_success(self):
        """测试发送成功消息"""
        ws_cmd = WorkspaceCommands()
        send_message_func = AsyncMock()

        await ws_cmd._send_success(
            user_id="test_user",
            content="测试成功",
            workspace_name="test_workspace",
            send_message_func=send_message_func
        )

        assert send_message_func.called
        call_kwargs = send_message_func.call_args.kwargs
        card = call_kwargs.get('card')
        assert card is not None
        assert "成功" in card.title
        assert card.template_color == "green"

    @pytest.mark.asyncio
    async def test_send_error(self):
        """测试发送错误消息"""
        ws_cmd = WorkspaceCommands()
        send_message_func = AsyncMock()

        await ws_cmd._send_error(
            user_id="test_user",
            error="测试错误",
            send_message_func=send_message_func
        )

        assert send_message_func.called
        call_kwargs = send_message_func.call_args.kwargs
        card = call_kwargs.get('card')
        assert card is not None
        assert card.title == "错误"
        assert card.template_color == "red"