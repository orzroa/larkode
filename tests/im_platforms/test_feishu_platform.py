"""
测试飞书平台实现
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestFeishuPlatformInit:
    """测试 FeishuPlatform 初始化"""

    @pytest.fixture
    def platform_config(self):
        """创建平台配置"""
        from src.interfaces.im_platform import PlatformConfig
        return PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

    def test_init(self, platform_config):
        """测试初始化"""
        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(platform_config)

            assert platform.config == platform_config
            assert platform._domain == "https://open.feishu.cn"
            assert platform._receive_id_type == "open_id"
            assert platform._ws_client is None

    def test_verification_token_from_config(self, platform_config):
        """测试从配置获取验证令牌"""
        platform_config.extra = {"verification_token": "test_token"}

        with patch('src.im_platforms.feishu.FeishuAPI'):
            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(platform_config)

            assert platform.verification_token == "test_token"

    def test_verification_token_none(self, platform_config):
        """测试没有验证令牌"""
        with patch('src.im_platforms.feishu.FeishuAPI'):
            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(platform_config)

            assert platform.verification_token is None


class TestGetWebSocketClient:
    """测试 get_websocket_client 方法"""

    @pytest.fixture
    def platform_config(self):
        """创建平台配置"""
        from src.interfaces.im_platform import PlatformConfig
        return PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

    def test_get_websocket_client_creates_instance(self, platform_config):
        """测试首次获取创建客户端"""
        with patch('src.im_platforms.feishu.FeishuAPI'):
            with patch('src.im_platforms.feishu.FeishuWebSocketClient') as mock_ws:
                mock_ws_instance = Mock()
                mock_ws.return_value = mock_ws_instance

                from src.im_platforms.feishu import FeishuPlatform
                platform = FeishuPlatform(platform_config)

                result = platform.get_websocket_client()

                assert result == mock_ws_instance
                mock_ws.assert_called_once()

    def test_get_websocket_client_reuses_instance(self, platform_config):
        """测试重复获取复用客户端"""
        with patch('src.im_platforms.feishu.FeishuAPI'):
            with patch('src.im_platforms.feishu.FeishuWebSocketClient') as mock_ws:
                mock_ws_instance = Mock()
                mock_ws.return_value = mock_ws_instance

                from src.im_platforms.feishu import FeishuPlatform
                platform = FeishuPlatform(platform_config)

                result1 = platform.get_websocket_client()
                result2 = platform.get_websocket_client()

                assert result1 == result2
                mock_ws.assert_called_once()


class TestSendMessage:
    """测试 send_message 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            mock_api_instance = Mock()
            mock_api_instance.send_message = AsyncMock(return_value=True)
            mock_api.return_value = mock_api_instance

            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            platform.api = mock_api_instance
            return platform

    @pytest.mark.asyncio
    async def test_send_message_success(self, platform):
        """测试成功发送消息"""
        from src.interfaces.im_platform import MessageType

        result = await platform.send_message("user_123", "test message", MessageType.TEXT)

        assert result is True
        platform.api.send_message.assert_called_once_with("user_123", "test message")

    @pytest.mark.asyncio
    async def test_send_message_exception(self, platform):
        """测试发送消息异常"""
        platform.api.send_message = AsyncMock(side_effect=Exception("API error"))

        result = await platform.send_message("user_123", "test message")

        assert result is False


class TestSendCard:
    """测试 send_card 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            mock_api_instance = Mock()
            mock_api_instance.send_message = AsyncMock(return_value=True)
            mock_api.return_value = mock_api_instance

            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            platform.api = mock_api_instance
            return platform

    @pytest.mark.asyncio
    async def test_send_card_success(self, platform):
        """测试成功发送卡片"""
        from src.interfaces.im_platform import NormalizedCard

        card = NormalizedCard(
            card_type="test",
            title="Test Card",
            content="Test content",
            template_color="blue"
        )

        result = await platform.send_card("user_123", card)

        assert result is True
        platform.api.send_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_card_exception(self, platform):
        """测试发送卡片异常"""
        from src.interfaces.im_platform import NormalizedCard

        platform.api.send_message = AsyncMock(side_effect=Exception("API error"))

        card = NormalizedCard(
            card_type="test",
            title="Test Card",
            content="Test content",
            template_color="blue"
        )

        result = await platform.send_card("user_123", card)

        assert result is False


class TestSendFile:
    """测试 send_file 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            mock_api_instance = Mock()
            mock_api_instance.send_file_message = AsyncMock(return_value=True)
            mock_api.return_value = mock_api_instance

            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            platform.api = mock_api_instance
            return platform

    @pytest.mark.asyncio
    async def test_send_file_success(self, platform):
        """测试成功发送文件"""
        result = await platform.send_file("user_123", "file_key_123")

        assert result is True
        platform.api.send_file_message.assert_called_once_with("user_123", "file_key_123")

    @pytest.mark.asyncio
    async def test_send_file_exception(self, platform):
        """测试发送文件异常"""
        platform.api.send_file_message = AsyncMock(side_effect=Exception("API error"))

        result = await platform.send_file("user_123", "file_key_123")

        assert result is False


