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

                # 应该发送工作空间列表（选项卡：dict 而非 NormalizedCard）
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert isinstance(card, dict)
                assert card["schema"] == "2.0"
                title = card["header"]["title"]["content"]
                assert "工作空间" in title
                # 项目名应出现在按钮文本中
                button_texts = self._collect_button_texts(card)
                assert any("project1" in t for t in button_texts)
                assert any("project2" in t for t in button_texts)

    @staticmethod
    def _collect_button_texts(card):
        """收集卡片中所有按钮的文本（V2 schema: column_set + column + button），返回 list[str]"""
        texts = []
        for element in card.get("body", {}).get("elements", []):
            if element.get("tag") == "column_set":
                for column in element.get("columns", []):
                    for el in column.get("elements", []):
                        if el.get("tag") == "button":
                            texts.append(el["text"]["content"])
        return texts

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
        """测试无效输入（非数字且无匹配）"""
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
                    args="abc",  # 非数字输入，按名称搜索无匹配
                    send_message_func=send_message_func
                )

                # 应该发送错误消息（名称搜索无匹配）
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
        """测试默认工作空间不在列表中时仍能正常渲染选项卡

        新版 OptionCard 不再在列表卡片里写警告文案——警告信息改为通过其他渠道传达。
        此处只验证：列表能正常渲染、不抛异常。
        """
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

                # 选项卡能正常渲染
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert isinstance(card, dict)
                assert card["schema"] == "2.0"
                # 至少有一个按钮（V2 schema: column_set 包裹 column + button）
                has_button = False
                for e in card.get("body", {}).get("elements", []):
                    if e.get("tag") == "column_set":
                        for column in e.get("columns", []):
                            for el in column.get("elements", []):
                                if el.get("tag") == "button":
                                    has_button = True
                assert has_button

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

    @pytest.mark.asyncio
    async def test_handle_workspace_command_by_name_unique_match(self):
        """测试按名称搜索工作空间 - 唯一匹配"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'github/larkode', 'path': '/tmp/github/larkode', 'depth': 2, 'is_running': False, 'is_default': True, 'is_current': False},
            {'name': 'github/other', 'path': '/tmp/github/other', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False}
        ]
        mock_manager.switch_workspace.return_value = (True, "切换成功")

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="larkode",  # 名称搜索
                    send_message_func=send_message_func
                )

                # 应该发送成功消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert "成功" in card.title

    @pytest.mark.asyncio
    async def test_handle_workspace_command_group_name_opens_level2(self):
        """测试一级目录名作为 args，应展示 level-2 内容列表而非触发多匹配错误"""
        ws_cmd = WorkspaceCommands()

        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # 5 个工作空间，其中 github 下有 3 个
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'osc/project1', 'path': '/tmp/osc/project1', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False},
            {'name': 'github', 'path': '/tmp/github', 'depth': 1, 'is_running': True, 'is_default': False, 'is_current': True},
            {'name': 'github/aiTermLark', 'path': '/tmp/github/aiTermLark', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False},
            {'name': 'github/druid', 'path': '/tmp/github/druid', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False},
            {'name': 'github/larkode', 'path': '/tmp/github/larkode', 'depth': 2, 'is_running': False, 'is_default': True, 'is_current': False},
        ]

        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="github",  # 精确匹配一级目录名
                    send_message_func=send_message_func,
                )

                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert isinstance(card, dict)
                assert card["schema"] == "2.0"
                # 顶部"整个一级目录"按钮 + 三个子工作空间按钮（不带 group 前缀）
                button_texts = self._collect_button_texts(card)
                assert any("📁 整个 github/" in t for t in button_texts)
                # 不应再显示 group 前缀
                assert not any("github/aiTermLark" in t for t in button_texts), "子工作空间按钮不应包含 group 前缀"
                assert not any("github/druid" in t for t in button_texts)
                assert not any("github/larkode" in t for t in button_texts)
                # 只显示子工作空间名
                assert any("aiTermLark" in t for t in button_texts)
                assert any("druid" in t for t in button_texts)
                assert any("larkode" in t for t in button_texts)
                # 不应有重复的 "1. 1." 编号
                assert not any("1. 1." in t for t in button_texts)
                # 不应有翻页行（page_size=999，总是一页）
                column_sets = [e for e in card["body"]["elements"] if e.get("tag") == "column_set"]
                # 1 个 parent button row + 1 个 workspace button row = 2 行
                assert len(column_sets) == 2

    @pytest.mark.asyncio
    async def test_handle_workspace_command_by_name_no_match(self):
        """测试按名称搜索工作空间 - 无匹配"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'github/larkode', 'path': '/tmp/github/larkode', 'depth': 2, 'is_running': False, 'is_default': True, 'is_current': False}
        ]

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="nonexistent",  # 不存在的名称
                    send_message_func=send_message_func
                )

                # 应该发送错误消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert card.title == "错误"
                assert "未找到匹配的工作空间" in card.content
                assert "nonexistent" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_substring_multiple_matches(self):
        """子串匹配命中多个时（且非 group 精确匹配），展示多匹配列表"""
        ws_cmd = WorkspaceCommands()

        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # 注意：没有 group 名能精确匹配 "demo"（一级目录是 alpha/beta/gamma）
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'alpha/demo1', 'path': '/tmp/alpha/demo1', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False},
            {'name': 'beta/demo2', 'path': '/tmp/beta/demo2', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False},
            {'name': 'gamma/demo3', 'path': '/tmp/gamma/demo3', 'depth': 2, 'is_running': False, 'is_default': False, 'is_current': False},
        ]

        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="demo",  # 子串命中 3 个，且都不在 groups 精确匹配中
                    send_message_func=send_message_func,
                )

                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert card.title == "错误"
                assert "找到多个匹配的工作空间" in card.content
                # 三个匹配都应出现
                assert "alpha/demo1" in card.content
                assert "beta/demo2" in card.content
                assert "gamma/demo3" in card.content

    @pytest.mark.asyncio
    async def test_handle_workspace_command_by_name_case_insensitive(self):
        """测试按名称搜索 - 不区分大小写"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'GitHub/Larkode', 'path': '/tmp/GitHub/Larkode', 'depth': 2, 'is_running': False, 'is_default': True, 'is_current': False}
        ]
        mock_manager.switch_workspace.return_value = (True, "切换成功")

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="github",  # 小写搜索
                    send_message_func=send_message_func
                )

                # 应该发送成功消息（因为不区分大小写）
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert "成功" in card.title

    @pytest.mark.asyncio
    async def test_handle_workspace_command_by_path_match(self):
        """测试按路径搜索工作空间"""
        ws_cmd = WorkspaceCommands()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = Path("/tmp")

        # Mock workspace_manager
        mock_manager = MagicMock()
        mock_manager.get_workspaces.return_value = [
            {'name': 'larkode', 'path': '/home/ubuntu/Workspaces/github/larkode', 'depth': 3, 'is_running': False, 'is_default': True, 'is_current': False}
        ]
        mock_manager.switch_workspace.return_value = (True, "切换成功")

        # Mock send_message_func
        send_message_func = AsyncMock()

        with patch('src.handlers.workspace_commands.get_settings', return_value=mock_settings):
            with patch('src.handlers.workspace_commands.get_workspace_manager', return_value=mock_manager):
                await ws_cmd.handle_workspace_command(
                    user_id="test_user",
                    args="github/larkode",  # 路径部分匹配
                    send_message_func=send_message_func
                )

                # 应该发送成功消息
                assert send_message_func.called
                call_kwargs = send_message_func.call_args.kwargs
                card = call_kwargs.get('card')
                assert card is not None
                assert "成功" in card.title