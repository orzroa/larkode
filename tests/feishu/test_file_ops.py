"""
测试飞书文件操作模块

主要测试：
1. 音频格式检测函数 _detect_audio_extension
2. 图片/音频互斥分支逻辑
3. 文件上传、下载、发送功能
"""
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from io import BytesIO

import pytest

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestDetectAudioExtension:
    """测试音频格式检测函数"""

    def test_detect_amr_format(self):
        """测试 AMR 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # AMR 文件头: #!AMR
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"#AMR")
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".amr", f"Expected .amr, got {result}"

    def test_detect_mp3_id3_format(self):
        """测试 MP3 ID3 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # MP3 ID3 标签头
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"ID3")
            f.write(b"\x00" * 9)  # 填充到 12 字节
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".mp3", f"Expected .mp3, got {result}"

    def test_detect_mp3_mpeg_format(self):
        """测试 MP3 MPEG 同步字格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # MP3 MPEG 同步字 0xFFFB
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"\xff\xfb")
            f.write(b"\x00" * 10)
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".mp3", f"Expected .mp3, got {result}"

    def test_detect_wav_format(self):
        """测试 WAV 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # WAV 文件头: RIFF....WAVE
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"RIFF")
            f.write(b"\x00\x00\x00\x00")  # 文件大小
            f.write(b"WAVE")
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".wav", f"Expected .wav, got {result}"

    def test_detect_ogg_format(self):
        """测试 OGG 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # OGG 文件头: OggS
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"OggS")
            f.write(b"\x00" * 8)
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".ogg", f"Expected .ogg, got {result}"

    def test_detect_m4a_format(self):
        """测试 M4A/AAC 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # M4A 文件头: ....ftyp
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"\x00\x00\x00\x00")
            f.write(b"ftyp")
            f.write(b"\x00" * 4)
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".m4a", f"Expected .m4a, got {result}"

    def test_detect_flac_format(self):
        """测试 FLAC 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # FLAC 文件头: fLaC
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"fLaC")
            f.write(b"\x00" * 8)
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".flac", f"Expected .flac, got {result}"

    def test_detect_aac_format(self):
        """测试 AAC/ADTS 格式检测"""
        from src.feishu.file_ops import _detect_audio_extension

        # AAC 文件头: 0xFFF1
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"\xff\xf1")
            f.write(b"\x00" * 10)
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".aac", f"Expected .aac, got {result}"

    def test_unknown_format_defaults_to_amr(self):
        """测试未知格式默认返回 .amr"""
        from src.feishu.file_ops import _detect_audio_extension

        # 随机文件头
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00")
            f.flush()
            result = _detect_audio_extension(Path(f.name))
            assert result == ".amr", f"Expected .amr for unknown, got {result}"


class TestFileTypeDetectionBranches:
    """测试图片/音频互斥分支逻辑"""

    def test_image_file_not_detected_as_audio(self):
        """测试图片文件不会被识别为音频"""
        import imghdr

        # 创建一个简单的 PNG 文件头
        png_header = (
            b"\x89PNG\r\n\x1a\n"  # PNG 签名
            b"\x00\x00\x00\rIHDR"  # IHDR 块
            b"\x00\x00\x00\x01"  # 宽度
            b"\x00\x00\x00\x01"  # 高度
            b"\x08\x02"  # 位深度、颜色类型
        )

        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(png_header)
            f.flush()
            path = Path(f.name)

            # 验证 imghdr 能识别为 PNG
            detected = imghdr.what(str(path))
            assert detected == "png", f"imghdr should detect PNG, got {detected}"

    def test_audio_file_not_detected_as_image(self):
        """测试音频文件不会被识别为图片"""
        import imghdr

        # 创建一个 AMR 文件头
        with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False) as f:
            f.write(b"#AMR\n")
            f.write(b"\x00" * 100)
            f.flush()

            # imghdr 应该返回 None
            detected = imghdr.what(f.name)
            assert detected is None, f"imghdr should not detect audio as image, got {detected}"


class TestVoiceMessageHandling:
    """测试语音消息处理"""

    @pytest.mark.asyncio
    async def test_handle_voice_attachment_with_valid_file_key(self):
        """测试有效的语音附件处理"""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.handlers.attachment_handler import AttachmentHandler
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        # 创建 mock 对象
        mock_platform = MagicMock()
        mock_platform.download_file = AsyncMock(return_value=Path("/tmp/test_audio.amr"))

        handler = AttachmentHandler(platform=mock_platform)

        # 创建标准化消息
        normalized_message = NormalizedMessage(
            message_id="test_msg_id",
            user_id="test_user_id",
            chat_id="test_chat_id",
            message_type=MessageType.VOICE,
            content="",
            raw_data={},
            attachments=[{"file_key": "test_file_key"}]
        )

        # 调用处理方法
        with patch.object(handler, '_send_error', new_callable=AsyncMock):
            result = await handler.handle_voice_attachment("test_user_id", normalized_message)

        # 验证结果
        assert result == "Listen to the audio at /tmp/test_audio.amr"
        mock_platform.download_file.assert_called_once_with("test_msg_id", "test_file_key")

    @pytest.mark.asyncio
    async def test_handle_voice_attachment_missing_file_key(self):
        """测试缺少 file_key 的语音附件"""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.handlers.attachment_handler import AttachmentHandler
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        mock_platform = MagicMock()
        handler = AttachmentHandler(platform=mock_platform)

        # 创建缺少 file_key 的消息
        normalized_message = NormalizedMessage(
            message_id="test_msg_id",
            user_id="test_user_id",
            chat_id="test_chat_id",
            message_type=MessageType.VOICE,
            content="",
            raw_data={},
            attachments=[{}]  # 空 attachments
        )

        # 调用处理方法
        with patch.object(handler, '_send_error', new_callable=AsyncMock) as mock_error:
            result = await handler.handle_voice_attachment("test_user_id", normalized_message)

        # 验证返回 None 并发送错误
        assert result is None
        mock_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_voice_attachment_download_failure(self):
        """测试语音文件下载失败"""
        from unittest.mock import AsyncMock, MagicMock, patch

        from src.handlers.attachment_handler import AttachmentHandler
        from src.interfaces.im_platform import MessageType, NormalizedMessage

        mock_platform = MagicMock()
        mock_platform.download_file = AsyncMock(return_value=None)  # 模拟下载失败

        handler = AttachmentHandler(platform=mock_platform)

        normalized_message = NormalizedMessage(
            message_id="test_msg_id",
            user_id="test_user_id",
            chat_id="test_chat_id",
            message_type=MessageType.VOICE,
            content="",
            raw_data={},
            attachments=[{"file_key": "test_file_key"}]
        )

        with patch.object(handler, '_send_error', new_callable=AsyncMock) as mock_error:
            result = await handler.handle_voice_attachment("test_user_id", normalized_message)

        assert result is None
        mock_error.assert_called_once()


class TestGetSavePath:
    """测试文件保存路径生成函数"""

    def test_get_save_path_default_dir(self):
        """测试默认保存目录"""
        from src.feishu.file_ops import _get_save_path

        file_key = "test_file_key_123"
        result = _get_save_path(file_key)

        # 验证路径包含 file_key 和时间戳
        assert file_key in str(result)
        assert "uploads" in str(result)

    def test_get_save_path_custom_dir(self):
        """测试自定义保存目录"""
        from src.feishu.file_ops import _get_save_path

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir)
            file_key = "test_key"

            result = _get_save_path(file_key, custom_dir)

            assert custom_dir in result.parents
            assert file_key in str(result)

    def test_get_save_path_creates_dir(self):
        """测试自动创建目录"""
        from src.feishu.file_ops import _get_save_path

        with tempfile.TemporaryDirectory() as tmpdir:
            custom_dir = Path(tmpdir) / "subdir" / "nested"

            # 目录不存在时调用函数
            result = _get_save_path("test_key", custom_dir)

            # 验证目录被创建
            assert custom_dir.exists()


class TestDownloadFile:
    """测试文件下载功能"""

    @pytest.mark.asyncio
    async def test_download_file_success(self):
        """测试成功下载文件"""
        from src.feishu.file_ops import download_file

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                # 创建模拟响应
                mock_response = Mock()
                mock_response.success.return_value = True
                mock_response.code = 0
                mock_response.msg = "success"
                mock_response.get_log_id.return_value = "log_123"
                mock_response.file_name = "test_file.txt"

                # 创建模拟文件对象
                mock_file = BytesIO(b"test content")
                mock_response.file = mock_file

                # 设置客户端 mock
                mock_client = Mock()
                mock_client.im.v1.message_resource.get.return_value = mock_response
                mock_create_client.return_value = mock_client

                result = await download_file(
                    "test_secret",
                    "msg_123",
                    "file_key_123",
                    Path(tmpdir)
                )

                assert result is not None
                assert result.exists()

    @pytest.mark.asyncio
    async def test_download_file_failure(self):
        """测试下载文件失败"""
        from src.feishu.file_ops import download_file

        with patch('src.feishu.file_ops._create_client') as mock_create_client:
            # 创建失败响应
            mock_response = Mock()
            mock_response.success.return_value = False
            mock_response.code = 400
            mock_response.msg = "Bad request"
            mock_response.get_log_id.return_value = "log_123"

            mock_client = Mock()
            mock_client.im.v1.message_resource.get.return_value = mock_response
            mock_create_client.return_value = mock_client

            result = await download_file(
                "test_secret",
                "msg_123",
                "file_key_123"
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_download_file_exception(self):
        """测试下载文件异常"""
        from src.feishu.file_ops import download_file

        with patch('src.feishu.file_ops._create_client') as mock_create_client:
            mock_create_client.side_effect = Exception("Connection error")

            result = await download_file(
                "test_secret",
                "msg_123",
                "file_key_123"
            )

            assert result is None


class TestUploadImage:
    """测试图片上传功能"""

    @pytest.mark.asyncio
    async def test_upload_image_success(self):
        """测试成功上传图片"""
        from src.feishu.file_ops import upload_image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # 创建一个简单的 PNG 头
            f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                # 创建模拟响应
                mock_response = Mock()
                mock_response.success.return_value = True
                mock_response.data = Mock()
                mock_response.data.image_key = "img_key_123"

                mock_client = Mock()
                mock_client.im.v1.image.create.return_value = mock_response
                mock_create_client.return_value = mock_client

                result = await upload_image("test_secret", temp_path)

                assert result == "img_key_123"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_upload_image_failure(self):
        """测试上传图片失败"""
        from src.feishu.file_ops import upload_image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image content")
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                mock_response = Mock()
                mock_response.success.return_value = False
                mock_response.code = 400
                mock_response.msg = "Invalid image"

                mock_client = Mock()
                mock_client.im.v1.image.create.return_value = mock_response
                mock_create_client.return_value = mock_client

                result = await upload_image("test_secret", temp_path)

                assert result is None
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_upload_image_exception(self):
        """测试上传图片异常"""
        from src.feishu.file_ops import upload_image

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image content")
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                mock_create_client.side_effect = Exception("Network error")

                result = await upload_image("test_secret", temp_path)

                assert result is None
        finally:
            os.unlink(temp_path)


class TestUploadFile:
    """测试文件上传功能"""

    @pytest.mark.asyncio
    async def test_upload_file_success(self):
        """测试成功上传文件"""
        from src.feishu.file_ops import upload_file

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                mock_response = Mock()
                mock_response.success.return_value = True
                mock_response.data = Mock()
                mock_response.data.file_key = "file_key_123"

                mock_client = Mock()
                mock_client.im.v1.file.create.return_value = mock_response
                mock_create_client.return_value = mock_client

                result = await upload_file("test_secret", temp_path)

                assert result == "file_key_123"
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_upload_file_failure_raises_error(self):
        """测试上传文件失败抛出异常"""
        from src.feishu.file_ops import upload_file
        from src.feishu.exceptions import FeishuAPIUploadError

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                mock_response = Mock()
                mock_response.success.return_value = False
                mock_response.code = 400
                mock_response.msg = "Upload failed"

                mock_client = Mock()
                mock_client.im.v1.file.create.return_value = mock_response
                mock_create_client.return_value = mock_client

                with pytest.raises(FeishuAPIUploadError):
                    await upload_file("test_secret", temp_path)
        finally:
            os.unlink(temp_path)

    @pytest.mark.asyncio
    async def test_upload_file_exception_raises_error(self):
        """测试上传文件异常抛出异常"""
        from src.feishu.file_ops import upload_file
        from src.feishu.exceptions import FeishuAPIUploadError

        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            f.write(b"test content")
            f.flush()
            temp_path = Path(f.name)

        try:
            with patch('src.feishu.file_ops._create_client') as mock_create_client:
                mock_create_client.side_effect = Exception("Network error")

                with pytest.raises(FeishuAPIUploadError):
                    await upload_file("test_secret", temp_path)
        finally:
            os.unlink(temp_path)


class TestSendFileMessage:
    """测试发送文件消息功能"""

    @pytest.mark.asyncio
    async def test_send_file_message_success(self):
        """测试成功发送文件消息"""
        from src.feishu.file_ops import send_file_message

        with patch('src.feishu.file_ops._create_client') as mock_create_client:
            mock_response = Mock()
            mock_response.success.return_value = True

            mock_client = Mock()
            mock_client.im.v1.message.create.return_value = mock_response
            mock_create_client.return_value = mock_client

            result = await send_file_message(
                "test_secret",
                "user_123",
                "file_key_123"
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_send_file_message_failure(self):
        """测试发送文件消息失败"""
        from src.feishu.file_ops import send_file_message

        with patch('src.feishu.file_ops._create_client') as mock_create_client:
            mock_response = Mock()
            mock_response.success.return_value = False
            mock_response.code = 400
            mock_response.msg = "Send failed"

            mock_client = Mock()
            mock_client.im.v1.message.create.return_value = mock_response
            mock_create_client.return_value = mock_client

            result = await send_file_message(
                "test_secret",
                "user_123",
                "file_key_123"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_send_file_message_exception(self):
        """测试发送文件消息异常"""
        from src.feishu.file_ops import send_file_message

        with patch('src.feishu.file_ops._create_client') as mock_create_client:
            mock_create_client.side_effect = Exception("Network error")

            result = await send_file_message(
                "test_secret",
                "user_123",
                "file_key_123"
            )

            assert result is False