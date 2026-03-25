"""
测试 ImageGenCapability 类
"""
import pytest
import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from src.minimax.capabilities.image_gen import ImageGenCapability


class TestImageGenCapability:
    """测试图片生成能力"""

    @pytest.fixture
    def mock_client(self):
        """模拟 MiniMaxClient"""
        client = AsyncMock()
        client.image_generation = AsyncMock(return_value={"image_urls": ["https://example.com/img.png"]})
        client.image_to_image = AsyncMock(return_value={"image_urls": ["https://example.com/new_img.png"]})
        return client

    @pytest.fixture
    def mock_delivery(self):
        """模拟 MiniMaxFeishuDelivery"""
        delivery = AsyncMock()
        delivery.send_error = AsyncMock()
        delivery.send_progress = AsyncMock()
        delivery.send_image = AsyncMock()
        return delivery

    @pytest.fixture
    def image_capability(self, mock_client, mock_delivery):
        """创建 ImageGenCapability 实例"""
        return ImageGenCapability(client=mock_client, delivery=mock_delivery)

    @pytest.mark.asyncio
    async def test_text_to_image_empty_prompt(self, image_capability, mock_delivery):
        """测试空提示词"""
        await image_capability.text_to_image("user_123", "")
        mock_delivery.send_error.assert_called_once()
        assert "请提供提示词" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_image_success_url(self, image_capability, mock_client, mock_delivery):
        """测试文生图成功返回URL"""
        with patch.object(image_capability, '_download_image', return_value=Path("/tmp/test.png")):
            await image_capability.text_to_image("user_123", "一只可爱的猫")
            mock_client.image_generation.assert_called_once()
            mock_delivery.send_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_to_image_success_base64(self, image_capability, mock_client, mock_delivery):
        """测试文生图成功返回base64"""
        mock_client.image_generation.return_value = {"image_base64": ["iVBORw0KGgoAAAANSUhEUgAA"]}
        with patch.object(image_capability, '_save_base64_image', return_value=Path("/tmp/test.png")):
            await image_capability.text_to_image("user_123", "一只可爱的猫")
            mock_delivery.send_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_to_image_no_data(self, image_capability, mock_client, mock_delivery):
        """测试文生图返回空数据"""
        mock_client.image_generation.return_value = {}
        await image_capability.text_to_image("user_123", "一只可爱的猫")
        mock_delivery.send_error.assert_called_once()
        assert "未获取到图片数据" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_image_download_failed(self, image_capability, mock_delivery):
        """测试图片下载失败"""
        with patch.object(image_capability, '_download_image', return_value=None):
            await image_capability.text_to_image("user_123", "一只可爱的猫")
            mock_delivery.send_error.assert_called_once()
            assert "图片下载失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_image_save_failed(self, image_capability, mock_client, mock_delivery):
        """测试图片保存失败"""
        mock_client.image_generation.return_value = {"image_base64": ["iVBORw0KGgoAAAANSUhEUgAA"]}
        with patch.object(image_capability, '_save_base64_image', return_value=None):
            await image_capability.text_to_image("user_123", "一只可爱的猫")
            mock_delivery.send_error.assert_called_once()
            assert "图片保存失败" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_text_to_image_exception(self, image_capability, mock_client, mock_delivery):
        """测试文生图异常"""
        mock_client.image_generation.side_effect = Exception("API error")
        await image_capability.text_to_image("user_123", "一只可爱的猫")
        mock_delivery.send_error.assert_called_once()
        assert "图片生成失败: API error" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_image_empty_prompt(self, image_capability, mock_delivery):
        """测试图生图空提示词"""
        await image_capability.image_to_image("user_123", "")
        mock_delivery.send_error.assert_called_once()
        assert "请提供提示词" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_image_no_image_path(self, image_capability, mock_delivery):
        """测试图生图没有图片路径"""
        with patch('src.minimax.get_user_image_path', return_value=None):
            await image_capability.image_to_image("user_123", "变成油画风格")
            mock_delivery.send_error.assert_called_once()
            assert "请先上传一张图片" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_image_file_not_exists(self, image_capability, mock_delivery):
        """测试图生图文件不存在"""
        await image_capability.image_to_image("user_11", "变成油画风格", image_path="/nonexistent.png")
        mock_delivery.send_error.assert_called_once()
        assert "图片文件不存在" in str(mock_delivery.send_error.call_args[0][1])

    @pytest.mark.asyncio
    async def test_image_to_image_url(self, image_capability, mock_client, mock_delivery):
        """测试图生图使用URL"""
        with patch.object(image_capability, '_download_image', return_value=Path("/tmp/new.png")):
            await image_capability.image_to_image("user_111", "变成油画", image_path="https://example.com/img.png")
            mock_client.image_to_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_image_to_image_local_file(self, image_capability, mock_client, mock_delivery, tmp_path):
        """测试图生图使用本地文件"""
        test_img = tmp_path / "test.png"
        test_img.write_bytes(b"fake image")
        with patch.object(image_capability, '_download_image', return_value=Path("/tmp/new.png")):
            await image_capability.image_to_image("user_111", "变成油画", image_path=str(test_img))
            mock_client.image_to_image.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_image_url(self, image_capability, tmp_path):
        """测试下载网络图片"""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"fake image data"
        mock_response.raise_for_status = MagicMock()

        with patch('httpx.AsyncClient') as mock_client_cls:
            mock_instance = AsyncMock()
            mock_instance.__aenter__.return_value = mock_instance
            mock_instance.__aexit__.return_value = None
            mock_instance.get.return_value = mock_response
            mock_client_cls.return_value = mock_instance

            result = await image_capability._download_image("user1", "https://example.com/img.png")
            assert result is not None
            assert result.exists()
            assert result.read_bytes() == b"fake image data"

    @pytest.mark.asyncio
    async def test_download_image_file_protocol(self, image_capability, tmp_path):
        """测试下载本地文件协议"""
        test_file = tmp_path / "test.png"
        test_file.write_bytes(b"test data")
        result = await image_capability._download_image("user1", f"file://{test_file}")
        assert result == test_file

    @pytest.mark.asyncio
    async def test_save_base64_image(self, image_capability, tmp_path):
        """测试保存base64图片"""
        base64_data = base64.b64encode(b"fake image data").decode()
        result = await image_capability._save_base64_image("user1", base64_data)
        assert result is not None
        assert result.exists()
        assert result.read_bytes() == b"fake image data"


def test_logging_import_fallback():
    """测试 logging 导入 fallback"""
    import sys
    import importlib
    for mod in ['src.minimax.capabilities.image_gen', 'src.logging_utils']:
        if mod in sys.modules:
            del sys.modules[mod]
    original_import = __import__
    def mock_import(name, *args, **kwargs):
        if name == 'src.logging_utils':
            raise ImportError("logging_utils not available")
        return original_import(name, *args, **kwargs)
    with patch('builtins.__import__', side_effect=mock_import):
        import src.minimax.capabilities.image_gen
        importlib.reload(src.minimax.capabilities.image_gen)
        assert hasattr(src.minimax.capabilities.image_gen, 'logger')
