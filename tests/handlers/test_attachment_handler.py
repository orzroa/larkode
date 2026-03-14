"""
测试附件处理器
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestAttachmentHandler:
    """测试附件处理器"""

    @pytest.fixture
    def mock_platform(self):
        """创建模拟的 IM 平台"""
        platform = Mock()
        platform.download_file = AsyncMock(return_value=Path("/tmp/test_image.png"))
        return platform

    @pytest.fixture
    def mock_card_dispatcher(self):
        """创建模拟的卡片分发器"""
        dispatcher = Mock()
        dispatcher.send_card = AsyncMock(return_value=True)
        return dispatcher

    @pytest.fixture
    def attachment_handler(self, mock_platform, mock_card_dispatcher):
        """创建附件处理器实例"""
        from src.handlers.attachment_handler import AttachmentHandler
        return AttachmentHandler(
            platform=mock_platform,
            card_dispatcher=mock_card_dispatcher
        )

    @pytest.mark.asyncio
    async def test_handle_image_message_success(self, attachment_handler, mock_platform, mock_card_dispatcher):
        """测试成功处理图片消息"""
        user_id = "test_user"
        content_data = {"image_key": "test_image_key"}
        message_id = "test_msg_id"

        with patch('src.handlers.attachment_handler.db') as mock_db:
            result = await attachment_handler.handle_image_message(user_id, content_data, message_id)

        # image_path 是 Path 对象，command 使用完整路径
        assert "Read the image at" in result
        mock_platform.download_file.assert_called_once_with(message_id, "test_image_key")

    @pytest.mark.asyncio
    async def test_handle_image_message_no_image_key(self, attachment_handler):
        """测试图片消息没有 image_key"""
        user_id = "test_user"
        content_data = {}
        message_id = "test_msg_id"

        result = await attachment_handler.handle_image_message(user_id, content_data, message_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_image_message_download_failed(self, attachment_handler, mock_platform):
        """测试图片下载失败"""
        mock_platform.download_file = AsyncMock(return_value=None)

        user_id = "test_user"
        content_data = {"image_key": "test_image_key"}
        message_id = "test_msg_id"

        with patch.object(attachment_handler, '_send_error', new_callable=AsyncMock):
            result = await attachment_handler.handle_image_message(user_id, content_data, message_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_file_attachment_success(self, attachment_handler, mock_platform):
        """测试成功处理文件附件"""
        user_id = "test_user"
        mock_platform.download_file = AsyncMock(return_value=Path("/tmp/test_file.txt"))

        normalized_message = Mock()
        normalized_message.message_id = "test_msg_id"
        normalized_message.attachments = [{"file_key": "test_file_key"}]

        with patch('src.handlers.attachment_handler.db') as mock_db:
            result = await attachment_handler.handle_file_attachment(user_id, normalized_message)

        assert "Read the file at" in result
        mock_platform.download_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_file_attachment_no_attachments(self, attachment_handler):
        """测试文件附件没有附件数据"""
        user_id = "test_user"
        normalized_message = Mock()
        normalized_message.message_id = "test_msg_id"
        normalized_message.attachments = []

        with patch.object(attachment_handler, '_send_error', new_callable=AsyncMock):
            result = await attachment_handler.handle_file_attachment(user_id, normalized_message)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_file_attachment_no_file_key(self, attachment_handler):
        """测试文件附件没有 file_key"""
        user_id = "test_user"
        normalized_message = Mock()
        normalized_message.message_id = "test_msg_id"
        normalized_message.attachments = [{}]

        with patch.object(attachment_handler, '_send_error', new_callable=AsyncMock):
            result = await attachment_handler.handle_file_attachment(user_id, normalized_message)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_voice_message_success(self, attachment_handler, mock_platform, mock_card_dispatcher):
        """测试成功处理语音消息"""
        user_id = "test_user"
        content_data = {"file_key": "test_voice_key"}
        message_id = "test_msg_id"

        with patch('src.handlers.attachment_handler.db') as mock_db:
            result = await attachment_handler.handle_voice_message(user_id, content_data, message_id)

        assert "Listen to the audio at" in result
        mock_platform.download_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_voice_message_no_file_key(self, attachment_handler):
        """测试语音消息没有 file_key"""
        user_id = "test_user"
        content_data = {}
        message_id = "test_msg_id"

        result = await attachment_handler.handle_voice_message(user_id, content_data, message_id)

        assert result is None

    @pytest.mark.asyncio
    async def test_handle_voice_attachment_success(self, attachment_handler, mock_platform):
        """测试成功处理语音附件"""
        user_id = "test_user"
        mock_platform.download_file = AsyncMock(return_value=Path("/tmp/test_voice.wav"))

        normalized_message = Mock()
        normalized_message.message_id = "test_msg_id"
        normalized_message.attachments = [{"file_key": "test_voice_key"}]

        with patch('src.handlers.attachment_handler.db') as mock_db:
            result = await attachment_handler.handle_voice_attachment(user_id, normalized_message)

        assert "Listen to the audio at" in result

    @pytest.mark.asyncio
    async def test_handle_image_attachment_success(self, attachment_handler, mock_platform):
        """测试成功处理图片附件"""
        user_id = "test_user"
        mock_platform.download_file = AsyncMock(return_value=Path("/tmp/test_image.png"))

        normalized_message = Mock()
        normalized_message.message_id = "test_msg_id"
        normalized_message.attachments = [{"image_key": "test_image_key"}]

        with patch('src.handlers.attachment_handler.db') as mock_db:
            result = await attachment_handler.handle_image_attachment(user_id, normalized_message)

        assert "Read the image at" in result

    @pytest.mark.asyncio
    async def test_handle_image_attachment_no_attachments(self, attachment_handler):
        """测试图片附件没有附件数据"""
        user_id = "test_user"
        normalized_message = Mock()
        normalized_message.message_id = "test_msg_id"
        normalized_message.attachments = []

        with patch.object(attachment_handler, '_send_error', new_callable=AsyncMock):
            result = await attachment_handler.handle_image_attachment(user_id, normalized_message)

        assert result is None

    def test_set_send_callback(self, attachment_handler):
        """测试设置发送回调函数"""
        callback = Mock()
        attachment_handler.set_send_callback(callback)
        assert attachment_handler._send_via_sender == callback
