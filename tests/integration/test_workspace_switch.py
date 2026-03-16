"""
工作空间切换功能集成测试

测试工作空间的枚举、切换、文件读取等功能
"""
import asyncio
import os
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio

from src.config.settings import get_settings, reload_settings
from src.handlers.workspace_commands import WorkspaceCommands
from src.workspace_manager import get_workspace_manager
from src.interfaces.im_platform import NormalizedCard


class TestWorkspaceSwitch:
    """工作空间切换集成测试"""

    @pytest.fixture(autouse=True)
    def test_workspaces(self):
        """使用 docs/testcases/workspace_switch_test 作为测试工作空间"""
        # 使用项目中的测试工作空间目录
        test_root = Path(__file__).parent.parent.parent / "docs" / "testcases" / "workspace_switch_test"
        alpha = test_root / "workspace_alpha"
        beta = test_root / "workspace_beta"

        # 验证测试目录存在
        assert test_root.exists(), f"测试工作空间根目录不存在: {test_root}"
        assert alpha.exists(), f"workspace_alpha 目录不存在: {alpha}"
        assert beta.exists(), f"workspace_beta 目录不存在: {beta}"

        # 计算预期的 session 名称用于清理
        def get_session_name(workspace_path: str) -> str:
            path_str = str(workspace_path).strip('/')
            return f"cc-{path_str.replace('/', '-')}"

        alpha_session = get_session_name(str(alpha))
        beta_session = get_session_name(str(beta))

        # 设置环境变量（临时）
        original_root = os.environ.get("WORKSPACE_ROOT_DIR")
        original_default = os.environ.get("WORKSPACE_DEFAULT_DIR")
        original_enabled = os.environ.get("WORKSPACE_DISCOVERY_ENABLED")

        os.environ["WORKSPACE_ROOT_DIR"] = str(test_root)
        os.environ["WORKSPACE_DEFAULT_DIR"] = str(alpha)
        os.environ["WORKSPACE_DISCOVERY_ENABLED"] = "True"

        # 重新加载设置
        settings = get_settings()
        settings.workspace_root_dir = test_root
        settings.workspace_default_dir = alpha
        settings.workspace_discovery_enabled = True

        yield {
            "root": test_root,
            "alpha": alpha,
            "beta": beta,
            "sessions_to_kill": [alpha_session, beta_session]
        }

        # 清理测试创建的 tmux sessions
        print(f"\n🧹 清理测试 tmux sessions: {[alpha_session, beta_session]}")
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                running_sessions = result.stdout.strip().split('\n')
                for session in running_sessions:
                    if session in [alpha_session, beta_session]:
                        try:
                            subprocess.run(
                                ["tmux", "kill-session", "-t", session],
                                capture_output=True,
                                timeout=5
                            )
                            print(f"   ✓ 已清理: {session}")
                        except Exception as e:
                            print(f"   ✗ 清理失败 {session}: {e}")
        except Exception as e:
            print(f"   ✗ 列出 sessions 失败: {e}")

        # 恢复环境变量
        if original_root is not None:
            os.environ["WORKSPACE_ROOT_DIR"] = original_root
        else:
            os.environ.pop("WORKSPACE_ROOT_DIR", None)

        if original_default is not None:
            os.environ["WORKSPACE_DEFAULT_DIR"] = original_default
        else:
            os.environ.pop("WORKSPACE_DEFAULT_DIR", None)

        if original_enabled is not None:
            os.environ["WORKSPACE_DISCOVERY_ENABLED"] = original_enabled
        else:
            os.environ.pop("WORKSPACE_DISCOVERY_ENABLED", None)

        # 重新加载设置以恢复原始配置
        reload_settings()

    def test_setup_workspaces(self, test_workspaces):
        """验证测试工作空间目录结构正确"""
        # 验证目录存在
        assert test_workspaces["alpha"].exists()
        assert test_workspaces["beta"].exists()

        # 验证文件存在
        assert (test_workspaces["alpha"] / "README.md").exists()
        assert (test_workspaces["alpha"] / "test_file.txt").exists()
        assert (test_workspaces["beta"] / "README.md").exists()
        assert (test_workspaces["beta"] / "test_file.txt").exists()

        # 验证内容
        alpha_readme = (test_workspaces["alpha"] / "README.md").read_text(encoding='utf-8')
        assert alpha_readme == "This is workspace Alpha"

        beta_readme = (test_workspaces["beta"] / "README.md").read_text(encoding='utf-8')
        assert beta_readme == "This is workspace Beta"

    @pytest.mark.asyncio
    async def test_enumerate_workspaces(self, test_workspaces):
        """测试枚举工作空间"""
        # 调用真实的业务逻辑
        workspace_manager = get_workspace_manager()
        workspaces = workspace_manager.get_workspaces()

        assert len(workspaces) == 2

        assert len(workspaces) == 2

        # 验证工作空间列表包含两个测试工作空间
        workspace_names = {ws["name"] for ws in workspaces}
        assert "workspace_alpha" in workspace_names
        assert "workspace_beta" in workspace_names

        # 验证工作空间路径正确
        for ws in workspaces:
            if ws["name"] == "workspace_alpha":
                assert "docs/testcases/workspace_switch_test/workspace_alpha" in ws["path"], \
                    f"workspace_alpha 路径错误: {ws['path']}"
            elif ws["name"] == "workspace_beta":
                assert "docs/testcases/workspace_switch_test/workspace_beta" in ws["path"], \
                    f"workspace_beta 路径错误: {ws['path']}"

        # 验证默认工作空间是 alpha（路径也要匹配）
        current = workspace_manager.get_current_workspace()
        assert current is not None
        assert str(test_workspaces["alpha"]) == current, \
            f"默认工作空间应该是 {test_workspaces['alpha']}，实际是 {current}"

    @pytest.mark.asyncio
    async def test_workspace_list_card(self, test_workspaces):
        """测试工作空间列表卡片"""
        # 记录发送的卡片
        sent_cards = []

        async def mock_send_message(user_id, card=None, message=None):
            """模拟发送消息函数"""
            if card:
                sent_cards.append({
                    "user_id": user_id,
                    "card": card
                })

        # 调用真实的业务逻辑
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="",  # 无参数，显示列表
            send_message_func=mock_send_message
        )

        # 验证卡片内容
        assert len(sent_cards) == 1
        card = sent_cards[0]["card"]
        assert isinstance(card, NormalizedCard)
        assert card.card_type == "workspace_list"
        assert "workspace_alpha" in card.content
        assert "workspace_beta" in card.content
        assert card.title == "工作空间"

    @pytest.mark.asyncio
    async def test_switch_to_alpha_card(self, test_workspaces):
        """测试切换到 workspace_alpha 的卡片"""
        # 记录发送的卡片
        sent_cards = []

        async def mock_send_message(user_id, card=None, message=None):
            """模拟发送消息函数"""
            if card:
                sent_cards.append({
                    "user_id": user_id,
                    "card": card
                })

        # 调用真实的业务逻辑
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="1",  # 切换到 alpha
            send_message_func=mock_send_message
        )

        # 验证切换成功的卡片
        assert len(sent_cards) == 1
        card = sent_cards[0]["card"]
        assert isinstance(card, NormalizedCard)
        assert card.card_type == "success"
        assert "workspace_alpha" in card.title  # 标题应包含工作空间名称
        assert card.template_color == "green"

        # 验证当前工作空间是 alpha（路径也要匹配）
        workspace_manager = get_workspace_manager()
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["alpha"]) == current, \
            f"切换后工作空间应该是 {test_workspaces['alpha']}，实际是 {current}"

    @pytest.mark.asyncio
    async def test_switch_to_beta_card(self, test_workspaces):
        """测试切换到 workspace_beta 的卡片"""
        # 记录发送的卡片
        sent_cards = []

        async def mock_send_message(user_id, card=None, message=None):
            """模拟发送消息函数"""
            if card:
                sent_cards.append({
                    "user_id": user_id,
                    "card": card
                })

        # 调用真实的业务逻辑
        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="2",  # 切换到 beta
            send_message_func=mock_send_message
        )

        # 验证切换成功的卡片
        assert len(sent_cards) == 1
        card = sent_cards[0]["card"]
        assert isinstance(card, NormalizedCard)
        assert card.card_type == "success"
        assert "workspace_beta" in card.title
        assert card.template_color == "green"

        # 验证当前工作空间是 beta（路径也要匹配）
        workspace_manager = get_workspace_manager()
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["beta"]) == current, \
            f"切换后工作空间应该是 {test_workspaces['beta']}，实际是 {current}"

    @pytest.mark.asyncio
    async def test_switch_back_and_forth(self, test_workspaces):
        """测试来回切换工作空间"""
        sent_cards = []

        async def mock_send_message(user_id, card=None, message=None):
            """模拟发送消息函数"""
            if card:
                sent_cards.append({"card": card})

        workspace_commands = WorkspaceCommands()
        workspace_manager = get_workspace_manager()

        # 从 alpha 开始
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="1",
            send_message_func=mock_send_message
        )
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["alpha"]) == current, \
            f"应该是 {test_workspaces['alpha']}，实际是 {current}"

        # 切换到 beta
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="2",
            send_message_func=mock_send_message
        )
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["beta"]) == current, \
            f"应该是 {test_workspaces['beta']}，实际是 {current}"

        # 切换回 alpha
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="1",
            send_message_func=mock_send_message
        )
        current = workspace_manager.get_current_workspace()
        assert str(test_workspaces["alpha"]) == current, \
            f"应该是 {test_workspaces['alpha']}，实际是 {current}"

        # 验证发送了 3 张卡片（3 次切换）
        assert len(sent_cards) == 3

    @pytest.mark.asyncio
    async def test_invalid_workspace_number(self, test_workspaces):
        """测试切换到不存在的工作空间序号"""
        sent_cards = []

        async def mock_send_message(user_id, card=None, message=None):
            """模拟发送消息函数"""
            if card:
                sent_cards.append({"card": card})

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="99",  # 不存在的序号
            send_message_func=mock_send_message
        )

        # 验证错误卡片
        assert len(sent_cards) == 1
        card = sent_cards[0]["card"]
        assert isinstance(card, NormalizedCard)
        assert card.card_type == "error"
        assert card.template_color == "red"

    @pytest.mark.asyncio
    async def test_invalid_input_not_number(self, test_workspaces):
        """测试无效输入（非数字）"""
        sent_cards = []

        async def mock_send_message(user_id, card=None, message=None):
            """模拟发送消息函数"""
            if card:
                sent_cards.append({"card": card})

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id="test_user",
            args="abc",  # 非数字
            send_message_func=mock_send_message
        )

        # 验证错误卡片
        assert len(sent_cards) == 1
        card = sent_cards[0]["card"]
        assert isinstance(card, NormalizedCard)
        assert card.card_type == "error"
        assert card.template_color == "red"