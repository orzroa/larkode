"""
测试 VideoGenCapability 类
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.minimax.capabilities.video_gen import VideoGenCapability


class TestVideoGenCapability:
    """测试视频生成能力"""

    @pytest.fixture
    def mock_client(self):
        """模拟 MiniMaxClient"""
        client = AsyncMock()
        client.text_to_video = AsyncMock(return_value="task_123")
        client.image_to_video = AsyncMock(return_value="task_456")
        client.get_video_task_result = AsyncMock(return_value={"status": "Success", "file_id": "file_789"})
        client.retrieve_file = AsyncMock(return_value={"download_url": "https://example.com/video.mp4"})
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
    def video_capability(self, mock_client, mock_delivery):
        """创建 VideoGenCapability 实例"""
        return VideoGenCapability(client=mock_client, delivery=mock_delivery)

    @pytest.mark.asyncio
    async def test_text_to_video_empty_prompt(self, video_capability, mock_delivery):
        """测试空提示词"""
        await video_capability.text_to_video("user_123", "")
        mock_delivery.send_error.assert_called_once()
        assert "请提供提示词" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_video_no_task_id(self, video_capability, mock_client, mock_delivery):
        """测试任务提交失败"""
        mock_client.text_to_video.return_value = None
        await video_capability.text_to_video("user_123", "日出")
        mock_delivery.send_error.assert_called_once()
        assert "任务提交失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_video_exception(self, video_capability, mock_client, mock_delivery):
        """测试文生视频异常"""
        mock_client.text_to_video.side_effect = Exception("API error")
        await video_capability.text_to_video("user_123", "日出")
        mock_delivery.send_error.assert_called_once()
        assert "视频生成失败: API error" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_video_empty_prompt(self, video_capability, mock_delivery):
        """测试图生视频空提示词"""
        await video_capability.image_to_video("user_123", "")
        mock_delivery.send_error.assert_called_once()
        assert "请提供提示词" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_video_no_image_path(self, video_capability, mock_delivery):
        """测试图生视频没有图片"""
        with patch('src.minimax.get_user_image_path', return_value=None):
            await video_capability.image_to_video("user_123", "动起来")
            mock_delivery.send_error.assert_called_once()
            assert "请先上传一张图片" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_video_file_not_exists(self, video_capability, mock_delivery):
        """测试图生视频文件不存在"""
        await video_capability.image_to_video("user_111", "动起来", image_path="/nonexistent.png")
        mock_delivery.send_error.assert_called_once()
        assert "图片文件不存在" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_video_url(self, video_capability, mock_client, mock_delivery):
        """测试图生视频使用URL"""
        await video_capability.image_to_video("user_111", "动起来", image_path="https://example.com/img.png")
        mock_client.image_to_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_to_video_local_file(self, video_capability, mock_client, mock_delivery, tmp_path):
        """测试图生视频使用本地文件"""
        test_img = tmp_path / "test.png"
        test_img.write_bytes(b"fake image")
        await video_capability.image_to_video("user_111", "动起来", image_path=str(test_img))
        mock_client.image_to_video.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_to_video_no_task_id(self, video_capability, mock_client, mock_delivery):
        """测试图生视频任务提交失败"""
        mock_client.image_to_video.return_value = None
        await video_capability.image_to_video("user_111", "动起来", image_path="https://example.com/img.png")
        mock_delivery.send_error.assert_called_once()
        assert "任务提交失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_video_exception(self, video_capability, mock_client, mock_delivery):
        """测试图生视频异常"""
        mock_client.image_to_video.side_effect = Exception("API error")
        await video_capability.image_to_video("user_111", "动起来", image_path="https://example.com/img.png")
        mock_delivery.send_error.assert_called_once()
        assert "视频生成失败: API error" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_poll_video_task_success(self, video_capability, mock_client, mock_delivery):
        """测试轮询成功"""
        with patch.object(video_capability, '_download_video', return_value=Path("/tmp/test.mp4")):
            await video_capability._poll_video_task("user_123", "task_123", "测试")

            mock_delivery.send_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_video_task_fail(self, video_capability, mock_client, mock_delivery):
        """测试轮询失败"""
        mock_client.get_video_task_result.return_value = {"status": "Fail", "error_message": "生成失败"}
        await video_capability._poll_video_task("user_123", "task_123", "测试")

        mock_delivery.send_error.assert_called_once()
        assert "生成失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_poll_video_task_no_file_id(self, video_capability, mock_client, mock_delivery):
        """测试轮询成功但没有文件ID"""
        mock_client.get_video_task_result.return_value = {"status": "Success"}
        await video_capability._poll_video_task("user_123", "task_123", "测试")

        mock_delivery.send_error.assert_called_once()
        assert "未获取到文件ID" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_poll_video_task_exception(self, video_capability, mock_client, mock_delivery):
        """测试轮询异常"""
        mock_client.get_video_task_result.side_effect = Exception("Poll error")
        await video_capability._poll_video_task("user_123", "task_123", "测试")

        mock_delivery.send_error.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_video_success_no_url(self, video_capability, mock_client, mock_delivery):
        """测试处理成功但没有下载URL"""
        mock_client.retrieve_file.return_value = {}
        await video_capability._handle_video_success("user_123", "file_789")

        mock_delivery.send_error.assert_called_once()
        assert "未获取到视频下载链接" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_handle_video_success_download_failed(self, video_capability, mock_delivery):
        """测试下载失败"""
        with patch.object(video_capability, '_download_video', return_value=None):
            await video_capability._handle_video_success("user_123", "file_789")

            mock_delivery.send_error.assert_called_once()
            assert "视频下载失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_download_video_url(self, video_capability, tmp_path):
        """测试下载视频"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake video data"
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            result = await video_capability._download_video("user1", "https://example.com/video.mp4")
            assert result is not None
            assert result.exists()
            assert result.read_bytes() == b"fake video data"

    @pytest.mark.asyncio
    async def test_download_video_exception(self, video_capability):
        """测试下载异常"""
        with patch('httpx.AsyncClient') as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get.side_effect = Exception("Download error")
            mock_client_cls.return_value = mock_instance

            result = await video_capability._download_video("user1", "https://example.com/video.mp4")
            assert result is None


def test_logging_import_fallback():
    """测试 logging 导入 fallback"""
    import sys
    import importlib
    for mod in ['src.minimax.capabilities.video_gen', 'src.logging_utils']:
        if mod in sys.modules:
            del sys.modules[mod]
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == 'src.logging_utils':
            raise ImportError("logging_utils not available")
        return original_import(name, *args, **kwargs)
    with patch('builtins.__import__', side_effect=mock_import):
        import src.minimax.capabilities.video_gen
        importlib.reload(src.minimax.capabilities.video_gen)
        assert hasattr(src.minimax.capabilities.video_gen, 'logger')