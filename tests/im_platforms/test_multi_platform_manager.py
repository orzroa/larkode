"""
测试多平台管理器 (N011)
测试节点：多平台支持 - MultiPlatformManager
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
import sys
sys.path.insert(0, str(PROJECT_ROOT))

from src.im_platforms.multi_platform_manager import MultiPlatformManager
from src.interfaces.im_platform import IIMPlatform, NormalizedCard, MessageType


class MockPlatform(IIMPlatform):
    """模拟平台实现"""

    def __init__(self, name: str, should_fail: bool = False):
        self.name = name
        self.should_fail = should_fail
        self.send_message_called = False
        self.send_card_called = False

    async def send_message(self, user_id: str, content: str, message_type: MessageType = MessageType.TEXT) -> bool:
        self.send_message_called = True
        if self.should_fail:
            raise Exception(f"{self.name} send failed")
        return True

    async def send_card(self, user_id: str, card: NormalizedCard) -> bool:
        self.send_card_called = True
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


class TestMultiPlatformManager:
    """测试多平台管理器"""

    def setup_method(self):
        """设置测试环境"""
        self.manager = MultiPlatformManager()

    def test_register_platform(self):
        """测试注册平台"""
        platform = MockPlatform("feishu")
        self.manager.register_platform("feishu", platform)

        assert self.manager.is_platform_registered("feishu")
        assert self.manager.get_platform("feishu") == platform
        assert "feishu" in self.manager.get_platform_names()

    def test_register_duplicate_platform(self):
        """测试注册重复平台"""
        platform1 = MockPlatform("feishu")
        platform2 = MockPlatform("feishu")

        self.manager.register_platform("feishu", platform1)
        self.manager.register_platform("feishu", platform2)

        # 应该覆盖旧的平台
        assert self.manager.get_platform("feishu") == platform2
        assert len(self.manager.get_all_platforms()) == 1

    def test_unregister_platform(self):
        """测试注销平台"""
        platform = MockPlatform("feishu")
        self.manager.register_platform("feishu", platform)

        unregistered = self.manager.unregister_platform("feishu")

        assert unregistered == platform
        assert not self.manager.is_platform_registered("feishu")
        assert self.manager.get_platform("feishu") is None

    def test_unregister_nonexistent_platform(self):
        """测试注销不存在的平台"""
        unregistered = self.manager.unregister_platform("nonexistent")
        assert unregistered is None

    def test_get_platform_names_sorted(self):
        """测试获取排序的平台名称"""
        self.manager.register_platform("zebra", MockPlatform("zebra"))
        self.manager.register_platform("alpha", MockPlatform("alpha"))
        self.manager.register_platform("beta", MockPlatform("beta"))

        names = self.manager.get_platform_names()
        assert names == ["alpha", "beta", "zebra"]

    def test_connection_status_initial_state(self):
        """测试初始连接状态"""
        platform = MockPlatform("feishu")
        self.manager.register_platform("feishu", platform)

        assert not self.manager.is_connected("feishu")
        assert len(self.manager.get_connected_platforms()) == 0

    def test_set_connected_status(self):
        """测试设置连接状态"""
        platform = MockPlatform("feishu")
        self.manager.register_platform("feishu", platform)

        self.manager.set_connected_status("feishu", True)
        assert self.manager.is_connected("feishu")

        self.manager.set_connected_status("feishu", False)
        assert not self.manager.is_connected("feishu")

    def test_set_connected_status_nonexistent(self):
        """测试为不存在的平台设置连接状态"""
        # 不应该抛出异常
        self.manager.set_connected_status("nonexistent", True)
        assert not self.manager.is_connected("nonexistent")

    def test_get_connected_platforms(self):
        """测试获取已连接的平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")
        discord = MockPlatform("discord")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)
        self.manager.register_platform("discord", discord)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)
        self.manager.set_connected_status("discord", False)

        connected = self.manager.get_connected_platforms()
        assert len(connected) == 2
        assert "feishu" in connected
        assert "slack" in connected
        assert "discord" not in connected

    def test_get_all_platforms(self):
        """测试获取所有平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        all_platforms = self.manager.get_all_platforms()
        assert len(all_platforms) == 2
        assert all_platforms["feishu"] == feishu
        assert all_platforms["slack"] == slack

    @pytest.mark.asyncio
    async def test_broadcast_message_to_connected_only(self):
        """测试广播消息到已连接平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")
        discord = MockPlatform("discord")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)
        self.manager.register_platform("discord", discord)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)
        self.manager.set_connected_status("discord", False)

        results = await self.manager.broadcast_message("user123", "test message")

        # 只有已连接的平台在结果中
        assert len(results) == 2
        assert results["feishu"] == True
        assert results["slack"] == True
        assert "discord" not in results

        assert feishu.send_message_called
        assert slack.send_message_called
        assert not discord.send_message_called

    @pytest.mark.asyncio
    async def test_broadcast_message_to_all(self):
        """测试广播消息到所有平台（包括未连接的）"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        # 都不连接
        self.manager.set_connected_status("feishu", False)
        self.manager.set_connected_status("slack", False)

        results = await self.manager.broadcast_message("user123", "test message", include_all=True)

        assert results["feishu"] == True
        assert results["slack"] == True

        assert feishu.send_message_called
        assert slack.send_message_called

    @pytest.mark.asyncio
    async def test_broadcast_message_with_failure(self):
        """测试广播消息时的错误处理"""
        feishu = MockPlatform("feishu", should_fail=False)
        slack = MockPlatform("slack", should_fail=True)

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)

        results = await self.manager.broadcast_message("user123", "test message")

        assert results["feishu"] == True
        assert results["slack"] == False

    @pytest.mark.asyncio
    async def test_broadcast_card(self):
        """测试广播卡片"""
        card = NormalizedCard("test", "Test Card", "Test content")

        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        self.manager.set_connected_status("feishu", True)
        self.manager.set_connected_status("slack", True)

        results = await self.manager.broadcast_card("user123", card)

        assert results["feishu"] == True
        assert results["slack"] == True

        assert feishu.send_card_called
        assert slack.send_card_called

    @pytest.mark.asyncio
    async def test_send_to_platform(self):
        """测试发送到指定平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        result = await self.manager.send_to_platform("feishu", "user123", "test message")

        assert result
        assert feishu.send_message_called
        assert not slack.send_message_called

    @pytest.mark.asyncio
    async def test_send_to_nonexistent_platform(self):
        """测试发送到不存在的平台"""
        result = await self.manager.send_to_platform("nonexistent", "user123", "test message")
        assert not result

    @pytest.mark.asyncio
    async def test_send_card_to_platform(self):
        """测试发送卡片到指定平台"""
        card = NormalizedCard("test", "Test Card", "Test content")

        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        result = await self.manager.send_card_to_platform("feishu", "user123", card)

        assert result
        assert feishu.send_card_called
        assert not slack.send_card_called

    @pytest.mark.asyncio
    async def test_send_to_platforms(self):
        """测试发送到多个平台"""
        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")
        discord = MockPlatform("discord")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)
        self.manager.register_platform("discord", discord)

        results = await self.manager.send_to_platforms(
            ["feishu", "discord"], "user123", "test message"
        )

        assert results["feishu"] == True
        assert "slack" not in results
        assert results["discord"] == True

        assert feishu.send_message_called
        assert not slack.send_message_called
        assert discord.send_message_called

    @pytest.mark.asyncio
    async def test_send_card_to_platforms(self):
        """测试发送卡片到多个平台"""
        card = NormalizedCard("test", "Test Card", "Test content")

        feishu = MockPlatform("feishu")
        slack = MockPlatform("slack")

        self.manager.register_platform("feishu", feishu)
        self.manager.register_platform("slack", slack)

        results = await self.manager.send_card_to_platforms(
            ["feishu", "slack"], "user123", card
        )

        assert results["feishu"] == True
        assert results["slack"] == True

        assert feishu.send_card_called
        assert slack.send_card_called
