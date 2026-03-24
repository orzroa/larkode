"""
MiniMax 客户端测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestMiniMaxClient:
    """MiniMax API 客户端测试"""

    @pytest.fixture
    def mock_settings(self):
        """模拟配置"""
        with patch("src.minimax.client.get_settings") as mock:
            settings = MagicMock()
            settings.minimax_api_key = "test_api_key"
            settings.minimax_group_id = "test_group_id"
            mock.return_value = settings
            yield mock

    @pytest.fixture
    def client(self, mock_settings):
        """创建测试客户端"""
        from src.minimax.client import MiniMaxClient
        return MiniMaxClient(api_key="test_key", group_id="test_group")

    def test_client_initialization(self, client):
        """测试客户端初始化"""
        assert client.api_key == "test_key"
        assert client.group_id == "test_group"

    def test_client_without_api_key(self, mock_settings):
        """测试未配置 API Key"""
        from src.minimax.client import MiniMaxClient
        client = MiniMaxClient()
        assert client.api_key == "test_api_key"

    @pytest.mark.asyncio
    async def test_image_generation_success(self, client):
        """测试图片生成成功"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"image_urls": ["https://example.com/img.png"]},
            "base_resp": {"status_code": 0},
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.image_generation(prompt="a cute cat")
            assert "image_urls" in result
            assert result["image_urls"][0] == "https://example.com/img.png"

    @pytest.mark.asyncio
    async def test_image_generation_base64(self, client):
        """测试图片生成返回 base64"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"image_base64": ["iVBORw0KGgoAAAANS"]},
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.image_generation(prompt="a cute cat")
            assert "image_base64" in result

    @pytest.mark.asyncio
    async def test_text_to_video(self, client):
        """测试文生视频"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "video-task-123",
            "base_resp": {"status_code": 0},
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            task_id = await client.text_to_video(prompt="a sunset")
            assert task_id == "video-task-123"

    @pytest.mark.asyncio
    async def test_text_to_speech(self, client):
        """测试文字转语音"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"audio": "48656c6c6f", "status": 2},
            "base_resp": {"status_code": 0},
        }

        with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            result = await client.text_to_speech(text="hello")
            assert result == b"Hello"

    @pytest.mark.asyncio
    async def test_text_to_music(self, client):
        """测试音乐生成"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"audio_url": "https://example.com/music.mp3"},
            "base_resp": {"status_code": 0},
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.text_to_music(prompt="happy electronic music")
            assert "audio_url" in result or "data" in result

    @pytest.mark.asyncio
    async def test_auth_error(self, client):
        """测试认证失败"""
        from src.minimax.exceptions import MiniMaxAuthError

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(MiniMaxAuthError):
                await client.image_generation(prompt="test")

    @pytest.mark.asyncio
    async def test_rate_limit_error(self, client):
        """测试频率限制"""
        from src.minimax.exceptions import MiniMaxRateLimitError

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with pytest.raises(MiniMaxRateLimitError):
                await client.image_generation(prompt="test")

    @pytest.mark.asyncio
    async def test_wait_for_task_success(self, client):
        """测试轮询等待任务成功"""
        call_count = [0]

        async def mock_get_result(task_id):
            call_count[0] += 1
            if call_count[0] < 2:
                return {"status": "Processing"}
            return {"status": "Success", "video_url": "http://example.com/video.mp4"}

        result = await client.wait_for_task(
            task_id="test-task",
            get_result_fn=mock_get_result,
            poll_interval=0.01,
            timeout=5,
        )
        assert result["status"] == "Success"

    @pytest.mark.asyncio
    async def test_wait_for_task_timeout(self, client):
        """测试轮询超时"""
        from src.minimax.exceptions import MiniMaxTimeoutError

        async def mock_get_result(task_id):
            return {"status": "Processing"}

        with pytest.raises(MiniMaxTimeoutError):
            await client.wait_for_task(
                task_id="test-task",
                get_result_fn=mock_get_result,
                poll_interval=0.01,
                timeout=0.1,
            )

    @pytest.mark.asyncio
    async def test_speech_to_text(self, client):
        """测试语音转文字"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"text": "这是测试文本"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_file = MagicMock()
            mock_file.__enter__ = MagicMock(return_value=mock_file)
            mock_file.__exit__ = MagicMock(return_value=False)
            mock_file.read.return_value = b"fake audio data"

            with patch("builtins.open", return_value=mock_file):
                with patch("src.minimax.client.Path") as mock_path_cls:
                    mock_path_instance = MagicMock()
                    mock_path_instance.name = "test.mp3"
                    mock_path_cls.return_value = mock_path_instance

                    with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
                        mock_instance = AsyncMock()
                        mock_instance.__aenter__.return_value = mock_instance
                        mock_instance.__aexit__.return_value = None
                        mock_instance.post.return_value = mock_response
                        mock_client_cls.return_value = mock_instance

                        result = await client.speech_to_text(audio_path="/path/to/test.mp3")
                        assert result["text"] == "这是测试文本"
