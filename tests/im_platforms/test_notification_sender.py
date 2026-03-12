"""
测试通知发送器 (N011)
测试节点：多平台支持 - NotificationSender
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.im_platforms.notification_sender import (
    INotificationSender,
    StaticNotificationSender,
    DynamicBroadcastSender,
    PlatformTargetedSender,
    MultiPlatformTargetedSender,
)
from src.im_platforms.multi_platform_manager import MultiPlatformManager
from src.interfaces.im_platform import IIMPlatform, NormalizedCard, MessageType


class MockPlatform(IIMPlatform):
    """模拟平台实现"""

    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail

    async def send_message(self, user_id: str, content: str, message_type: MessageType = MessageType.TEXT) -> bool:
        if self.should_fail:
            raise Exception(f"{self.name} send failed")
        return True

    async def send_card(self, user_id: str, card: NormalizedCard) -> bool:
        if self.should_fail:
            raise Exception(f"{self.name} send card failed")
        return True

    async def send_file(self, user_id: str, file_key: str) -> bool:
        return True

    async def download_file(self, message_id: str, file_key: str, save_dir: Path = None) -> Path:
        return None

    async def get_user_info(self, user_id: str):
        return None

    async def upload_file(self, file_path: Path, file_type: str = "stream") -> str:
        return "file_key"

    def parse_event(self, event_data: dict):
        return None

    def is_platform_command(self, content: str) -> bool:
        return False


class TestStaticNotificationSender:
    """测试静态通知发送器"""

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """测试成功发送消息"""
        platform = MockPlatform("feishu")
        sender = StaticNotificationSender(platform)

        result = await sender.send_message("user123", "test message")

        assert result

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        """测试发送消息失败"""
        platform = MockPlatform("feishu", should_fail=True)
        sender = StaticNotificationSender(platform)

        result = await sender.send_message("user123", "test message")

        assert not result

    @pytest.mark.asyncio
    async def test_send_card_success(self):
        """测试成功发送卡片"""
        platform = MockPlatform("feishu")
        sender = StaticNotificationSender(platform)
        card = NormalizedCard("test", "Test Card", "Test content")

        result = await sender.send_card("user123", card)

        assert result

    @pytest.mark.asyncio
    async def test_send_card_failure(self):
        """测试发送卡片失败"""
        platform = MockPlatform("feishu", should_fail=True)
        sender = StaticNotificationSender(platform)
        card = NormalizedCard("test", "Test Card", "Test content")

        result = await sender.send_card("user123", card)

        assert not result


class TestDynamicBroadcastSender:
    """测试动态广播发送器"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = MultiPlatformManager()

    @pytest.mark.asyncio
    async def test_send_message_to_connected(self):
        """测试发送消息到已连接平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")
        discord = MockPlatform("discord")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)
        self.manager.register_platform("discord", discord)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)
        self.manager.set_connected_status("discord", False)

        sender = DynamicBroadcastSender(self.manager)
        result = await sender.send_message("user123", "test message")

        # 至少有一个平台成功就返回 True
        assert result

    @pytest.mark.asyncio
    async def test_send_message_broadcast_all(self):
        """测试广播消息到所有平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        self.manager.set_connected_status("feishu", False)
        self.manager.set_connected_status("slack", False)

        sender = DynamicBroadcastSender(self.manager)
        result = await sender.send_message("user123", "test message")

        assert result

    @pytest.mark.asyncio
    async def test_send_message_all_fail(self):
        """测试所有平台都发送失败"""
        feishu = MockPlatform("feishu", should_fail=True)
        slack = MockPlatform("slack", should_fail=True)

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)

        sender = DynamicBroadcastSender(self.manager)
        result = await sender.send_message("user123", "test message")

        assert not result

    @pytest.mark.asyncio
    async def test_send_card_to_connected(self):
        """测试发送卡片到已连接平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)

        card = NormalizedCard("test", "Test Card", "Test content")
        sender = DynamicBroadcastSender(self.manager)
        result = await sender.send_card("user123", card)

        assert result


class TestPlatformTargetedSender:
    """测试平台定向发送器"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = MultiPlatformManager()
        self.feishu = MockPlatform("feishu")
        self.slack = MockPlatform("slack")

        self.manager.register_platform("feishu", self.feishu)
        self.manager.register_platform("slack", self.slack)

    @pytest.mark.asyncio
    async def test_platform_name_property(self):
        """测试平台名称属性"""
        sender = PlatformTargetedSender("feishu", self.manager)

        assert sender.platform_name == "feishu"

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """测试发送消息到指定平台"""
        sender = PlatformTargetedSender("feishu", self.manager)
        result = await sender.send_message("user123", "test message")

        assert result

    @pytest.mark.asyncio
    async def test_send_message_to_nonexistent_platform(self):
        """测试发送到不存在的平台"""
        sender = PlatformTargetedSender("nonexistent", self.manager)
        result = await sender.send_message("user123", "test message")

        assert not result

    @pytest.mark.asyncio
    async def test_send_card_success(self):
        """测试发送卡片到指定平台"""
        card = NormalizedCard("test", "Test Card", "Test content")
        sender = PlatformTargetedSender("feishu", self.manager)

        result = await sender.send_card("user123", card)

        assert result

    @pytest.mark.asyncio
    async def test_send_card_to_nonexistent_platform(self):
        """测试发送卡片到不存在的平台"""
        card = NormalizedCard("test", "Test Card", "Test content")
        sender = PlatformTargetedSender("nonexistent", self.manager)

        result = await sender.send_card("user123", card)

        assert not result


