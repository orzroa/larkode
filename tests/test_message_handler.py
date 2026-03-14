"""
MessageHandler 单元测试
"""
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from pathlib import Path

from src.message_handler import MessageHandler


class TestMessageHandlerInit:
    """测试 MessageHandler 初始化"""

    def test_init_with_platform(self):
        """测试使用传入的平台初始化"""
        mock_platform = MagicMock()
        mock_card_builder = MagicMock()

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                handler = MessageHandler(
                    platform=mock_platform,
                    card_builder=mock_card_builder
                )

                assert handler.platform is mock_platform
                assert handler.card_builder is mock_card_builder

    def test_init_without_platform(self):
        """测试不传入平台时的初始化"""
        with patch('src.factories.platform_factory.IMPlatformFactory.is_platform_registered', return_value=False):
            with patch('src.im_platforms.register_feishu_platform'):
                with patch('src.factories.platform_factory.IMPlatformFactory.create_platform') as mock_create:
                    mock_platform = MagicMock()
                    mock_create.return_value = mock_platform

                    with patch('src.factories.platform_factory.IMPlatformFactory.create_card_builder') as mock_builder:
                        mock_builder.return_value = MagicMock()

                        with patch('src.config.settings.get_settings') as mock_settings:
                            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
                            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
                            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
                            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"
                            mock_settings.return_value.IM_PLATFORM = "feishu"

                            with patch('src.feishu.FeishuAPI'):
                                handler = MessageHandler()

                                assert handler.platform is mock_platform


class TestSetCurrentPlatform:
    """测试 set_current_platform 方法"""

    def test_set_current_platform(self):
        """测试设置当前平台"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._command_executor = MagicMock()

                    handler.set_current_platform("slack")

                    assert handler._current_platform == "slack"
                    handler._command_executor.set_current_platform.assert_called_once_with("slack")

    def test_set_current_platform_feishu(self):
        """测试设置为飞书平台"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._command_executor = MagicMock()

                    handler.set_current_platform("feishu")

                    assert handler._current_platform == "feishu"


class TestGetCurrentPlatform:
    """测试 get_current_platform 方法"""

    def test_get_current_platform_none(self):
        """测试获取未设置的平台"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._current_platform = None
                    handler._command_executor = MagicMock()

                    result = handler.get_current_platform()

                    assert result is None

    def test_get_current_platform_set(self):
        """测试获取已设置的平台"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._current_platform = "slack"
                    handler._command_executor = MagicMock()

                    result = handler.get_current_platform()

                    assert result == "slack"


class TestSetNotificationSender:
    """测试 set_notification_sender 方法"""

    def test_set_notification_sender(self):
        """测试设置通知发送器"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._message_sender = MagicMock()
                    handler._platform_commands = MagicMock()
                    handler._attachment_handler = MagicMock()
                    handler._command_executor = MagicMock()

                    mock_sender = MagicMock()
                    handler.set_notification_sender(mock_sender)

                    assert handler._notification_sender is mock_sender
                    handler._message_sender.set_notification_sender.assert_called_once_with(mock_sender)


class TestHandleEvent:
    """测试 handle_event 方法"""

    @pytest.mark.asyncio
    async def test_handle_event(self):
        """测试处理事件"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._event_parser = MagicMock()
                    handler._event_parser.handle_event = AsyncMock()
                    handler._command_executor = MagicMock()

                    event_data = {"type": "message", "content": "test"}
                    await handler.handle_event(event_data)

                    handler._event_parser.handle_event.assert_called_once_with(event_data)

    @pytest.mark.asyncio
    async def test_handle_event_empty(self):
        """测试处理空事件"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._event_parser = MagicMock()
                    handler._event_parser.handle_event = AsyncMock()
                    handler._command_executor = MagicMock()

                    await handler.handle_event({})

                    handler._event_parser.handle_event.assert_called_once_with({})

    @pytest.mark.asyncio
    async def test_handle_event_with_complex_data(self):
        """测试处理复杂事件数据"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._event_parser = MagicMock()
                    handler._event_parser.handle_event = AsyncMock()
                    handler._command_executor = MagicMock()

                    complex_event = {
                        "header": {"event_id": "123", "event_type": "message"},
                        "event": {
                            "sender": {"sender_id": {"open_id": "ou_xxx"}},
                            "message": {"content": "test message"}
                        }
                    }
                    await handler.handle_event(complex_event)

                    handler._event_parser.handle_event.assert_called_once_with(complex_event)


