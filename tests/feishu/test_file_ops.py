"""
测试飞书文件操作模块

主要测试：
1. 音频格式检测函数 _detect_audio_extension
2. 图片/音频互斥分支逻辑
"""
import tempfile
from pathlib import Path

import pytest


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