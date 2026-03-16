"""
工作空间切换端到端测试

直接调用业务逻辑，真实发送飞书消息

运行方式：
    pytest tests/integration/test_workspace_switch_e2e.py -v -s

注意：
    1. 需要在 .env 中配置 FEISHU_HOOK_NOTIFICATION_USER_ID
    2. 入口：直接调用业务逻辑（不启动服务）
    3. 出口：真实发送飞书消息
"""
import os
import subprocess
from pathlib import Path

import pytest
import pytest_asyncio

from src.config.settings import get_settings, reload_settings
from src.handlers.workspace_commands import WorkspaceCommands
from src.workspace_manager import get_workspace_manager
from src.feishu import FeishuAPI
from src.interfaces.im_platform import NormalizedCard

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestWorkspaceSwitchE2E:
    """工作空间切换端到端测试

    入口：直接调用业务逻辑
    出口：真实发送飞书消息
    """

    @pytest.fixture(scope="class")
    def feishu_api(self):
        """获取飞书 API 实例"""
        settings = get_settings()
        return FeishuAPI(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)

    @pytest.fixture(scope="class")
    def user_id(self):
        """获取飞书用户 ID"""
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")

        uid = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
        if not uid:
            pytest.skip("❌ 未配置 FEISHU_HOOK_NOTIFICATION_USER_ID，跳过端到端测试")
        return uid

    @pytest.fixture(autouse=True)
    def setup_test_workspaces(self):
        """设置测试工作空间"""
        test_root = PROJECT_ROOT / "docs" / "testcases" / "workspace_switch_test"
        alpha = test_root / "workspace_alpha"
        beta = test_root / "workspace_beta"

        assert test_root.exists(), f"测试工作空间根目录不存在: {test_root}"
        assert alpha.exists(), f"workspace_alpha 目录不存在: {alpha}"
        assert beta.exists(), f"workspace_beta 目录不存在: {beta}"

        # 保存原始环境变量
        original_root = os.environ.get("WORKSPACE_ROOT_DIR")
        original_default = os.environ.get("WORKSPACE_DEFAULT_DIR")
        original_enabled = os.environ.get("WORKSPACE_DISCOVERY_ENABLED")

        # 设置测试环境变量
        os.environ["WORKSPACE_ROOT_DIR"] = str(test_root)
        os.environ["WORKSPACE_DEFAULT_DIR"] = str(alpha)
        os.environ["WORKSPACE_DISCOVERY_ENABLED"] = "True"

        # 更新 settings
        settings = get_settings()
        settings.workspace_root_dir = test_root
        settings.workspace_default_dir = alpha
        settings.workspace_discovery_enabled = True

        # 计算需要清理的 session 名称
        def get_session_name(workspace_path: str) -> str:
            path_str = str(workspace_path).strip('/')
            return f"cc-{path_str.replace('/', '-')}"

        sessions_to_kill = [
            get_session_name(str(alpha)),
            get_session_name(str(beta))
        ]

        yield {
            "root": test_root,
            "alpha": alpha,
            "beta": beta,
            "sessions_to_kill": sessions_to_kill
        }

        # 清理 tmux sessions
        print(f"\n🧹 清理测试 tmux sessions: {sessions_to_kill}")
        try:
            result = subprocess.run(
                ["tmux", "list-sessions", "-F", "#{session_name}"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                running_sessions = result.stdout.strip().split('\n')
                for session in running_sessions:
                    if session in sessions_to_kill:
                        subprocess.run(
                            ["tmux", "kill-session", "-t", session],
                            capture_output=True, timeout=5
                        )
                        print(f"   ✓ 已清理: {session}")
        except Exception as e:
            print(f"   ✗ 清理失败: {e}")

        # 恢复环境变量
        for key, original in [
            ("WORKSPACE_ROOT_DIR", original_root),
            ("WORKSPACE_DEFAULT_DIR", original_default),
            ("WORKSPACE_DISCOVERY_ENABLED", original_enabled)
        ]:
            if original is not None:
                os.environ[key] = original
            else:
                os.environ.pop(key, None)

        reload_settings()

    async def _send_real_message(self, feishu_api: FeishuAPI, user_id: str, card: NormalizedCard):
        """真实发送飞书消息"""
        # 构建 Lark 卡片格式
        import json

        card_content = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": card.title},
                "template": card.template_color
            },
            "body": {
                "elements": [
                    {"tag": "markdown", "content": card.content}
                ]
            }
        }

        await feishu_api.send_message(user_id, json.dumps(card_content, ensure_ascii=False))
        print(f"   📤 已发送飞书卡片: {card.title}")

    # ==================== 测试用例 ====================

    @pytest.mark.asyncio
    async def test_01_workspace_list(self, feishu_api, user_id, setup_test_workspaces):
        """测试 #ws 命令（显示工作空间列表）"""
        print(f"\n{'='*60}")
        print(f"📤 测试 1: 显示工作空间列表")
        print(f"{'='*60}")

        sent_cards = []

        async def send_func(uid, card=None, message=None):
            if card:
                sent_cards.append(card)
                await self._send_real_message(feishu_api, uid, card)

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id=user_id,
            args="",
            send_message_func=send_func
        )

        assert len(sent_cards) == 1
        assert "workspace_alpha" in sent_cards[0].content
        assert "workspace_beta" in sent_cards[0].content
        print(f"✅ 工作空间列表卡片已发送")

    @pytest.mark.asyncio
    async def test_02_switch_to_alpha(self, feishu_api, user_id, setup_test_workspaces):
        """测试切换到 workspace_alpha"""
        print(f"\n{'='*60}")
        print(f"📤 测试 2: 切换到 workspace_alpha")
        print(f"{'='*60}")

        sent_cards = []

        async def send_func(uid, card=None, message=None):
            if card:
                sent_cards.append(card)
                await self._send_real_message(feishu_api, uid, card)

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id=user_id,
            args="1",
            send_message_func=send_func
        )

        assert len(sent_cards) == 1
        assert "workspace_alpha" in sent_cards[0].title
        assert sent_cards[0].template_color == "green"
        print(f"✅ 切换成功卡片已发送")

    @pytest.mark.asyncio
    async def test_03_switch_to_beta(self, feishu_api, user_id, setup_test_workspaces):
        """测试切换到 workspace_beta"""
        print(f"\n{'='*60}")
        print(f"📤 测试 3: 切换到 workspace_beta")
        print(f"{'='*60}")

        sent_cards = []

        async def send_func(uid, card=None, message=None):
            if card:
                sent_cards.append(card)
                await self._send_real_message(feishu_api, uid, card)

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id=user_id,
            args="2",
            send_message_func=send_func
        )

        assert len(sent_cards) == 1
        assert "workspace_beta" in sent_cards[0].title
        assert sent_cards[0].template_color == "green"
        print(f"✅ 切换成功卡片已发送")

    @pytest.mark.asyncio
    async def test_04_invalid_workspace_number(self, feishu_api, user_id, setup_test_workspaces):
        """测试无效序号"""
        print(f"\n{'='*60}")
        print(f"📤 测试 4: 无效序号")
        print(f"{'='*60}")

        sent_cards = []

        async def send_func(uid, card=None, message=None):
            if card:
                sent_cards.append(card)
                await self._send_real_message(feishu_api, uid, card)

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id=user_id,
            args="99",
            send_message_func=send_func
        )

        assert len(sent_cards) == 1
        assert sent_cards[0].card_type == "error"
        assert sent_cards[0].template_color == "red"
        print(f"✅ 错误卡片已发送")

    @pytest.mark.asyncio
    async def test_05_switch_back_to_alpha(self, feishu_api, user_id, setup_test_workspaces):
        """测试切换回 workspace_alpha"""
        print(f"\n{'='*60}")
        print(f"📤 测试 5: 切换回 workspace_alpha")
        print(f"{'='*60}")

        sent_cards = []

        async def send_func(uid, card=None, message=None):
            if card:
                sent_cards.append(card)
                await self._send_real_message(feishu_api, uid, card)

        workspace_commands = WorkspaceCommands()
        await workspace_commands.handle_workspace_command(
            user_id=user_id,
            args="1",
            send_message_func=send_func
        )

        assert len(sent_cards) == 1
        assert "workspace_alpha" in sent_cards[0].title
        print(f"✅ 切换成功卡片已发送")

        print(f"\n{'='*60}")
        print("🎉 端到端测试完成！")
        print("📱 请在飞书中确认收到了 5 张卡片")
        print(f"{'='*60}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
