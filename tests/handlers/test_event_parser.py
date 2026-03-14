"""
测试事件解析器
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestEventParser:
    """测试事件解析器"""

    @pytest.fixture
    def mock_platform(self):
        """创建模拟的 IM 平台"""
        platform = Mock()
        platform.parse_event = Mock(return_value=None)
        return platform

    @pytest.fixture
    def mock_attachment_handler(self):
        """创建模拟的附件处理器"""
        handler = Mock()
        handler.handle_image_message = AsyncMock(return_value="Read image command")
        handler.handle_voice_message = AsyncMock(return_value="Listen audio command")
        handler.handle_image_attachment = AsyncMock(return_value="Read image command")
        handler.handle_file_attachment = AsyncMock(return_value="Read file command")
        handler.handle_voice_attachment = AsyncMock(return_value="Listen audio command")
        return handler

    @pytest.fixture
    def event_parser(self, mock_platform, mock_attachment_handler):
        """创建事件解析器实例"""
        from src.handlers.event_parser import EventParser
        return EventParser(
            platform=mock_platform,
            attachment_handler=mock_attachment_handler
        )

    @pytest.mark.asyncio
    async def test_handle_event_with_platform(self, event_parser, mock_platform):
        """测试使用平台处理事件"""
        mock_message = Mock()
        mock_message.message_type = "text"
        mock_message.user_id = "test_user"
        mock_message.content = "test message"
        mock_message.message_id = "msg_123"
        mock_platform.parse_event.return_value = mock_message

        with patch.object(event_parser, '_handle_normalized_message', new_callable=AsyncMock) as mock_handle:
            await event_parser.handle_event({"type": "test_event"})

        mock_platform.parse_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_event_platform_returns_none(self, event_parser, mock_platform):
        """测试平台返回 None"""
        mock_platform.parse_event.return_value = None

        with patch.object(event_parser, '_handle_normalized_message', new_callable=AsyncMock) as mock_handle:
            await event_parser.handle_event({"type": "test_event"})

        mock_handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_event_platform_raises_exception(self, event_parser, mock_platform):
        """测试平台解析事件抛出异常"""
        mock_platform.parse_event.side_effect = Exception("Parse error")

        await event_parser.handle_event({"type": "test_event"})
        # 应该捕获异常，不抛出

    @pytest.mark.asyncio
    async def test_handle_legacy_event_message(self, event_parser, mock_attachment_handler):
        """测试处理飞书消息事件"""
        event_parser.platform = None  # 使用传统模式

        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "text",
                    "content": '{"text": "Hello"}'
                }
            }
        }

        with patch.object(event_parser, '_handle_message_receive', new_callable=AsyncMock) as mock_handle:
            await event_parser._handle_legacy_event(event_data)
            mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_legacy_event_unknown_type(self, event_parser):
        """测试处理未知事件类型"""
        event_parser.platform = None

        with patch('src.handlers.event_parser.logger') as mock_logger:
            await event_parser._handle_legacy_event({"type": "unknown_event"})

        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handle_message_receive_text(self, event_parser):
        """测试处理文本消息"""
        event_parser.platform = None

        event_data = {
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "text",
                    "content": '{"text": "Hello"}'
                }
            }
        }

        with patch('src.handlers.command_executor.command_executor') as mock_executor:
            mock_executor.process_command = AsyncMock()

            # 替换模块中的 command_executor
            with patch.dict('sys.modules', {'src.handlers.command_executor': mock_executor}):
                await event_parser._handle_message_receive(event_data)

    @pytest.mark.asyncio
    async def test_handle_message_receive_image(self, event_parser, mock_attachment_handler):
        """测试处理图片消息"""
        event_parser.platform = None

        event_data = {
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "image",
                    "content": '{"image_key": "img_123"}'
                }
            }
        }

        await event_parser._handle_message_receive(event_data)
        mock_attachment_handler.handle_image_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_receive_audio(self, event_parser, mock_attachment_handler):
        """测试处理语音消息"""
        event_parser.platform = None

        event_data = {
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "audio",
                    "content": '{"file_key": "audio_123"}'
                }
            }
        }

        await event_parser._handle_message_receive(event_data)
        mock_attachment_handler.handle_voice_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_message_receive_incomplete_data(self, event_parser):
        """测试消息数据不完整"""
        event_parser.platform = None

        event_data = {
            "event": {
                "sender": {},
                "message": {}
            }
        }

        with patch('src.handlers.event_parser.logger') as mock_logger:
            await event_parser._handle_message_receive(event_data)

        mock_logger.warning.assert_called()

    def test_set_attachment_handler(self, event_parser):
        """测试设置附件处理器"""
        new_handler = Mock()
        event_parser.set_attachment_handler(new_handler)
        assert event_parser._attachment_handler == new_handler

    def test_set_execute_command_callback(self, event_parser):
        """测试设置执行命令回调"""
        callback = AsyncMock()
        event_parser.set_execute_command_callback(callback)
        assert event_parser._on_execute_command == callback


class TestHandleNormalizedMessage:
    """测试 _handle_normalized_message 方法"""

    @pytest.fixture
    def mock_platform(self):
        """创建模拟的 IM 平台"""
        platform = Mock()
        platform.parse_event = Mock(return_value=None)
        return platform

    @pytest.fixture
    def mock_attachment_handler(self):
        """创建模拟的附件处理器"""
        handler = Mock()
        handler.handle_image_attachment = AsyncMock(return_value="Read image command")
        handler.handle_file_attachment = AsyncMock(return_value="Read file command")
        handler.handle_voice_attachment = AsyncMock(return_value="Listen audio command")
        return handler

    @pytest.fixture
    def event_parser(self, mock_platform, mock_attachment_handler):
        """创建事件解析器实例"""
        from src.handlers.event_parser import EventParser
        return EventParser(
            platform=mock_platform,
            attachment_handler=mock_attachment_handler
        )

    @pytest.mark.asyncio
    async def test_handle_normalized_text_message(self, event_parser):
        """测试处理标准化文本消息"""
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        normalized_message = NormalizedMessage(
            message_id="msg_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.TEXT,
            content="Hello world",
            raw_data={}
        )

        with patch('src.handlers.command_executor.command_executor') as mock_executor:
            mock_executor.process_command = AsyncMock()

            await event_parser._handle_normalized_message(normalized_message)

            mock_executor.process_command.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_normalized_image_message(self, event_parser, mock_attachment_handler):
        """测试处理标准化图片消息"""
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        normalized_message = NormalizedMessage(
            message_id="msg_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.IMAGE,
            content="",
            raw_data={},
            attachments=[{"file_key": "img_123"}]
        )

        callback = AsyncMock()
        event_parser.set_execute_command_callback(callback)

        await event_parser._handle_normalized_message(normalized_message)

        mock_attachment_handler.handle_image_attachment.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_normalized_file_message(self, event_parser, mock_attachment_handler):
        """测试处理标准化文件消息"""
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        normalized_message = NormalizedMessage(
            message_id="msg_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.FILE,
            content="",
            raw_data={},
            attachments=[{"file_key": "file_123"}]
        )

        callback = AsyncMock()
        event_parser.set_execute_command_callback(callback)

        await event_parser._handle_normalized_message(normalized_message)

        mock_attachment_handler.handle_file_attachment.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_normalized_voice_message(self, event_parser, mock_attachment_handler):
        """测试处理标准化语音消息"""
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        normalized_message = NormalizedMessage(
            message_id="msg_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.VOICE,
            content="",
            raw_data={},
            attachments=[{"file_key": "audio_123"}]
        )

        callback = AsyncMock()
        event_parser.set_execute_command_callback(callback)

        await event_parser._handle_normalized_message(normalized_message)

        mock_attachment_handler.handle_voice_attachment.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_normalized_message_empty_content(self, event_parser):
        """测试处理空内容的文本消息"""
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        normalized_message = NormalizedMessage(
            message_id="msg_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.TEXT,
            content="",
            raw_data={}
        )

        # 应该直接返回，不处理
        await event_parser._handle_normalized_message(normalized_message)

    @pytest.mark.asyncio
    async def test_handle_normalized_message_exception(self, event_parser):
        """测试处理标准化消息异常"""
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        normalized_message = NormalizedMessage(
            message_id="msg_123",
            user_id="user_123",
            chat_id="chat_123",
            message_type=MessageType.TEXT,
            content="Hello",
            raw_data={}
        )

        with patch('src.handlers.command_executor.command_executor') as mock_executor:
            mock_executor.process_command = AsyncMock(side_effect=Exception("Test error"))

            # 应该捕获异常，不抛出
            await event_parser._handle_normalized_message(normalized_message)


class TestDispatchCommand:
    """测试 _dispatch_command 方法"""

    @pytest.fixture
    def event_parser(self):
        """创建事件解析器实例"""
        from src.handlers.event_parser import EventParser
        return EventParser()

    @pytest.mark.asyncio
    async def test_dispatch_command(self, event_parser):
        """测试分发命令"""
        with patch('src.handlers.command_executor.command_executor') as mock_executor:
            mock_executor.process_command = AsyncMock()

            await event_parser._dispatch_command("user_123", "test command", "msg_123")

            mock_executor.process_command.assert_called_once_with(
                "user_123", "test command", "msg_123"
            )
