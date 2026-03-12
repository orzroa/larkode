"""
飞书 WebSocket 客户端
"""
from typing import Dict, Any

from src.interfaces.websocket_client import WebSocketClient, EventType

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class FeishuWebSocketClient:
    """飞书 WebSocket 客户端"""

    def __init__(self, app_id: str, app_secret: str, verification_token: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.client = WebSocketClient(app_id, app_secret, verification_token)

    async def connect(self):
        """连接到飞书WebSocket"""
        return await self.client.connect()

    async def disconnect(self):
        """断开连接"""
        return await self.client.disconnect()

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息"""
        return await self.client.send_message(message)

    def register_handler(self, event_type: EventType, handler):
        """注册事件处理器"""
        return self.client.register_handler(event_type, handler)

    def unregister_handler(self, event_type: EventType, handler):
        """注销事件处理器"""
        return self.client.unregister_handler(event_type, handler)

    def get_status(self):
        """获取连接状态"""
        return self.client.get_status()

    def is_connected(self):
        """检查是否已连接"""
        return self.client.is_connected()