class TestDownloadFile:
    """测试 download_file 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            mock_api_instance = Mock()
            mock_api_instance.download_file = AsyncMock(return_value=Path("/tmp/test.txt"))
            mock_api.return_value = mock_api_instance

            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            platform.api = mock_api_instance
            return platform

    @pytest.mark.asyncio
    async def test_download_file_success(self, platform):
        """测试成功下载文件"""
        result = await platform.download_file("msg_123", "file_key_123")

        assert result == Path("/tmp/test.txt")
        platform.api.download_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_download_file_exception(self, platform):
        """测试下载文件异常"""
        platform.api.download_file = AsyncMock(side_effect=Exception("API error"))

        result = await platform.download_file("msg_123", "file_key_123")

        assert result is None


class TestGetUserInfo:
    """测试 get_user_info 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            mock_api_instance = Mock()
            mock_api_instance.get_user_info = AsyncMock(return_value={
                "user_id": "user_123",
                "name": "Test User",
                "avatar": "https://example.com/avatar.png"
            })
            mock_api.return_value = mock_api_instance

            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            platform.api = mock_api_instance
            return platform

    @pytest.mark.asyncio
    async def test_get_user_info_success(self, platform):
        """测试成功获取用户信息"""
        result = await platform.get_user_info("user_123")

        assert result is not None
        assert result.user_id == "user_123"
        assert result.name == "Test User"
        assert result.avatar == "https://example.com/avatar.png"

    @pytest.mark.asyncio
    async def test_get_user_info_none(self, platform):
        """测试用户信息为空"""
        platform.api.get_user_info = AsyncMock(return_value=None)

        result = await platform.get_user_info("user_123")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_info_exception(self, platform):
        """测试获取用户信息异常"""
        platform.api.get_user_info = AsyncMock(side_effect=Exception("API error"))

        result = await platform.get_user_info("user_123")

        assert result is None


class TestUploadFile:
    """测试 upload_file 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI') as mock_api:
            mock_api_instance = Mock()
            mock_api_instance.upload_file = AsyncMock(return_value="file_key_123")
            mock_api.return_value = mock_api_instance

            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            platform.api = mock_api_instance
            return platform

    @pytest.mark.asyncio
    async def test_upload_file_success(self, platform):
        """测试成功上传文件"""
        result = await platform.upload_file(Path("/tmp/test.txt"))

        assert result == "file_key_123"
        platform.api.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_file_exception(self, platform):
        """测试上传文件异常"""
        platform.api.upload_file = AsyncMock(side_effect=Exception("API error"))

        result = await platform.upload_file(Path("/tmp/test.txt"))

        assert result is None


class TestParseEvent:
    """测试 parse_event 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI'):
            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            return platform

    def test_parse_event_text_message(self, platform):
        """测试解析文本消息"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "text",
                    "content": '{"text": "Hello"}',
                    "create_time": "2024-01-01T00:00:00"
                }
            }
        }

        result = platform.parse_event(event_data)

        assert result is not None
        assert result.user_id == "user_123"
        assert result.message_id == "msg_123"
        assert result.content == "Hello"
        from src.interfaces.im_platform import MessageType
        assert result.message_type == MessageType.TEXT

    def test_parse_event_image_message(self, platform):
        """测试解析图片消息"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "image",
                    "content": '{"image_key": "img_123"}'
                }
            }
        }

        result = platform.parse_event(event_data)

        assert result is not None
        from src.interfaces.im_platform import MessageType
        assert result.message_type == MessageType.IMAGE
        assert len(result.attachments) == 1
        assert result.attachments[0]["image_key"] == "img_123"

    def test_parse_event_file_message(self, platform):
        """测试解析文件消息"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "file",
                    "content": '{"file_key": "file_123"}'
                }
            }
        }

        result = platform.parse_event(event_data)

        assert result is not None
        from src.interfaces.im_platform import MessageType
        assert result.message_type == MessageType.FILE
        assert len(result.attachments) == 1
        assert result.attachments[0]["file_key"] == "file_123"

    def test_parse_event_audio_message(self, platform):
        """测试解析语音消息"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "audio",
                    "content": '{"file_key": "audio_123"}'
                }
            }
        }

        result = platform.parse_event(event_data)

        assert result is not None
        from src.interfaces.im_platform import MessageType
        assert result.message_type == MessageType.VOICE
        assert len(result.attachments) == 1
        assert result.attachments[0]["file_key"] == "audio_123"

    def test_parse_event_interactive_message(self, platform):
        """测试解析交互消息"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "interactive",
                    "content": '{"text": "Interaction text"}'
                }
            }
        }

        result = platform.parse_event(event_data)

        assert result is not None
        from src.interfaces.im_platform import MessageType
        assert result.message_type == MessageType.INTERACTION
        assert result.content == "Interaction text"

    def test_parse_event_incomplete_data(self, platform):
        """测试数据不完整"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {},
                "message": {}
            }
        }

        result = platform.parse_event(event_data)

        assert result is None

    def test_parse_event_unknown_type(self, platform):
        """测试未知事件类型"""
        event_data = {
            "type": "unknown.event"
        }

        result = platform.parse_event(event_data)

        assert result is None

    def test_parse_event_message_read(self, platform):
        """测试消息已读事件"""
        event_data = {
            "type": "im.message.message_read_v1"
        }

        result = platform.parse_event(event_data)

        assert result is None

    def test_parse_event_card_action(self, platform):
        """测试卡片按钮点击事件"""
        event_data = {
            "type": "card.action.trigger"
        }

        result = platform.parse_event(event_data)

        assert result is None

    def test_parse_event_exception(self, platform):
        """测试解析异常"""
        event_data = {
            "type": "im.message.receive_v1",
            "event": {
                "sender": {
                    "sender_id": {"open_id": "user_123"}
                },
                "message": {
                    "message_id": "msg_123",
                    "msg_type": "text",
                    "content": "invalid json"
                }
            }
        }

        result = platform.parse_event(event_data)

        assert result is None


