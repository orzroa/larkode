"""
MiniMax 命令解析与分发测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path


class TestMiniMaxCommands:
    """MiniMax 命令处理器测试"""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.fixture
    def mock_delivery(self):
        delivery = AsyncMock()
        delivery.send_text = AsyncMock()
        delivery.send_error = AsyncMock()
        delivery.send_progress = AsyncMock()
        return delivery

    @pytest.fixture
    def commands(self, mock_client, mock_delivery):
        from src.minimax.commands import MiniMaxCommands
        return MiniMaxCommands(
            client=mock_client,
            delivery=mock_delivery,
        )

    @pytest.mark.asyncio
    async def test_help_command(self, commands, mock_delivery):
        """测试 #mm help"""
        await commands.handle_command("user-123", "help")
        mock_delivery.send_text.assert_called_once()
        call_args = mock_delivery.send_text.call_args
        assert "MiniMax" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_img_command_empty_prompt(self, commands, mock_delivery):
        """测试 #mm img 空提示词"""
        await commands.handle_command("user-123", "img ")
        mock_delivery.send_error.assert_called_once()
        call_args = mock_delivery.send_error.call_args[0]
        assert "提示词" in call_args[1]

    @pytest.mark.asyncio
    async def test_img_command_success(self, commands, mock_client, mock_delivery):
        """测试 #mm img 成功"""
        mock_client.image_generation = AsyncMock(
            return_value={"image_urls": ["http://example.com/img.png"]}
        )

        with patch.object(commands.image_cap, "_download_image", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = Path("/tmp/test.png")
            with patch.object(commands.delivery, "send_image", new_callable=AsyncMock):
                await commands.handle_command("user-123", "img 画一只可爱的猫")
                mock_client.image_generation.assert_called_once_with(prompt="画一只可爱的猫", response_format="url")

    @pytest.mark.asyncio
    async def test_unknown_subcommand(self, commands, mock_delivery):
        """测试未知子命令"""
        await commands.handle_command("user-123", "foobar")
        mock_delivery.send_error.assert_called_once()
        call_args = mock_delivery.send_error.call_args[0]
        assert "foobar" in call_args[1]

    @pytest.mark.asyncio
    async def test_tts_command(self, commands, mock_client, mock_delivery):
        """测试 #mm tts"""
        mock_client.text_to_speech = AsyncMock(return_value=b"fake audio")

        with patch.object(commands.voice_cap, "_save_audio", new_callable=AsyncMock) as mock_save:
            mock_save.return_value = Path("/tmp/test.mp3")
            with patch.object(commands.delivery, "send_audio", new_callable=AsyncMock):
                await commands.handle_command("user-123", "tts 今天天气真好")
                mock_client.text_to_speech.assert_called_once_with(text="今天天气真好")

    @pytest.mark.asyncio
    async def test_t2v_command(self, commands, mock_client, mock_delivery):
        """测试 #mm t2v"""
        mock_client.text_to_video = AsyncMock(return_value="video-task-123")

        await commands.handle_command("user-123", "t2v 日出时分海面波光粼粼")
        mock_client.text_to_video.assert_called_once_with(
            prompt="日出时分海面波光粼粼",
            model="MiniMax-Hailuo-2.3"
        )

    @pytest.mark.asyncio
    async def test_music_command(self, commands, mock_client, mock_delivery):
        """测试 #mm music"""
        mock_client.text_to_music = AsyncMock(
            return_value={"data": {"audio": "https://example.com/music.mp3"}}
        )

        with patch.object(commands.music_cap, "_download_music", new_callable=AsyncMock) as mock_dl:
            mock_dl.return_value = Path("/tmp/test.mp3")
            with patch.object(commands.delivery, "send_file", new_callable=AsyncMock):
                await commands.handle_command("user-123", "music 古典 明月几时有")
                # 注意：prompt 会被补足到至少 10 个字符
                mock_client.text_to_music.assert_called_once()
                call_kwargs = mock_client.text_to_music.call_args[1]
                assert "古典" in call_kwargs["prompt"]
                assert call_kwargs["lyrics"] == "明月几时有"
                assert call_kwargs["output_format"] == "url"