"""
工作空间切换功能集成测试

测试工作空间的枚举、切换等功能
使用 mock 发送函数，不真实发送飞书消息

运行方式：
    pytest tests/integration/test_workspace_switch.py -v -s
"""
import pytest

from src.handlers.workspace_commands import WorkspaceCommands
from src.interfaces.im_platform import NormalizedCard
from src.workspace_manager import get_workspace_manager


class TestWorkspaceSwitch:
    """工作空间切换集成测试（使用 mock 发送）"""

    @pytest.fixture
    def mock_send_func(self):
        """创建 mock 发送函数，记录发送的卡片"""
        sent_cards = []

        async def _send(user_id: str, card: NormalizedCard = None, message: str = None):
            if card:
                sent_cards.append({"user_id": user_id, "card": card})
            return True

        _send.sent_cards = sent_cards
        return _send

    # ==================== 测试用例 ====================

    def test_setup_workspaces(self, test_workspaces):
        """验证测试工作空间目录结构正确"""
        assert test_workspaces["alpha"].exists()
        assert test_workspaces["beta"].exists()
        assert (test_workspaces["alpha"] / "README.md").exists()
        assert (test_workspaces["beta"] / "README.md").exists()

    @pytest.mark.asyncio
    async def test_enumerate_workspaces(self, test_workspaces):
        """测试枚举工作空间"""
        workspace_manager = get_workspace_manager()
        workspaces = workspace_manager.get_workspaces()

        assert len(workspaces) == 2
        workspace_names = {ws["name"] for ws in workspaces}
        assert "workspace_alpha" in workspace_names
        assert "workspace_beta" in workspace_names

        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["alpha"]) == current

    @pytest.mark.asyncio
    async def test_workspace_list_card(self, test_workspaces, mock_send_func):
        """测试工作空间列表卡片"""
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="",
            send_message_func=mock_send_func
        )

        assert len(mock_send_func.sent_cards) == 1
        card = mock_send_func.sent_cards[0]["card"]
        assert isinstance(card, NormalizedCard)
        assert "workspace_alpha" in card.content
        assert "workspace_beta" in card.content

    @pytest.mark.asyncio
    async def test_switch_to_alpha(self, test_workspaces, mock_send_func):
        """测试切换到 workspace_alpha"""
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="1",
            send_message_func=mock_send_func
        )

        assert len(mock_send_func.sent_cards) == 1
        card = mock_send_func.sent_cards[0]["card"]
        assert "workspace_alpha" in card.title
        assert card.template_color == "green"

        workspace_manager = get_workspace_manager()
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["alpha"]) == current

    @pytest.mark.asyncio
    async def test_switch_to_beta(self, test_workspaces, mock_send_func):
        """测试切换到 workspace_beta"""
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="2",
            send_message_func=mock_send_func
        )

        assert len(mock_send_func.sent_cards) == 1
        card = mock_send_func.sent_cards[0]["card"]
        assert "workspace_beta" in card.title
        assert card.template_color == "green"

        workspace_manager = get_workspace_manager()
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["beta"]) == current

    @pytest.mark.asyncio
    async def test_switch_back_and_forth(self, test_workspaces, mock_send_func):
        """测试来回切换工作空间"""
        workspace_commands = WorkspaceCommands()
        workspace_manager = get_workspace_manager()

        # alpha -> beta -> alpha
        await workspace_commands.handle_workspace_command(
            user_id="test_user", args="1", send_message_func=mock_send_func
        )
        assert str(test_workspaces["alpha"]) == workspace_manager.get_current_workspace()

        await workspace_commands.handle_workspace_command(
            user_id="test_user", args="2", send_message_func=mock_send_func
        )
        assert str(test_workspaces["beta"]) == workspace_manager.get_current_workspace()

        await workspace_commands.handle_workspace_command(
            user_id="test_user", args="1", send_message_func=mock_send_func
        )
        assert str(test_workspaces["alpha"]) == workspace_manager.get_current_workspace()

        assert len(mock_send_func.sent_cards) == 3

    @pytest.mark.asyncio
    async def test_invalid_workspace_number(self, test_workspaces, mock_send_func):
        """测试无效序号"""
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="99",
            send_message_func=mock_send_func
        )

        assert len(mock_send_func.sent_cards) == 1
        card = mock_send_func.sent_cards[0]["card"]
        assert card.card_type == "error"
        assert card.template_color == "red"

    @pytest.mark.asyncio
    async def test_invalid_input_not_number(self, test_workspaces, mock_send_func):
        """测试非数字输入"""
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="abc",
            send_message_func=mock_send_func
        )

        assert len(mock_send_func.sent_cards) == 1
        card = mock_send_func.sent_cards[0]["card"]
        assert card.card_type == "error"
        assert card.template_color == "red"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