class TestIsPlatformCommand:
    """测试 is_platform_command 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI'):
            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            return platform

    def test_is_platform_command_true(self, platform):
        """测试是平台命令"""
        assert platform.is_platform_command("#help") is True
        assert platform.is_platform_command(" #cancel") is True
        assert platform.is_platform_command("#history") is True

    def test_is_platform_command_false(self, platform):
        """测试不是平台命令"""
        assert platform.is_platform_command("help") is False
        assert platform.is_platform_command("write a function") is False
        assert platform.is_platform_command("") is False


class TestConvertNormalizedCardToFeishu:
    """测试 _convert_normalized_card_to_feishu 方法"""

    @pytest.fixture
    def platform(self):
        """创建平台实例"""
        from src.interfaces.im_platform import PlatformConfig
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret",
            domain="https://open.feishu.cn",
            receive_id_type="open_id"
        )

        with patch('src.im_platforms.feishu.FeishuAPI'):
            from src.im_platforms.feishu import FeishuPlatform
            platform = FeishuPlatform(config)
            return platform

    def test_convert_card(self, platform):
        """测试转换卡片"""
        from src.interfaces.im_platform import NormalizedCard

        card = NormalizedCard(
            card_type="test",
            title="Test Title",
            content="Test content",
            template_color="blue"
        )

        result = platform._convert_normalized_card_to_feishu(card)

        # 验证是 JSON 字符串
        parsed = json.loads(result)
        assert parsed["schema"] == "2.0"
        assert parsed["header"]["title"]["content"] == "Test Title"
        assert parsed["header"]["template"] == "blue"
        assert len(parsed["body"]["elements"]) == 1


class TestFeishuCardBuilder:
    """测试 FeishuCardBuilder"""

    def test_create_command_card(self):
        """测试创建命令卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_command_card("test command")

        assert card.card_type == "command"
        assert card.title == "命令确认"
        assert "test command" in card.content
        assert card.template_color == "grey"

    def test_create_output_card(self):
        """测试创建输出卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_output_card("test output", "Test Title")

        assert card.card_type == "output"
        assert card.title == "Test Title"
        assert "test output" in card.content

    def test_create_error_card(self):
        """测试创建错误卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_error_card("test error")

        assert card.card_type == "error"
        assert card.title == "错误"
        assert "test error" in card.content
        assert card.template_color == "red"

    def test_create_help_card(self):
        """测试创建帮助卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_help_card("Help text")

        assert card.card_type == "help"
        assert card.title == "帮助"
        assert "Help text" in card.content

    def test_create_history_card(self):
        """测试创建历史卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_history_card("History text")

        assert card.card_type == "history"
        assert card.title == "历史记录"
        assert "History text" in card.content

    def test_create_cancel_card(self):
        """测试创建取消卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_cancel_card("Cancelled")

        assert card.card_type == "cancel"
        assert card.title == "取消"
        assert "Cancelled" in card.content

    def test_create_download_image_card(self):
        """测试创建下载图片卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_download_image_card("Image downloaded")

        assert card.card_type == "download_image"
        assert card.title == "下载图片"
        assert "Image downloaded" in card.content

    def test_create_download_voice_card(self):
        """测试创建下载语音卡片"""
        from src.im_platforms.feishu import FeishuCardBuilder

        card = FeishuCardBuilder.create_download_voice_card("Voice downloaded")

        assert card.card_type == "download_voice"
        assert card.title == "下载语音"
        assert "Voice downloaded" in card.content


class TestRegisterFeishuPlatform:
    """测试 register_feishu_platform 函数"""

    def test_register_feishu_platform(self):
        """测试注册飞书平台"""
        with patch('src.factories.platform_factory.IMPlatformFactory') as mock_factory:
            from src.im_platforms.feishu import register_feishu_platform

            register_feishu_platform()

            mock_factory.register_platform.assert_called_once()