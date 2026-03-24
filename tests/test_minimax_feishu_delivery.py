"""
MiniMax Feishu 投递测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestMiniMaxFeishuDelivery:
    """MiniMax 结果发回飞书测试"""

    @pytest.fixture
    def mock_feishu_api(self):
        api = AsyncMock()
        api.upload_image = AsyncMock(return_value="feishu-img-key")
        api.upload_audio = AsyncMock(return_value="feishu-audio-key")
        api.upload_video = AsyncMock(return_value="feishu-video-key")
        api.upload_file = AsyncMock(return_value="feishu-file-key")
        api.send_image_message = AsyncMock(return_value=True)
        api.send_audio_message = AsyncMock(return_value=True)
        api.send_video_message = AsyncMock(return_value=True)
        api.send_file_message = AsyncMock(return_value=True)
        api.send_message = AsyncMock()
        return api

    @pytest.fixture
    def mock_card_dispatcher(self):
        return AsyncMock()

    @pytest.fixture
    def delivery(self, mock_feishu_api, mock_card_dispatcher):
        from src.minimax.feishu_delivery import MiniMaxFeishuDelivery
        return MiniMaxFeishuDelivery(
            feishu_api=mock_feishu_api,
            card_dispatcher=mock_card_dispatcher,
        )

    @pytest.fixture
    def delivery_no_dispatcher(self, mock_feishu_api):
        """无 card_dispatcher 的 delivery"""
        from src.minimax.feishu_delivery import MiniMaxFeishuDelivery
        return MiniMaxFeishuDelivery(
            feishu_api=mock_feishu_api,
            card_dispatcher=None,
        )

    @pytest.mark.asyncio
    async def test_send_text_with_card_dispatcher(self, delivery, mock_card_dispatcher):
        """测试发送文字（使用卡片分发器）"""
        await delivery.send_text("user-123", "测试文本")
        mock_card_dispatcher.send_card.assert_called_once()
        call_kwargs = mock_card_dispatcher.send_card.call_args[1]
        assert call_kwargs["user_id"] == "user-123"
        assert call_kwargs["card_type"] == "minimax"

    @pytest.mark.asyncio
    async def test_send_text_without_card_dispatcher(self, delivery_no_dispatcher, mock_feishu_api):
        """测试发送文字（无卡片分发器）"""
        await delivery_no_dispatcher.send_text("user-123", "测试文本")
        mock_feishu_api.send_message.assert_called_once()
        call_args = mock_feishu_api.send_message.call_args
        assert call_args[0][0] == "user-123"

    @pytest.mark.asyncio
    async def test_send_image_success(self, delivery, mock_feishu_api):
        """测试发送图片成功"""
        image_path = MagicMock(spec=Path)
        image_path.name = "test.png"
        image_path.exists.return_value = True

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_image("user-123", image_path)

        mock_feishu_api.upload_image.assert_called_once_with(image_path)
        mock_feishu_api.send_image_message.assert_called_once_with("user-123", "feishu-img-key")

    @pytest.mark.asyncio
    async def test_send_audio_success(self, delivery, mock_feishu_api):
        """测试发送音频成功"""
        audio_path = MagicMock(spec=Path)
        audio_path.name = "test.mp3"
        audio_path.exists.return_value = True

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_audio("user-123", audio_path)

        mock_feishu_api.upload_audio.assert_called_once_with(audio_path)
        mock_feishu_api.send_audio_message.assert_called_once_with("user-123", "feishu-audio-key")

    @pytest.mark.asyncio
    async def test_send_video_success(self, delivery, mock_feishu_api):
        """测试发送视频成功"""
        video_path = MagicMock(spec=Path)
        video_path.name = "test.mp4"
        video_path.exists.return_value = True

        thumbnail_path = MagicMock(spec=Path)
        thumbnail_path.exists.return_value = True

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_video("user-123", video_path, thumbnail_path)

        mock_feishu_api.upload_video.assert_called_once_with(video_path)
        mock_feishu_api.upload_image.assert_called_once_with(thumbnail_path)
        mock_feishu_api.send_video_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_file_success(self, delivery, mock_feishu_api):
        """测试发送文件成功"""
        file_path = MagicMock(spec=Path)
        file_path.name = "test.mp3"
        file_path.exists.return_value = True

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_file("user-123", file_path)

        mock_feishu_api.upload_file.assert_called_once_with(file_path)
        mock_feishu_api.send_file_message.assert_called_once_with("user-123", "feishu-file-key")

    @pytest.mark.asyncio
    async def test_send_image_upload_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试图片上传失败"""
        mock_feishu_api.upload_image = AsyncMock(return_value=None)

        image_path = MagicMock(spec=Path)
        image_path.name = "test.png"

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_image("user-123", image_path)

        # 降级到错误消息
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_error(self, delivery, mock_card_dispatcher):
        """测试发送错误消息"""
        await delivery.send_error("user-123", "Something went wrong")
        mock_card_dispatcher.send_card.assert_called_once()
        call_kwargs = mock_card_dispatcher.send_card.call_args[1]
        assert call_kwargs["template_color"] == "red"
        assert call_kwargs["card_type"] == "error"

    @pytest.mark.asyncio
    async def test_send_progress(self, delivery, mock_card_dispatcher):
        """测试发送进度消息"""
        await delivery.send_progress("user-123", "正在处理中...")
        mock_card_dispatcher.send_card.assert_called_once()
        call_kwargs = mock_card_dispatcher.send_card.call_args[1]
        assert call_kwargs["title"] == "MiniMax 处理中"

    # ==================== 更多测试 ====================

    @pytest.mark.asyncio
    async def test_send_video_without_thumbnail(self, delivery, mock_feishu_api):
        """测试发送视频（无缩略图）"""
        video_path = MagicMock(spec=Path)
        video_path.name = "test.mp4"

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_video("user-123", video_path, None)

        mock_feishu_api.upload_video.assert_called_once_with(video_path)
        mock_feishu_api.send_video_message.assert_called_once_with("user-123", "feishu-video-key", None)

    @pytest.mark.asyncio
    async def test_send_video_thumbnail_not_exists(self, delivery, mock_feishu_api):
        """测试发送视频（缩略图不存在）"""
        video_path = MagicMock(spec=Path)
        video_path.name = "test.mp4"

        thumbnail_path = MagicMock(spec=Path)
        thumbnail_path.exists.return_value = False

        with patch.object(Path, "exists", return_value=False):
            await delivery.send_video("user-123", video_path, thumbnail_path)

        mock_feishu_api.upload_video.assert_called_once()
        # 缩略图不存在，不应该上传
        mock_feishu_api.upload_image.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_video_upload_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试视频上传失败"""
        mock_feishu_api.upload_video = AsyncMock(return_value=None)

        video_path = MagicMock(spec=Path)
        video_path.name = "test.mp4"

        await delivery.send_video("user-123", video_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_video_send_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试视频发送失败"""
        mock_feishu_api.send_video_message = AsyncMock(return_value=False)

        video_path = MagicMock(spec=Path)
        video_path.name = "test.mp4"

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_video("user-123", video_path)

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_video_exception(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试视频发送异常"""
        mock_feishu_api.upload_video = AsyncMock(side_effect=Exception("Upload error"))

        video_path = MagicMock(spec=Path)
        video_path.name = "test.mp4"

        await delivery.send_video("user-123", video_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_audio_upload_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试音频上传失败"""
        mock_feishu_api.upload_audio = AsyncMock(return_value=None)

        audio_path = MagicMock(spec=Path)
        audio_path.name = "test.mp3"

        await delivery.send_audio("user-123", audio_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_audio_send_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试音频发送失败"""
        mock_feishu_api.send_audio_message = AsyncMock(return_value=False)

        audio_path = MagicMock(spec=Path)
        audio_path.name = "test.mp3"

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_audio("user-123", audio_path)

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_audio_exception(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试音频发送异常"""
        mock_feishu_api.upload_audio = AsyncMock(side_effect=Exception("Upload error"))

        audio_path = MagicMock(spec=Path)
        audio_path.name = "test.mp3"

        await delivery.send_audio("user-123", audio_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_file_upload_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试文件上传失败"""
        mock_feishu_api.upload_file = AsyncMock(return_value=None)

        file_path = MagicMock(spec=Path)
        file_path.name = "test.mp3"

        await delivery.send_file("user-123", file_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_file_send_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试文件发送失败"""
        mock_feishu_api.send_file_message = AsyncMock(return_value=False)

        file_path = MagicMock(spec=Path)
        file_path.name = "test.mp3"

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_file("user-123", file_path)

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_file_exception(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试文件发送异常"""
        mock_feishu_api.upload_file = AsyncMock(side_effect=Exception("Upload error"))

        file_path = MagicMock(spec=Path)
        file_path.name = "test.mp3"

        await delivery.send_file("user-123", file_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_image_send_failure(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试图片发送失败"""
        mock_feishu_api.send_image_message = AsyncMock(return_value=False)

        image_path = MagicMock(spec=Path)
        image_path.name = "test.png"

        with patch.object(Path, "exists", return_value=True):
            await delivery.send_image("user-123", image_path)

        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_image_exception(self, delivery, mock_feishu_api, mock_card_dispatcher):
        """测试图片发送异常"""
        mock_feishu_api.upload_image = AsyncMock(side_effect=Exception("Upload error"))

        image_path = MagicMock(spec=Path)
        image_path.name = "test.png"

        await delivery.send_image("user-123", image_path)
        mock_card_dispatcher.send_card.assert_called()

    @pytest.mark.asyncio
    async def test_send_error_without_dispatcher(self, delivery_no_dispatcher, mock_feishu_api):
        """测试发送错误消息（无 dispatcher）"""
        await delivery_no_dispatcher.send_error("user-123", "Something went wrong")
        mock_feishu_api.send_message.assert_called()

    @pytest.mark.asyncio
    async def test_send_progress_without_dispatcher(self, delivery_no_dispatcher, mock_feishu_api):
        """测试发送进度消息（无 dispatcher）"""
        await delivery_no_dispatcher.send_progress("user-123", "Processing...")
        mock_feishu_api.send_message.assert_called()
