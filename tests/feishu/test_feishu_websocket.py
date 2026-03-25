"""
测试 feishu/websocket.py
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.interfaces.websocket_client import EventType


class TestFeishuWebSocket:
    """测试飞书 WebSocket 客户端"""

    @pytest.fixture
    def mock_ws_client(self):
        """模拟 WebSocketClient"""
        mock = MagicMock()
        mock.connect = AsyncMock(return_value=True)
        mock.disconnect = AsyncMock(return_value=True)
        mock.send_message = AsyncMock(return_value=True)
        mock.register_handler = MagicMock()
        mock.unregister_handler = MagicMock()
        mock.get_status = MagicMock(return_value="connected")
        mock.is_connected = MagicMock(return_value=True)
        return mock

    @pytest.fixture
    def feishu_ws(self, mock_ws_client):
        """创建 FeishuWebSocketClient 实例"""
        with patch('src.feishu.websocket.WebSocketClient', return_value=mock_ws_client):
            from src.feishu.websocket import FeishuWebSocketClient
            return FeishuWebSocketClient("app_id", "app_secret", "token")

    def test_init(self, feishu_ws):
        """测试初始化"""
        assert feishu_ws.app_id == "app_id"
        assert feishu_ws.app_secret == "app_secret"
        assert feishu_ws.verification_token == "token"

    @pytest.mark.asyncio
    async def test_connect(self, feishu_ws, mock_ws_client):
        """测试连接"""
        result = await feishu_ws.connect()
        mock_ws_client.connect.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_disconnect(self, feishu_ws, mock_ws_client):
        """测试断开连接"""
        result = await feishu_ws.disconnect()
        mock_ws_client.disconnect.assert_called_once()
        assert result is True

    @pytest.mark.asyncio
    async def test_send_message(self, feishu_ws, mock_ws_client):
        """测试发送消息"""
        msg = {"test": "data"}
        result = await feishu_ws.send_message(msg)
        mock_ws_client.send_message.assert_called_once_with(msg)
        assert result is True

    def test_register_handler(self, feishu_ws, mock_ws_client):
        """测试注册处理器"""
        handler = MagicMock()
        feishu_ws.register_handler(EventType.MESSAGE, handler)
        mock_ws_client.register_handler.assert_called_once_with(EventType.MESSAGE, handler)

    def test_unregister_handler(self, feishu_ws, mock_ws_client):
        """测试注销处理器"""
        handler = MagicMock()
        feishu_ws.unregister_handler(EventType.MESSAGE, handler)
        mock_ws_client.unregister_handler.assert_called_once_with(EventType.MESSAGE, handler)

    def test_get_status(self, feishu_ws, mock_ws_client):
        """测试获取状态"""
        status = feishu_ws.get_status()
        mock_ws_client.get_status.assert_called_once()
        assert status == "connected"

    def test_is_connected(self, feishu_ws, mock_ws_client):
        """测试检查是否连接"""
        result = feishu_ws.is_connected()
        mock_ws_client.is_connected.assert_called_once()
        assert result is True


def test_logging_fallback():
    """测试日志 fallback"""
    import sys
    import importlib

    for mod in ['src.feishu.websocket', 'src.logging_utils']:
        if mod in sys.modules:
            del sys.modules[mod]

    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == 'src.logging_utils':
            raise ImportError("not available")
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=mock_import):
        import src.feishu.websocket
        importlib.reload(src.feishu.websocket)
        assert hasattr(src.feishu.websocket, 'logger')