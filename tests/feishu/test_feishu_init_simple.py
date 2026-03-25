"""
飞书 __init__ 简单测试，覆盖未覆盖的三行代码
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock


def test_feishu_api_methods():
    """测试 FeishuAPI 类的三个方法是否存在并被正确调用"""
    # 导入模块
    from src.feishu import FeishuAPI

    # 创建实例
    api = FeishuAPI("app_id", "app_secret")
    api.app_secret = "test_secret"

    # 测试 download_file 方法被正确定义
    assert hasattr(api, 'download_file')
    assert callable(api.download_file)

    # 测试 upload_file 方法被正确定义
    assert hasattr(api, 'upload_file')
    assert callable(api.upload_file)

    # 测试 send_file_message 方法被正确定义
    assert hasattr(api, 'send_file_message')
    assert callable(api.send_file_message)


@pytest.mark.asyncio
async def test_download_file_call():
    """测试 download_file 实际调用"""
    from src.feishu import FeishuAPI

    # mock 全局的 download_file 函数
    with patch('src.feishu.download_file', new_callable=AsyncMock) as mock_download:
        mock_download.return_value = "/tmp/test.txt"

        api = FeishuAPI("app_id", "app_secret")
        api.app_secret = "test_secret"

        await api.download_file("msg1", "file1", None)

        mock_download.assert_called_once()


@pytest.mark.asyncio
async def test_upload_file_call():
    """测试 upload_file 实际调用"""
    from src.feishu import FeishuAPI

    with patch('src.feishu.upload_file', new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = {"file_key": "test"}

        api = FeishuAPI("app_id", "app_secret")
        api.app_secret = "test_secret"

        await api.upload_file("/tmp/test.txt", "txt")

        mock_upload.assert_called_once()


@pytest.mark.asyncio
async def test_send_file_message_call():
    """测试 send_file_message 实际调用"""
    from src.feishu import FeishuAPI

    with patch('src.feishu.send_file_message', new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"message_id": "msg1"}

        api = FeishuAPI("app_id", "app_secret")
        api.app_secret = "test_secret"

        await api.send_file_message("user1", "file1")

        mock_send.assert_called_once()
