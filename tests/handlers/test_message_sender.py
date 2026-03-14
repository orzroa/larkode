"""
测试消息发送器
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestMessageSender:
    """测试消息发送器"""

    @pytest.fixture
    def mock_platform(self):
        """创建模拟的 IM 平台"""
        platform = Mock()
        platform.send_card = AsyncMock(return_value="feishu_msg_123")
        platform.send_message = AsyncMock(return_value="feishu_msg_456")
        return platform

    @pytest.fixture
    def mock_feishu_api(self):
        """创建模拟的飞书 API"""
        feishu = Mock()
        feishu.send_message = AsyncMock(return_value="feishu_msg_789")
        return feishu

    @pytest.fixture
    def mock_notification_sender(self):
        """创建模拟的通知发送器"""
        sender = Mock()
        sender.send_card = AsyncMock(return_value=True)
        sender.send_message = AsyncMock(return_value=True)
        sender.last_message_id = "notif_msg_123"
        return sender

    @pytest.fixture
    def mock_card_dispatcher(self):
        """创建模拟的卡片分发器"""
        dispatcher = Mock()
        dispatcher.send_card = AsyncMock(return_value=True)
        return dispatcher

    @pytest.fixture
    def message_sender(self, mock_notification_sender, mock_platform, mock_feishu_api, mock_card_dispatcher):
        """创建消息发送器实例"""
        from src.handlers.message_sender import MessageSender
        return MessageSender(
            notification_sender=mock_notification_sender,
            platform=mock_platform,
            feishu_api=mock_feishu_api,
            card_dispatcher=mock_card_dispatcher
        )

    @pytest.mark.asyncio
    async def test_send_message_via_notification_sender(self, message_sender, mock_notification_sender):
        """测试通过通知发送器发送消息"""
        with patch('src.storage.db') as mock_db:
            result = await message_sender.send(
                user_id="test_user",
                message="Hello World"
            )

        assert result is True
        mock_notification_sender.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_card_via_notification_sender(self, message_sender, mock_notification_sender):
        """测试通过通知发送器发送卡片"""
        from src.interfaces.im_platform import NormalizedCard
        mock_card = Mock(spec=NormalizedCard)
        mock_card.get_pure_content.return_value = '{"content": "test"}'
        mock_card.card_id = 123

        with patch('src.storage.db') as mock_db:
            result = await message_sender.send(
                user_id="test_user",
                card=mock_card
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_message_fallback_to_platform(self, message_sender, mock_platform):
        """测试回退到平台发送"""
        # 不设置 notification_sender 的场景
        message_sender._notification_sender = None

        with patch('src.storage.db') as mock_db:
            result = await message_sender.send(
                user_id="test_user",
                message="Fallback message"
            )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_card_dict_fallback_to_feishu(self, message_sender, mock_feishu_api):
        """测试发送 dict 类型的卡片时回退到飞书 API"""
        message_sender._notification_sender = None

        with patch('src.storage.db') as mock_db:
            result = await message_sender.send(
                user_id="test_user",
                card={"key": "value"}
            )

        mock_feishu_api.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_card_normalized_fallback_to_platform(self, message_sender, mock_platform):
        """测试发送 NormalizedCard 类型的卡片时回退到平台"""
        message_sender._notification_sender = None

        from src.interfaces.im_platform import NormalizedCard
        mock_card = Mock(spec=NormalizedCard)
        mock_card.get_pure_content.return_value = '{"content": "test"}'
        mock_card.card_id = 123

        with patch('src.storage.db') as mock_db:
            result = await message_sender.send(
                user_id="test_user",
                card=mock_card
            )

        mock_platform.send_card.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_stores_to_database(self, message_sender, mock_notification_sender):
        """测试发送消息时记录到数据库"""
        with patch('src.storage.db') as mock_db:
            await message_sender.send(
                user_id="test_user",
                message="Test message"
            )

        mock_db.save_message.assert_called_once()

    def test_set_notification_sender(self, message_sender):
        """测试设置通知发送器"""
        new_sender = Mock()
        message_sender.set_notification_sender(new_sender)
        assert message_sender._notification_sender == new_sender

    def test_set_card_builder(self, message_sender):
        """测试设置卡片构建器"""
        new_builder = Mock()
        message_sender.set_card_builder(new_builder)
        assert message_sender.card_builder == new_builder

    def test_get_message_id_from_notification_sender(self, message_sender, mock_notification_sender):
        """测试从通知发送器获取消息 ID"""
        message_id = message_sender._get_message_id_from_notification_sender()
        assert message_id == "notif_msg_123"

    def test_get_message_id_no_sender(self, message_sender):
        """测试没有通知发送器时返回空"""
        message_sender._notification_sender = None
        message_id = message_sender._get_message_id_from_notification_sender()
        assert message_id == ""

    def test_get_message_id_sender_without_last_message_id(self, message_sender):
        """测试通知发送器没有 last_message_id 属性时返回空"""
        sender = Mock()
        del sender.last_message_id
        message_sender._notification_sender = sender
        message_id = message_sender._get_message_id_from_notification_sender()
        assert message_id == ""

    @pytest.mark.asyncio
    async def test_send_error_with_card_builder(self, message_sender):
        """测试使用卡片构建器发送错误"""
        mock_card = Mock()
        message_sender.card_builder = Mock()
        message_sender.card_builder.create_error_card = Mock(return_value=mock_card)
        message_sender.send = AsyncMock(return_value=True)

        await message_sender.send_error("test_user", "Error message")

        message_sender.card_builder.create_error_card.assert_called_once_with("Error message")

    @pytest.mark.asyncio
    async def test_send_error_with_card_dispatcher(self, message_sender, mock_card_dispatcher):
        """测试使用卡片分发器发送错误"""
        message_sender.card_builder = None

        with patch('src.card_builder.UnifiedCardBuilder') as mock_builder_class:
            mock_builder_class.build_error_card = Mock(return_value="error content")

            await message_sender.send_error("test_user", "Error message")

        mock_card_dispatcher.send_card.assert_called_once()