class TestSendViaSender:
    """测试 _send_via_sender 方法"""

    @pytest.mark.asyncio
    async def test_send_via_sender_with_card(self):
        """测试通过发送器发送卡片"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._message_sender = MagicMock()
                    handler._message_sender.send = AsyncMock(return_value=True)
                    handler._command_executor = MagicMock()

                    card = {"type": "interactive", "content": "test"}
                    result = await handler._send_via_sender("user123", card=card)

                    assert result is True
                    handler._message_sender.send.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_via_sender_with_message(self):
        """测试通过发送器发送文本消息"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._message_sender = MagicMock()
                    handler._message_sender.send = AsyncMock(return_value=True)
                    handler._command_executor = MagicMock()

                    result = await handler._send_via_sender("user123", message="Hello")

                    assert result is True

    @pytest.mark.asyncio
    async def test_send_via_sender_both_card_and_message(self):
        """测试同时发送卡片和消息"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._message_sender = MagicMock()
                    handler._message_sender.send = AsyncMock(return_value=True)
                    handler._command_executor = MagicMock()

                    result = await handler._send_via_sender(
                        "user123",
                        card={"type": "card"},
                        message="text"
                    )

                    assert result is True


class TestSendError:
    """测试 _send_error 方法"""

    @pytest.mark.asyncio
    async def test_send_error(self):
        """测试发送错误消息"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._command_executor = MagicMock()
                    handler._command_executor.send_error = AsyncMock()

                    await handler._send_error("user123", "Error occurred")

                    handler._command_executor.send_error.assert_called_once_with(
                        "user123", "Error occurred"
                    )


class TestGlobalInstance:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from src.message_handler import message_handler

        assert message_handler is not None
        assert isinstance(message_handler, MessageHandler)


class TestEdgeCases:
    """测试边界情况"""

    def test_init_with_multi_platform_manager(self):
        """测试使用多平台管理器初始化"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    mock_mpm = MagicMock()
                    mock_ns = MagicMock()

                    handler = MessageHandler(
                        platform=MagicMock(),
                        card_builder=MagicMock(),
                        multi_platform_manager=mock_mpm,
                        notification_sender=mock_ns
                    )

                    assert handler._multi_platform_manager is mock_mpm
                    assert handler._notification_sender is mock_ns

    @pytest.mark.asyncio
    async def test_handle_event_with_none_data(self):
        """测试处理 None 数据"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.message_handler.MessageHandler._init_sub_handlers'):
                    handler = MessageHandler(platform=MagicMock(), card_builder=MagicMock())
                    handler._event_parser = MagicMock()
                    handler._event_parser.handle_event = AsyncMock()
                    handler._command_executor = MagicMock()

                    await handler.handle_event(None)

                    handler._event_parser.handle_event.assert_called_once_with(None)

    def test_init_sub_handlers(self):
        """测试子处理器初始化"""
        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_APP_SECRET = "test_secret"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.IM_PLATFORM = "feishu"

            with patch('src.feishu.FeishuAPI'):
                with patch('src.handlers.message_sender.MessageSender'):
                    with patch('src.handlers.event_parser.EventParser'):
                        with patch('src.handlers.command_executor.CommandExecutor'):
                            with patch('src.handlers.platform_commands.PlatformCommands'):
                                with patch('src.handlers.attachment_handler.AttachmentHandler'):
                                    with patch('src.card_dispatcher.CardDispatcher'):
                                        handler = MessageHandler(
                                            platform=MagicMock(),
                                            card_builder=MagicMock()
                                        )

                                        assert handler._message_sender is not None
                                        assert handler._platform_commands is not None
                                        assert handler._attachment_handler is not None
                                        assert handler._command_executor is not None
                                        assert handler._event_parser is not None