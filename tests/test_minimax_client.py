"""
MiniMax 客户端测试
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import httpx


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

    def test_client_warning_no_api_key(self, mock_settings):
        """测试无 API Key 时发出警告"""
        from src.minimax.client import MiniMaxClient
        # 设置空 API key
        mock_settings.return_value.minimax_api_key = None
        client = MiniMaxClient()
        assert client.api_key is None

    def test_get_client_creates_new(self, client):
        """测试 _get_client 创建新客户端"""
        httpx_client = client._get_client()
        assert httpx_client is not None
        assert isinstance(httpx_client, httpx.AsyncClient)

    def test_get_client_reuses_existing(self, client):
        """测试 _get_client 复用现有客户端"""
        client1 = client._get_client()
        client2 = client._get_client()
        assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_client(self, client):
        """测试关闭客户端"""
        client._get_client()  # 创建客户端
        await client.close()
        assert client._client is None

    @pytest.mark.asyncio
    async def test_close_already_closed(self, client):
        """测试关闭已关闭的客户端"""
        await client.close()  # 不会报错
        assert client._client is None

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

    # ==================== 更多测试 ====================

    @pytest.mark.asyncio
    async def test_handle_response_non_json(self, client):
        """测试非 JSON 响应"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = Exception("Not JSON")
        mock_response.text = "plain text"

        result = client._handle_response(mock_response)
        assert result == {}

    @pytest.mark.asyncio
    async def test_handle_response_base_resp_error(self, client):
        """测试 base_resp 错误"""
        from src.minimax.exceptions import MiniMaxAPIError

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "base_resp": {"status_code": 1001, "status_msg": "参数错误"}
        }

        with pytest.raises(MiniMaxAPIError) as exc_info:
            client._handle_response(mock_response)
        assert "参数错误" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_response_api_error_with_msg(self, client):
        """测试 API 错误（带 msg 字段）"""
        from src.minimax.exceptions import MiniMaxAPIError

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"msg": "Bad Request"}

        with pytest.raises(MiniMaxAPIError) as exc_info:
            client._handle_response(mock_response)
        assert "Bad Request" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_handle_response_api_error_with_message(self, client):
        """测试 API 错误（带 message 字段）"""
        from src.minimax.exceptions import MiniMaxAPIError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {"message": "Internal Error"}

        with pytest.raises(MiniMaxAPIError) as exc_info:
            client._handle_response(mock_response)
        assert "Internal Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_image_generation_top_level_urls(self, client):
        """测试图片生成返回顶层 image_urls"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "image_urls": ["https://example.com/img1.png", "https://example.com/img2.png"]
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.image_generation(prompt="a cute cat")
            assert result["image_urls"] == ["https://example.com/img1.png", "https://example.com/img2.png"]

    @pytest.mark.asyncio
    async def test_image_generation_top_level_base64(self, client):
        """测试图片生成返回顶层 image_base64"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "image_base64": ["base64data1", "base64data2"]
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.image_generation(prompt="a cute cat")
            assert result["image_base64"] == ["base64data1", "base64data2"]

    @pytest.mark.asyncio
    async def test_image_generation_empty_result(self, client):
        """测试图片生成返回空结果"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.image_generation(prompt="a cute cat")
            assert result == {}

    @pytest.mark.asyncio
    async def test_get_video_task_result(self, client):
        """测试查询视频任务结果"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "Success",
            "file_id": "file-123"
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.get_video_task_result("task-123")
            assert result["status"] == "Success"

    @pytest.mark.asyncio
    async def test_retrieve_file(self, client):
        """测试获取文件下载链接"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "file": {
                "download_url": "https://example.com/download.mp4",
                "filename": "video.mp4",
                "bytes": 1024000,
                "file_id": "file-123"
            }
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.retrieve_file("file-123")
            assert result["download_url"] == "https://example.com/download.mp4"
            assert result["filename"] == "video.mp4"
            assert result["bytes"] == 1024000

    @pytest.mark.asyncio
    async def test_retrieve_file_missing_fields(self, client):
        """测试获取文件（缺少字段）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"file": {}}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.retrieve_file("file-123")
            assert result["download_url"] == ""
            assert result["filename"] == ""
            assert result["bytes"] == 0

    @pytest.mark.asyncio
    async def test_image_to_video_with_url(self, client):
        """测试图生视频（URL 图片）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "video-task-123",
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            task_id = await client.image_to_video(
                prompt="make it move",
                image_path="https://example.com/image.png"
            )
            assert task_id == "video-task-123"

    @pytest.mark.asyncio
    async def test_image_to_video_with_base64(self, client):
        """测试图生视频（Base64 图片）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "video-task-123",
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            task_id = await client.image_to_video(
                prompt="make it move",
                image_path="data:image/png;base64,iVBORw0KGgo="
            )
            assert task_id == "video-task-123"

    @pytest.mark.asyncio
    async def test_image_to_video_with_local_file_jpeg(self, client):
        """测试图生视频（本地 JPEG 文件）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "video-task-123",
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch("builtins.open", mock_open(read_data=b"fake image data")):
                task_id = await client.image_to_video(
                    prompt="make it move",
                    image_path="/path/to/image.jpg"
                )
            assert task_id == "video-task-123"

    @pytest.mark.asyncio
    async def test_image_to_video_with_local_file_png(self, client):
        """测试图生视频（本地 PNG 文件）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "video-task-123",
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch("builtins.open", mock_open(read_data=b"fake image data")):
                task_id = await client.image_to_video(
                    prompt="make it move",
                    image_path="/path/to/image.PNG"
                )
            assert task_id == "video-task-123"

    @pytest.mark.asyncio
    async def test_image_to_video_with_local_file_webp(self, client):
        """测试图生视频（本地 WebP 文件）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "task_id": "video-task-123",
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            with patch("builtins.open", mock_open(read_data=b"fake image data")):
                task_id = await client.image_to_video(
                    prompt="make it move",
                    image_path="/path/to/image.webp"
                )
            assert task_id == "video-task-123"

    @pytest.mark.asyncio
    async def test_text_to_speech_auth_error(self, client):
        """测试 TTS 认证失败"""
        from src.minimax.exceptions import MiniMaxAuthError

        mock_response = MagicMock()
        mock_response.status_code = 401

        with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            with pytest.raises(MiniMaxAuthError):
                await client.text_to_speech(text="hello")

    @pytest.mark.asyncio
    async def test_text_to_speech_rate_limit(self, client):
        """测试 TTS 频率限制"""
        from src.minimax.exceptions import MiniMaxRateLimitError

        mock_response = MagicMock()
        mock_response.status_code = 429

        with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            with pytest.raises(MiniMaxRateLimitError):
                await client.text_to_speech(text="hello")

    @pytest.mark.asyncio
    async def test_text_to_speech_api_error(self, client):
        """测试 TTS API 错误"""
        from src.minimax.exceptions import MiniMaxAPIError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "base_resp": {"status_msg": "Internal Error"}
        }

        with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            with pytest.raises(MiniMaxAPIError) as exc_info:
                await client.text_to_speech(text="hello")
            assert "Internal Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_text_to_speech_api_error_non_json(self, client):
        """测试 TTS API 错误（非 JSON 响应）"""
        from src.minimax.exceptions import MiniMaxAPIError

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = Exception("Not JSON")

        with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            with pytest.raises(MiniMaxAPIError) as exc_info:
                await client.text_to_speech(text="hello")
            assert "HTTP 500" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_text_to_speech_fallback_binary(self, client):
        """测试 TTS 降级返回二进制"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}
        mock_response.content = b"binary audio data"

        with patch("src.minimax.client.httpx.AsyncClient") as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.post.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            result = await client.text_to_speech(text="hello")
            assert result == b"binary audio data"

    @pytest.mark.asyncio
    async def test_text_to_speech_streaming_success(self, client):
        """测试流式 TTS"""
        from unittest.mock import AsyncMock

        mock_response = MagicMock()
        mock_response.status_code = 200

        # 创建异步生成器
        async def async_iter_bytes():
            yield b"chunk1"
            yield b"chunk2"
        mock_response.aiter_bytes = async_iter_bytes

        # 创建 stream 的返回值 - 需要是一个异步上下文管理器
        stream_context = MagicMock()
        stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        stream_context.__aexit__ = AsyncMock(return_value=None)

        mock_httpx_client = MagicMock()
        mock_httpx_client.stream.return_value = stream_context
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.minimax.client.httpx.AsyncClient", return_value=mock_httpx_client):
            chunks = []
            async for chunk in client.text_to_speech_streaming(text="hello"):
                chunks.append(chunk)
            assert chunks == [b"chunk1", b"chunk2"]

    @pytest.mark.asyncio
    async def test_text_to_speech_streaming_auth_error(self, client):
        """测试流式 TTS 认证错误"""
        from src.minimax.exceptions import MiniMaxAuthError

        mock_response = MagicMock()
        mock_response.status_code = 401

        stream_context = MagicMock()
        stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        stream_context.__aexit__ = AsyncMock(return_value=None)

        mock_httpx_client = MagicMock()
        mock_httpx_client.stream.return_value = stream_context
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.minimax.client.httpx.AsyncClient", return_value=mock_httpx_client):
            with pytest.raises(MiniMaxAuthError):
                async for _ in client.text_to_speech_streaming(text="hello"):
                    pass

    @pytest.mark.asyncio
    async def test_text_to_speech_streaming_api_error(self, client):
        """测试流式 TTS API 错误"""
        from src.minimax.exceptions import MiniMaxAPIError

        mock_response = MagicMock()
        mock_response.status_code = 500

        stream_context = MagicMock()
        stream_context.__aenter__ = AsyncMock(return_value=mock_response)
        stream_context.__aexit__ = AsyncMock(return_value=None)

        mock_httpx_client = MagicMock()
        mock_httpx_client.stream.return_value = stream_context
        mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
        mock_httpx_client.__aexit__ = AsyncMock(return_value=None)

        with patch("src.minimax.client.httpx.AsyncClient", return_value=mock_httpx_client):
            with pytest.raises(MiniMaxAPIError):
                async for _ in client.text_to_speech_streaming(text="hello"):
                    pass

    @pytest.mark.asyncio
    async def test_text_to_music_with_lyrics(self, client):
        """测试音乐生成（带歌词）"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": {"audio_url": "https://example.com/music.mp3"},
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.text_to_music(
                prompt="happy music",
                lyrics="la la la"
            )
            assert result["data"]["audio_url"] == "https://example.com/music.mp3"

    @pytest.mark.asyncio
    async def test_text_to_music_v2(self, client):
        """测试音乐生成 V2"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "audio": "48656c6c6f",
            "extra_info": {"duration": 60}
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.text_to_music_v2(
                prompt="electronic music",
                duration=60
            )
            assert "audio" in result

    @pytest.mark.asyncio
    async def test_get_music_task_result(self, client):
        """测试查询音乐任务结果"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "Success",
            "audio_url": "https://example.com/music.mp3"
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            result = await client.get_music_task_result("task-123")
            assert result["status"] == "Success"

    @pytest.mark.asyncio
    async def test_wait_for_task_fail_status(self, client):
        """测试轮询等待任务失败"""
        from src.minimax.exceptions import MiniMaxAPIError

        async def mock_get_result(task_id):
            return {"status": "FAIL", "message": "生成失败"}

        with pytest.raises(MiniMaxAPIError) as exc_info:
            await client.wait_for_task(
                task_id="test-task",
                get_result_fn=mock_get_result,
                poll_interval=0.01,
                timeout=5,
            )
        assert "生成失败" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_task_fail_lowercase(self, client):
        """测试轮询等待任务失败（小写）"""
        from src.minimax.exceptions import MiniMaxAPIError

        async def mock_get_result(task_id):
            return {"status": "fail", "msg": "出错了"}

        with pytest.raises(MiniMaxAPIError) as exc_info:
            await client.wait_for_task(
                task_id="test-task",
                get_result_fn=mock_get_result,
                poll_interval=0.01,
                timeout=5,
            )
        assert "出错了" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wait_for_task_success_variants(self, client):
        """测试轮询等待任务成功（多种状态格式）"""
        # 测试 SUCCESS
        async def mock_get_result_success(task_id):
            return {"status": "SUCCESS"}

        result = await client.wait_for_task(
            task_id="test-task",
            get_result_fn=mock_get_result_success,
            poll_interval=0.01,
            timeout=5,
        )
        assert result["status"] == "SUCCESS"

        # 测试 Completed
        async def mock_get_result_completed(task_id):
            return {"status": "Completed"}

        result = await client.wait_for_task(
            task_id="test-task",
            get_result_fn=mock_get_result_completed,
            poll_interval=0.01,
            timeout=5,
        )
        assert result["status"] == "Completed"

    @pytest.mark.asyncio
    async def test_wait_for_task_with_base_resp_status(self, client):
        """测试轮询等待任务（base_resp 状态）"""
        async def mock_get_result(task_id):
            return {"base_resp": {"status_msg": "Success"}}

        result = await client.wait_for_task(
            task_id="test-task",
            get_result_fn=mock_get_result,
            poll_interval=0.01,
            timeout=5,
        )
        assert result["base_resp"]["status_msg"] == "Success"

    def test_get_minimax_client_singleton(self, mock_settings):
        """测试全局客户端单例"""
        from src.minimax.client import get_minimax_client, _client
        import src.minimax.client as client_module

        # 重置全局客户端
        client_module._client = None

        client1 = get_minimax_client()
        client2 = get_minimax_client()
        assert client1 is client2

        # 清理
        client_module._client = None
