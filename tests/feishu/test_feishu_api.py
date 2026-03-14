"""
FeishuAPI 单元测试
"""
import pytest
import asyncio
import json
from unittest.mock import patch, MagicMock, AsyncMock, PropertyMock
from typing import Any

from src.feishu.api import FeishuAPI
from src.feishu.exceptions import FeishuAPISendError


class TestFeishuAPIInit:
    """测试 FeishuAPI 初始化"""

    def test_init_basic(self):
        """测试基本初始化"""
        api = FeishuAPI("test_app_id", "test_secret")

        assert api.app_id == "test_app_id"
        assert api.app_secret == "test_secret"
        assert api.access_token is None
        assert api._client is None

    def test_init_with_empty_credentials(self):
        """测试空凭证初始化"""
        api = FeishuAPI("", "")

        assert api.app_id == ""
        assert api.app_secret == ""

    def test_init_sets_access_token_none(self):
        """测试初始化时 access_token 为 None"""
        api = FeishuAPI("app_id", "secret")

        assert api.access_token is None


class TestGetClient:
    """测试 _get_client 方法"""

    def test_get_client_creates_once(self):
        """测试客户端只创建一次"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                client1 = api._get_client()
                client2 = api._get_client()

                assert client1 is client2
                # builder 只应被调用一次
                assert mock_builder.call_count == 1

    def test_get_client_returns_cached(self):
        """测试返回缓存的客户端"""
        api = FeishuAPI("test_app_id", "test_secret")
        mock_client = MagicMock()
        api._client = mock_client

        client = api._get_client()

        assert client is mock_client


class TestSendMessage:
    """测试 send_message 方法"""

    @pytest.mark.asyncio
    async def test_send_message_success(self):
        """测试成功发送消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_123"

                mock_client = MagicMock()
                mock_client.im.v1.message.create = MagicMock(return_value=mock_response)
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("user_123", '{"type": "text", "content": "hello"}')

                    assert result == "msg_123"

    @pytest.mark.asyncio
    async def test_send_message_with_dict(self):
        """测试使用 dict 发送消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_456"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    message_dict = {"type": "text", "content": "hello"}
                    result = await api.send_message("user_123", message_dict)

                    assert result == "msg_456"

    @pytest.mark.asyncio
    async def test_send_message_failure(self):
        """测试发送消息失败"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = False
                mock_response.code = 400
                mock_response.msg = "Bad Request"
                mock_response.get_log_id.return_value = "log_123"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    with pytest.raises(FeishuAPISendError):
                        await api.send_message("user_123", "test message")

    @pytest.mark.asyncio
    async def test_send_message_with_exception(self):
        """测试发送消息时发生异常"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('asyncio.to_thread', side_effect=Exception("Network error")):
                with pytest.raises(FeishuAPISendError):
                    await api.send_message("user_123", "test message")

    @pytest.mark.asyncio
    async def test_send_message_with_plain_text(self):
        """测试发送纯文本消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_789"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("user_123", "plain text message")

                    assert result == "msg_789"


class TestSendInteractiveMessage:
    """测试 send_interactive_message 方法"""

    @pytest.mark.asyncio
    async def test_send_interactive_message(self):
        """测试发送交互式消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch.object(api, 'send_message', new_callable=AsyncMock) as mock_send:
            mock_send.return_value = "msg_123"

            result = await api.send_interactive_message(
                "user_123",
                '{"type": "interactive"}',
                "001"
            )

            assert result == "msg_123"
            mock_send.assert_called_once_with("user_123", '{"type": "interactive"}')


class TestGetUserInfo:
    """测试 get_user_info 方法"""

    @pytest.mark.asyncio
    async def test_get_user_info_success(self):
        """测试成功获取用户信息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.name = "Test User"
                mock_response.data.avatar_72x72 = "https://avatar.url"

                mock_client = MagicMock()
                mock_client.contact.v3.user.get.return_value = mock_response
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                result = await api.get_user_info("ou_123")

                assert result["user_id"] == "ou_123"
                assert result["name"] == "Test User"
                assert result["avatar"] == "https://avatar.url"

    @pytest.mark.asyncio
    async def test_get_user_info_not_found(self):
        """测试用户不存在"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = False

                mock_client = MagicMock()
                mock_client.contact.v3.user.get.return_value = mock_response
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                result = await api.get_user_info("ou_nonexistent")

                assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_with_exception(self):
        """测试获取用户信息时发生异常"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('lark_oapi.Client.builder') as mock_builder:
            mock_builder.side_effect = Exception("API Error")

            result = await api.get_user_info("ou_123")

            assert result is None


