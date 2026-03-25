"""
测试 MusicGenCapability 类
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.minimax.capabilities.music_gen import MusicGenCapability


class TestMusicGenCapability:
    """测试音乐生成能力"""

    @pytest.fixture
    def mock_client(self):
        """模拟 MiniMaxClient"""
        client = AsyncMock()
        client.text_to_music = AsyncMock(return_value={
            "data": {"audio": "https://example.com/music.mp3"},
            "extra_info": {"music_duration": 120000}
        })
        return client

    @pytest.fixture
    def mock_delivery(self):
        """模拟 MiniMaxFeishuDelivery"""
        delivery = AsyncMock()
        delivery.send_error = AsyncMock()
        delivery.send_progress = AsyncMock()
        delivery.send_file = AsyncMock()
        return delivery

    @pytest.fixture
    def music_capability(self, mock_client, mock_delivery):
        """创建 MusicGenCapability 实例"""
        return MusicGenCapability(client=mock_client, delivery=mock_delivery)

    def test_parse_music_prompt(self, music_capability):
        """测试音乐提示词解析"""
        # 正常格式：风格+歌词
        style, lyrics = music_capability._parse_music_prompt("古典 明月几时有 把酒问青天")
        assert style == "古典"
        assert lyrics == "明月几时有 把酒问青天"

        # 只有风格，没有歌词
        style, lyrics = music_capability._parse_music_prompt("摇滚")
        assert style == "摇滚"
        assert lyrics == ""

        # 歌词包含多个空格
        style, lyrics = music_capability._parse_music_prompt("流行 今天 天气 真 好")
        assert style == "流行"
        assert lyrics == "今天 天气 真 好"

        # 风格本身有空格的情况
        style, lyrics = music_capability._parse_music_prompt("电子流行 阳光明媚的一天")
        assert style == "电子流行"
        assert lyrics == "阳光明媚的一天"

    @pytest.mark.asyncio
    async def test_text_to_music_empty_prompt(self, music_capability, mock_delivery):
        """测试空提示词"""
        await music_capability.text_to_music("user_123", "")
        mock_delivery.send_error.assert_called_once()
        assert "请提供音乐提示词" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_music_no_lyrics(self, music_capability, mock_delivery):
        """测试只有风格没有歌词"""
        await music_capability.text_to_music("user_123", "古典")
        mock_delivery.send_error.assert_called_once()
        assert "必须提供歌词" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_music_short_style(self, music_capability, mock_client):
        """测试风格短于10字符时自动补充"""
        with patch.object(music_capability, '_download_music', return_value=Path("/tmp/test.mp3")):
            await music_capability.text_to_music("user_123", "古典 明月几时有")
            # 验证风格被补充
            call_args = mock_client.text_to_music.call_args
            assert call_args[1]['prompt'] == "古典风格，音乐优雅动听"
            assert call_args[1]['lyrics'] == "明月几时有"

    @pytest.mark.asyncio
    async def test_text_to_music_long_style(self, music_capability, mock_client):
        """测试风格足够长时不补充"""
        with patch.object(music_capability, '_download_music', return_value=Path("/tmp/test.mp3")):
            # 使用超过 10 个字符的风格
            await music_capability.text_to_music("user_123", "中国风古典优雅的音乐 明月几时有")
            call_args = mock_client.text_to_music.call_args
            assert call_args[1]['prompt'] == "中国风古典优雅的音乐"

    @pytest.mark.asyncio
    async def test_text_to_music_success(self, music_capability, mock_client, mock_delivery):
        """测试音乐生成成功"""
        with patch.object(music_capability, '_download_music', return_value=Path("/tmp/test.mp3")):
            await music_capability.text_to_music("user_123", "古典 明月几时有")
            mock_client.text_to_music.assert_called_once()
            mock_delivery.send_file.assert_called_once_with("user_123", Path("/tmp/test.mp3"))

    @pytest.mark.asyncio
    async def test_text_to_music_download_failed(self, music_capability, mock_delivery):
        """测试音乐下载失败"""
        with patch.object(music_capability, '_download_music', return_value=None):
            await music_capability.text_to_music("user_123", "古典 明月几时有")
            mock_delivery.send_error.assert_called_once()
            assert "音乐下载失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_music_no_audio_url(self, music_capability, mock_client, mock_delivery):
        """测试返回结果没有音频URL"""
        mock_client.text_to_music.return_value = {"data": {}}
        await music_capability.text_to_music("user_123", "古典 明月几时有")
        mock_delivery.send_error.assert_called_once()
        assert "音乐生成失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_music_api_error(self, music_capability, mock_client, mock_delivery):
        """测试API调用异常"""
        mock_client.text_to_music.side_effect = Exception("API error")
        await music_capability.text_to_music("user_123", "古典 明月几时有")
        mock_delivery.send_error.assert_called_once()
        assert "音乐生成失败: API error" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_download_music_url(self, music_capability, tmp_path):
        """测试下载网络音乐"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake audio data"
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            result = await music_capability._download_music("user_123", "https://example.com/music.mp3")
            assert result is not None
            assert result.exists()
            assert result.read_bytes() == b"fake audio data"

    @pytest.mark.asyncio
    async def test_download_music_failed(self, music_capability):
        """测试下载音乐失败"""
        with patch('httpx.AsyncClient') as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get.side_effect = Exception("Download error")
            mock_client_cls.return_value = mock_instance

            result = await music_capability._download_music("user_123", "https://example.com/music.mp3")
            assert result is None


def test_logging_import_fallback():
    """测试 logging 导入 fallback"""
    import sys
    import importlib

    # 清除模块缓存
    for mod in ['src.minimax.capabilities.music_gen', 'src.logging_utils']:
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
        import src.minimax.capabilities.music_gen
        importlib.reload(src.minimax.capabilities.music_gen)
        assert hasattr(src.minimax.capabilities.music_gen, 'logger')
