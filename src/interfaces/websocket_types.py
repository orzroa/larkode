"""
WebSocket 类型定义

包含枚举和事件类
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class WebSocketStatus(str, Enum):
    """WebSocket连接状态"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class EventType(str, Enum):
    """事件类型"""
    MESSAGE = "message"
    ERROR = "error"
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    RECONNECT = "reconnect"


class WebSocketEvent:
    """WebSocket事件"""

    def __init__(self, event_type: EventType, data: Any, timestamp: Optional[datetime] = None):
        self.event_type = event_type
        self.data = data
        self.timestamp = timestamp or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }
