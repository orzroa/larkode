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
from pathlib import Path

import pytest

from src.handlers.workspace_commands import WorkspaceCommands
from src.interfaces.im_platform import NormalizedCard

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


class TestWorkspaceSwitchE2E:
    """工作空间切换端到端测试

    入口：直接调用业务逻辑
    出口：真实发送飞书消息
    """

    async def _send_real_message(self, feishu_api, user_id: str, card: NormalizedCard):
        """真实发送飞书消息"""
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
    async def test_01_workspace_list(self, feishu_api, user_id, test_workspaces):
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
    async def test_02_switch_to_alpha(self, feishu_api, user_id, test_workspaces):
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
    async def test_03_switch_to_beta(self, feishu_api, user_id, test_workspaces):
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
    async def test_04_invalid_workspace_number(self, feishu_api, user_id, test_workspaces):
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
    async def test_05_switch_back_to_alpha(self, feishu_api, user_id, test_workspaces):
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