class TestGetMessage:
    """测试 get_message 方法"""

    @pytest.mark.asyncio
    async def test_get_message_success(self):
        """测试成功获取消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.msg_type = "text"
                mock_response.data.body = '{"text": "hello"}'

                mock_client = MagicMock()
                mock_client.im.v1.message.get.return_value = mock_response
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_response)

                    result = await api.get_message("msg_123")

                    assert result["message_id"] == "msg_123"
                    assert result["msg_type"] == "text"

    @pytest.mark.asyncio
    async def test_get_message_not_found(self):
        """测试消息不存在"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = False
                mock_response.code = 404
                mock_response.msg = "Not found"

                mock_client = MagicMock()
                mock_client.im.v1.message.get.return_value = mock_response
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_response)

                    result = await api.get_message("msg_nonexistent")

                    assert result is None

    @pytest.mark.asyncio
    async def test_get_message_with_exception(self):
        """测试获取消息时发生异常"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("Network error"))

            result = await api.get_message("msg_123")

            assert result is None


class TestUpdateMessage:
    """测试 update_message 方法"""

    @pytest.mark.asyncio
    async def test_update_message_success(self):
        """测试成功更新消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True

                mock_client = MagicMock()
                mock_client.im.v1.message.update.return_value = mock_response
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_response)

                    result = await api.update_message("msg_123", '{"updated": "content"}')

                    assert result is True

    @pytest.mark.asyncio
    async def test_update_message_failure(self):
        """测试更新消息失败"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = False
                mock_response.code = 400
                mock_response.msg = "Bad Request"

                mock_client = MagicMock()
                mock_client.im.v1.message.update.return_value = mock_response
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.get_event_loop') as mock_loop:
                    mock_loop.return_value.run_in_executor = AsyncMock(return_value=mock_response)

                    result = await api.update_message("msg_123", '{"updated": "content"}')

                    assert result is False

    @pytest.mark.asyncio
    async def test_update_message_with_exception(self):
        """测试更新消息时发生异常"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("Network error"))

            result = await api.update_message("msg_123", '{"updated": "content"}')

            assert result is False


class TestEdgeCases:
    """测试边界情况"""

    @pytest.mark.asyncio
    async def test_send_message_with_empty_user_id(self):
        """测试空用户 ID"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_123"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("", "test message")

                    assert result == "msg_123"

    @pytest.mark.asyncio
    async def test_send_message_with_long_content(self):
        """测试长内容消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        long_content = "x" * 10000

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_123"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("user_123", long_content)

                    assert result == "msg_123"

    @pytest.mark.asyncio
    async def test_send_message_with_unicode(self):
        """测试 Unicode 消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        unicode_content = "你好世界 🎉🎉🎉"

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_123"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("user_123", unicode_content)

                    assert result == "msg_123"

    @pytest.mark.asyncio
    async def test_send_message_with_json_string(self):
        """测试 JSON 字符串消息"""
        api = FeishuAPI("test_app_id", "test_secret")

        json_message = '{"type": "text", "content": "hello"}'

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data.message_id = "msg_123"

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("user_123", json_message)

                    assert result == "msg_123"

    @pytest.mark.asyncio
    async def test_send_message_response_no_data(self):
        """测试响应没有数据"""
        api = FeishuAPI("test_app_id", "test_secret")

        with patch('src.config.settings.get_settings') as mock_settings:
            mock_settings.return_value.FEISHU_APP_ID = "test_app_id"
            mock_settings.return_value.FEISHU_MESSAGE_DOMAIN = "FEISHU_DOMAIN"
            mock_settings.return_value.FEISHU_MESSAGE_RECEIVE_ID_TYPE = "open_id"

            with patch('lark_oapi.Client.builder') as mock_builder:
                mock_response = MagicMock()
                mock_response.success.return_value = True
                mock_response.data = None

                mock_client = MagicMock()
                mock_builder.return_value.app_id.return_value.app_secret.return_value.domain.return_value.log_level.return_value.build.return_value = mock_client

                with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                    mock_to_thread.return_value = mock_response

                    result = await api.send_message("user_123", "test")

                    assert result == ""  # message_id 为空字符串