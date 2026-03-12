"""
测试统一卡片发送器 (CardDispatcher)
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

import pytest

from src.card_dispatcher import CardDispatcher
from src.models import MessageSource


# Fixtures at module level
@pytest.fixture
def mock_feishu_api():
    """Mock 飞书 API"""
    api = MagicMock()
    api.upload_file = AsyncMock(return_value="test_file_key")
    api.send_file_message = AsyncMock(return_value=True)
    return api


@pytest.fixture
def mock_notification_sender():
    """Mock 通知发送器"""
    sender = MagicMock()
    sender.send_card = AsyncMock(return_value=True)
    sender.last_message_id = "msg_123"
    return sender


@pytest.fixture
def card_dispatcher(mock_feishu_api):
    """创建 CardDispatcher 实例"""
    dispatcher = CardDispatcher(feishu_api=mock_feishu_api)
    return dispatcher


class TestCardDispatcher:

    def test_initialization(self, card_dispatcher):
        """测试初始化"""
        assert card_dispatcher is not None
        assert card_dispatcher.feishu is not None
        assert card_dispatcher._card_id_manager is not None

    def test_get_default_max_length(self, card_dispatcher):
        """测试获取默认最大长度"""
        length = card_dispatcher.get_default_max_length()
        assert isinstance(length, int)
        assert length > 0

    def test_should_use_file_true_for_specific_types(self, card_dispatcher):
        """测试特定类型应该使用文件"""
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "true"
        for card_type in ["stop", "prompt", "permission", "tmux"]:
            assert card_dispatcher.should_use_file(card_type) is True
        del os.environ["USE_FILE_FOR_LONG_CONTENT"]

    def test_should_use_file_false_for_other_types(self, card_dispatcher):
        """测试其他类型不应该使用文件"""
        assert card_dispatcher.should_use_file("command") is False
        assert card_dispatcher.should_use_file("error") is False
        assert card_dispatcher.should_use_file("help") is False

    def test_should_use_file_disabled(self, card_dispatcher):
        """测试禁用文件模式"""
        os.environ["USE_FILE_FOR_LONG_CONTENT"] = "false"
        assert card_dispatcher.should_use_file("stop") is False
        del os.environ["USE_FILE_FOR_LONG_CONTENT"]

    def test_get_card_id(self, card_dispatcher):
        """测试获取卡片编号"""
        card_id = card_dispatcher._get_card_id()
        assert isinstance(card_id, int)
        assert card_id > 0

    def test_format_timestamp(self, card_dispatcher):
        """测试格式化时间戳"""
        iso_timestamp = "2026-03-12T10:30:45.123456"
        formatted = card_dispatcher._format_timestamp(iso_timestamp)
        assert "2026-03-12" in formatted
        assert "10:30:45" in formatted

    def test_build_display_content(self, card_dispatcher):
        """测试构建展示内容"""
        pure_content = "测试内容"
        card_id = 123
        timestamp = "2026-03-12T10:30:00"
        display = card_dispatcher._build_display_content(pure_content, card_id, timestamp)
        assert "📨 **卡片编号**: 123" in display
        assert pure_content in display
        assert "2026-03-12" in display


class TestCardDispatcherSendCard:
    """测试 CardDispatcher.send_card 方法"""

    @pytest.mark.asyncio
    async def test_send_short_card(self, mock_feishu_api, mock_notification_sender):
        """测试发送短内容卡片"""
        dispatcher = CardDispatcher(
            feishu_api=mock_feishu_api,
            notification_sender=mock_notification_sender
        )

        short_content = "这是一条短消息"
        msg_id, file_key = await dispatcher.send_card(
            user_id="test_user",
            card_type="command",
            title="命令确认",
            content=short_content,
            message_type="response",
            template_color="grey"
        )

        assert msg_id == "msg_123"
        assert file_key is None
        mock_notification_sender.send_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_long_card_with_file(self, mock_feishu_api, mock_notification_sender):
        """测试发送长内容卡片（触发文件上传）"""
        dispatcher = CardDispatcher(
            feishu_api=mock_feishu_api,
            notification_sender=mock_notification_sender
        )

        # 设置较短的最大长度以便测试
        long_content = "A" * 2000
        msg_id, file_key = await dispatcher.send_card(
            user_id="test_user",
            card_type="stop",
            title="回复完成",
            content=long_content,
            message_type="status",
            template_color="green",
            max_length=100  # 强制触发文件上传
        )

        assert msg_id is not None
        assert file_key == "test_file_key"
        mock_feishu_api.upload_file.assert_called_once()
        mock_feishu_api.send_file_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_card_with_custom_max_length(self, mock_feishu_api, mock_notification_sender):
        """测试使用自定义最大长度"""
        dispatcher = CardDispatcher(
            feishu_api=mock_feishu_api,
            notification_sender=mock_notification_sender
        )

        content = "A" * 200  # 200 字符
        msg_id, file_key = await dispatcher.send_card(
            user_id="test_user",
            card_type="stop",
            title="回复完成",
            content=content,
            message_type="status",
            template_color="green",
            max_length=300  # 设置更大的限制，不会触发文件上传
        )

        assert msg_id is not None
        assert file_key is None
        mock_feishu_api.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_card_with_message_source(self, mock_feishu_api, mock_notification_sender):
        """测试指定消息来源"""
        dispatcher = CardDispatcher(
            feishu_api=mock_feishu_api,
            notification_sender=mock_notification_sender
        )

        content = "Hook 通知"
        msg_id, file_key = await dispatcher.send_card(
            user_id="test_user",
            card_type="stop",
            title="回复完成",
            content=content,
            message_type="status",
            template_color="green",
            message_source=MessageSource.HOOK
        )

        assert msg_id is not None
        assert file_key is None

    @pytest.mark.asyncio
    async def test_send_card_different_card_types(self, mock_feishu_api, mock_notification_sender):
        """测试不同类型的卡片"""
        dispatcher = CardDispatcher(
            feishu_api=mock_feishu_api,
            notification_sender=mock_notification_sender
        )

        card_types = [
            ("command", "命令确认", "test command", "grey"),
            ("error", "错误", "test error", "red"),
            ("help", "帮助", "test help", "blue"),
            ("history", "历史记录", "test history", "grey"),
        ]

        for card_type, title, content, template in card_types:
            msg_id, file_key = await dispatcher.send_card(
                user_id="test_user",
                card_type=card_type,
                title=title,
                content=content,
                message_type="response",
                template_color=template
            )
            assert msg_id is not None

    @pytest.mark.asyncio
    async def test_send_card_without_notification_sender(self, mock_feishu_api):
        """测试没有 notification_sender 时使用 platform"""
        mock_platform = MagicMock()
        mock_platform.send_card = AsyncMock(return_value="msg_from_platform")

        dispatcher = CardDispatcher(
            feishu_api=mock_feishu_api,
            platform=mock_platform
        )

        content = "测试内容"
        msg_id, file_key = await dispatcher.send_card(
            user_id="test_user",
            card_type="command",
            title="命令确认",
            content=content,
            message_type="response",
            template_color="grey"
        )

        assert msg_id == "msg_from_platform"
        mock_platform.send_card.assert_called_once()


class TestCardDispatcherFileUpload:
    """测试文件上传功能"""

    @pytest.mark.asyncio
    async def test_upload_file_and_send(self, mock_feishu_api):
        """测试上传文件并发送"""
        dispatcher = CardDispatcher(feishu_api=mock_feishu_api)

        file_content = "文件内容" * 100
        file_key, display_content = await dispatcher._upload_file_and_send(
            user_id="test_user",
            file_content=file_content,
            card_type="stop",
            title="回复完成",
            template_color="green",
            card_id=123,
            timestamp="2026-03-12T10:30:00"
        )

        assert file_key == "test_file_key"
        assert "完整内容已保存为文件" in display_content or "文件上传" in display_content
        mock_feishu_api.upload_file.assert_called_once()
        mock_feishu_api.send_file_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_with_error(self, mock_feishu_api):
        """测试文件上传失败处理"""
        mock_feishu_api.upload_file = AsyncMock(return_value=None)  # 上传失败

        dispatcher = CardDispatcher(feishu_api=mock_feishu_api)

        file_content = "文件内容" * 100
        file_key, display_content = await dispatcher._upload_file_and_send(
            user_id="test_user",
            file_content=file_content,
            card_type="stop",
            title="回复完成",
            template_color="green",
            card_id=123,
            timestamp="2026-03-12T10:30:00"
        )

        assert file_key is None
        assert "文件上传失败" in display_content or "文件上传不可用" in display_content


class TestCardDispatcherSetters:
    """测试 CardDispatcher 的 setter 方法"""

    def test_set_notification_sender(self):
        """测试设置通知发送器"""
        dispatcher = CardDispatcher()
        mock_sender = MagicMock()

        dispatcher.set_notification_sender(mock_sender)
        assert dispatcher._notification_sender == mock_sender

    def test_set_platform(self):
        """测试设置平台"""
        dispatcher = CardDispatcher()
        mock_platform = MagicMock()

        dispatcher.set_platform(mock_platform)
        assert dispatcher.platform == mock_platform

    def test_set_feishu_api(self):
        """测试设置飞书 API"""
        dispatcher = CardDispatcher()
        mock_feishu = MagicMock()

        dispatcher.set_feishu_api(mock_feishu)
        assert dispatcher.feishu == mock_feishu


class TestGlobalCardDispatcher:
    """测试全局 CardDispatcher 实例"""

    def test_get_card_dispatcher(self):
        """测试获取全局实例"""
        from src.card_dispatcher import get_card_dispatcher, set_card_dispatcher

        # 初始应该为 None
        dispatcher = get_card_dispatcher()
        assert dispatcher is None

    def test_set_card_dispatcher(self):
        """测试设置全局实例"""
        from src.card_dispatcher import get_card_dispatcher, set_card_dispatcher

        mock_dispatcher = MagicMock()
        set_card_dispatcher(mock_dispatcher)

        dispatcher = get_card_dispatcher()
        assert dispatcher == mock_dispatcher