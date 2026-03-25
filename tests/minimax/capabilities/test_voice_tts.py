"""
测试 VoiceTTSCapability 类
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.minimax.capabilities.voice_tts import VoiceTTSCapability


class TestVoiceTTSCapability:
    """测试文字转语音能力"""

    @pytest.fixture
    def mock_client(self):
        """模拟 MiniMaxClient"""
        client = AsyncMock()
        client.text_to_speech = AsyncMock(return_value=b"fake audio data")
        return client

    @pytest.fixture
    def mock_delivery(self):
        """模拟 MiniMaxFeishuDelivery"""
        delivery = AsyncMock()
        delivery.send_error = AsyncMock()
        delivery.send_progress = AsyncMock()
        delivery.send_audio = AsyncMock()
        return delivery

    @pytest.fixture
    def tts_capability(self, mock_client, mock_delivery):
        """创建 VoiceTTSCapability 实例"""
        return VoiceTTSCapability(client=mock_client, delivery=mock_delivery)

    @pytest.mark.asyncio
    async def test_text_to_speech_empty_text(self, tts_capability, mock_delivery):
        """测试空文本输入"""
        await tts_capability.text_to_speech("user_123", "")

        mock_delivery.send_error.assert_called_once()
        assert "请提供要转换的文字" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_speech_too_long(self, tts_capability, mock_delivery):
        """测试文本超过长度限制"""
        long_text = "a" * 1001
        await tts_capability.text_to_speech("user_123", long_text)

        mock_delivery.send_error.assert_called_once()
        assert "不能超过 1000 字" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_speech_success(self, tts_capability, mock_client, mock_delivery):
        """测试语音生成成功"""
        with patch.object(tts_capability, '_save_audio', return_value=Path("/tmp/test.mp3")):
            await tts_capability.text_to_speech("user_123", "你好，世界")

            mock_client.text_to_speech.assert_called_once_with(text="你好，世界")
            mock_delivery.send_progress.assert_called_once()
            mock_delivery.send_audio.assert_called_once_with("user_123", Path("/tmp/test.mp3"))

    @pytest.mark.asyncio
    async def test_text_to_speech_no_audio_data(self, tts_capability, mock_client, mock_delivery):
        """测试语音生成返回空数据"""
        mock_client.text_to_speech.return_value = b""
        await tts_capability.text_to_speech("user_123", "你好")

        mock_delivery.send_error.assert_called_once()
        assert "未获取到音频数据" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_speech_save_failed(self, tts_capability, mock_delivery):
        """测试音频保存失败"""
        with patch.object(tts_capability, '_save_audio', return_value=None):
            await tts_capability.text_to_speech("user_123", "你好")

            mock_delivery.send_error.assert_called_once()
            assert "音频保存失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_speech_exception(self, tts_capability, mock_client, mock_delivery):
        """测试语音生成异常"""
        mock_client.text_to_speech.side_effect = Exception("API error")
        await tts_capability.text_to_speech("user_123", "你好")

        mock_delivery.send_error.assert_called_once()
        assert "语音生成失败: API error" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_save_audio_success(self, tts_capability, tmp_path):
        """测试保存音频成功"""
        audio_bytes = b"fake audio data"
        result = await tts_capability._save_audio("user_123", audio_bytes)

        assert result is not None
        assert result.exists()
        assert result.read_bytes() == audio_bytes

    @pytest.mark.asyncio
    async def test_save_audio_exception(self, tts_capability):
        """测试保存音频异常"""
        with patch('src.minimax.capabilities.voice_tts.open', side_effect=Exception("Write error")):
            result = await tts_capability._save_audio("user_123", b"test")
            assert result is None


def test_logging_import_fallback():
    """测试 logging 导入 fallback"""
    import sys
    import importlib

    # 清除模块缓存
    for mod in ['src.minimax.capabilities.voice_tts', 'src.logging_utils']:
        if mod in sys.modules:
            del sys.modules[mod]

    # 模拟导入 logging_utils 失败
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == 'src.logging_utils':
            raise ImportError("logging_utils not available")
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=mock_import):
        # 导入模块
        import src.minimax.capabilities.voice_tts
        importlib.reload(src.minimax.capabilities.voice_tts)

        assert hasattr(src.minimax.capabilities.voice_tts, 'logger')