class TestMultiPlatformTargetedSender:
    """测试多平台定向发送器"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = MultiPlatformManager()
        self.feishu = MockPlatform("feishu")
        self.slack = MockPlatform("slack")
        self.discord = MockPlatform("discord")

        self.manager.register_platform("feishu", self.feishu)
        self.manager.register_platform("slack", self.slack)
        self.manager.register_platform("discord", self.discord)

    @pytest.mark.asyncio
    async def test_platform_names_property(self):
        """测试平台名称列表属性"""
        sender = MultiPlatformTargetedSender(["feishu", "slack"], self.manager)

        names = sender.platform_names
        assert names == ["feishu", "slack"]
        # 修改返回值不应该影响原始列表
        names.append("new")
        assert sender.platform_names == ["feishu", "slack"]

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """测试发送消息到多个平台"""
        sender = MultiPlatformTargetedSender(["feishu", "slack"], self.manager)
        result = await sender.send_message("user123", "test message")

        assert result

    @pytest.mark.asyncio
    async def test_send_message_with_partial_failure(self):
        """测试部分平台发送失败的情况"""
        failing_slack = MockPlatform("slack", should_fail=True)
        self.manager.unregister_platform("slack")
        self.manager.register_platform("slack", failing_slack)

        sender = MultiPlatformTargetedSender(["feishu", "slack"], self.manager)
        result = await sender.send_message("user123", "test message")

        # 只要有一个成功就返回 True
        assert result

    @pytest.mark.asyncio
    async def test_send_message_all_fail(self):
        """测试所有平台都发送失败"""
        failing_feishu = MockPlatform("feishu", should_fail=True)
        failing_slack = MockPlatform("slack", should_fail=True)

        self.manager.unregister_platform("feishu")
        self.manager.unregister_platform("slack")
        self.manager.register_platform("feishu", failing_feishu)
        self.manager.register_platform("slack", failing_slack)

        sender = MultiPlatformTargetedSender(["feishu", "slack"], self.manager)
        result = await sender.send_message("user123", "test message")

        assert not result

    @pytest.mark.asyncio
    async def test_send_card_success(self):
        """测试发送卡片到多个平台"""
        card = NormalizedCard("test", "Test Card", "Test content")
        sender = MultiPlatformTargetedSender(["feishu", "slack"], self.manager)

        result = await sender.send_card("user123", card)

        assert result
