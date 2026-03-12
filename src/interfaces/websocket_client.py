
# 导入统一异常（如果可用）
try:
    from src.exceptions import BaseAppError, handle_exception
    HAS_NEW_EXCEPTIONS = True
except ImportError:
    HAS_NEW_EXCEPTIONS = False


"""
WebSocket客户端接口定义
"""
# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

import asyncio
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any, List

# 导入类型定义
from src.interfaces.websocket_types import (
    WebSocketStatus,
    EventType,
    WebSocketEvent,
)

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class IWebSocketClient(ABC):
    """WebSocket客户端接口"""

    @abstractmethod
    async def connect(self) -> bool:
        """建立WebSocket连接"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """断开WebSocket连接"""
        pass

    @abstractmethod
    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息"""
        pass

    @abstractmethod
    def register_handler(self, event_type: EventType, handler: Callable[[WebSocketEvent], None]):
        """注册事件处理器"""
        pass

    @abstractmethod
    def unregister_handler(self, event_type: EventType, handler: Callable[[WebSocketEvent], None]):
        """注销事件处理器"""
        pass

    @abstractmethod
    def get_status(self) -> WebSocketStatus:
        """获取连接状态"""
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """检查是否已连接"""
        pass


# 导入 Mock 客户端
from src.interfaces.mock_websocket_client import MockWebSocketClient


class WebSocketClient(IWebSocketClient):
    """WebSocket客户端实现"""

    def __init__(self, app_id: str, app_secret: str, verification_token: str, ws_url: Optional[str] = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self.verification_token = verification_token
        self.ws_url = ws_url or f"wss://open.feishu.cn/open-apis/ws/v4/app/{app_id}/subscription"

        self._ws = None
        self._status = WebSocketStatus.DISCONNECTED
        self._handlers: Dict[EventType, List[Callable[[WebSocketEvent], None]]] = {}
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 10
        self._reconnect_base_delay = 1  # 基础重连延迟（秒）
        self._max_reconnect_delay = 60  # 最大重连延迟（秒）
        self._is_running = False
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def connect(self) -> bool:
        """建立WebSocket连接"""
        if self._status == WebSocketStatus.CONNECTED:
            return True

        self._status = WebSocketStatus.CONNECTING
        logger.info(f"Connecting to WebSocket: {self.ws_url}")

        try:
            # 获取访问令牌
            await self._refresh_access_token()

            # 创建WebSocket连接
            try:
                import websockets
            except ImportError:
                logger.warning("websockets not installed, using mock for testing")
                websockets = None

            # 设置连接头
            headers = {
                "Authorization": f"Bearer {self._access_token}",
                "User-Agent": "larkode-client"
            }

            # 连接WebSocket
            if websockets is not None:
                self._ws = await websockets.connect(
                    self.ws_url,
                    headers=headers,
                    ping_interval=30,
                    ping_timeout=10,
                    close_timeout=1
                )
            else:
                # 模拟WebSocket连接（用于测试）
                self._ws = None

            # 启动消息接收协程
            self._is_running = True
            asyncio.create_task(self._receive_messages())
            asyncio.create_task(self._heartbeat())

            self._status = WebSocketStatus.CONNECTED
            self._reconnect_attempts = 0

            # 发送连接成功事件
            self._emit_event(EventType.CONNECT, {
                "url": self.ws_url,
                "timestamp": datetime.now().isoformat()
            })

            logger.info("WebSocket connected successfully")
            return True

        except Exception as e:
            self._status = WebSocketStatus.FAILED
            logger.error(f"Failed to connect to WebSocket: {e}", exc_info=True)
            self._emit_event(EventType.ERROR, {"error": str(e)})
            return False

    async def disconnect(self) -> bool:
        """断开WebSocket连接"""
        if self._ws is None or self._status == WebSocketStatus.DISCONNECTED:
            return True

        self._is_running = False

        try:
            await self._ws.close()
            self._ws = None
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}", exc_info=True)

        self._status = WebSocketStatus.DISCONNECTED

        # 发送断开事件
        self._emit_event(EventType.DISCONNECT, {
            "timestamp": datetime.now().isoformat()
        })

        logger.info("WebSocket disconnected")
        return True

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """发送消息"""
        if not self.is_connected() or self._ws is None:
            return False

        try:
            # 序列化消息
            message_str = json.dumps(message)

            # 发送消息
            await self._ws.send(message_str)

            logger.debug(f"Sent message: {message}")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}", exc_info=True)
            return False

    def register_handler(self, event_type: EventType, handler: Callable[[WebSocketEvent], None]):
        """注册事件处理器"""
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def unregister_handler(self, event_type: EventType, handler: Callable[[WebSocketEvent], None]):
        """注销事件处理器"""
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
            except ValueError:
                pass

    def get_status(self) -> WebSocketStatus:
        """获取连接状态"""
        return self._status

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._status == WebSocketStatus.CONNECTED

    async def _refresh_access_token(self) -> bool:
        """刷新访问令牌"""
        try:
            # 模拟获取访问令牌（实际实现需要调用飞书API）
            await asyncio.sleep(0.1)  # 模拟网络延迟

            # 设置模拟的访问令牌和过期时间
            import uuid
            self._access_token = f"mock_token_{uuid.uuid4().hex[:8]}"
            self._token_expires_at = datetime.now() + timedelta(hours=1)

            logger.info("Access token refreshed")
            return True

        except Exception as e:
            logger.error(f"Failed to refresh access token: {e}", exc_info=True)
            return False

    async def _check_token_expiry(self):
        """检查令牌是否过期"""
        if self._token_expires_at and datetime.now() >= self._token_expires_at:
            logger.info("Access token expired, refreshing...")
            await self._refresh_access_token()

    async def _receive_messages(self):
        """接收消息"""
        while self._is_running and self._ws:
            try:
                message = await self._ws.recv()
                data = json.loads(message)

                # 检查令牌过期
                await self._check_token_expiry()

                # 处理消息
                self._emit_event(EventType.MESSAGE, {
                    "message": data,
                    "timestamp": datetime.now().isoformat()
                })

            except Exception as e:
                if "ConnectionClosed" in str(type(e)) or "closed" in str(e).lower():
                    logger.warning("WebSocket connection closed")
                    await self._handle_connection_lost()
                    break
                else:
                    logger.error(f"Error receiving message: {e}", exc_info=True)
                    break
            except Exception as e:
                logger.error(f"Error receiving message: {e}", exc_info=True)
                break

    async def _heartbeat(self):
        """心跳检测"""
        while self._is_running and self._ws and self.is_connected():
            try:
                if hasattr(self._ws, 'ping'):
                    await self._ws.ping()
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Heartbeat failed: {e}", exc_info=True)
                await self._handle_connection_lost()
                break

    async def _handle_connection_lost(self):
        """处理连接丢失"""
        self._status = WebSocketStatus.DISCONNECTED

        # 发送断开事件
        self._emit_event(EventType.DISCONNECT, {
            "timestamp": datetime.now().isoformat()
        })

        # 尝试重连
        if self._reconnect_attempts < self._max_reconnect_attempts:
            self._status = WebSocketStatus.RECONNECTING
            self._reconnect_attempts += 1

            # 计算重连延迟（指数退避）
            delay = min(
                self._reconnect_base_delay * (2 ** (self._reconnect_attempts - 1)),
                self._max_reconnect_delay
            )

            logger.info(f"Connection lost. Attempting to reconnect in {delay} seconds (attempt {self._reconnect_attempts}/{self._max_reconnect_attempts})")

            self._emit_event(EventType.RECONNECT, {
                "attempt": self._reconnect_attempts,
                "max_attempts": self._max_reconnect_attempts,
                "delay": delay,
                "timestamp": datetime.now().isoformat()
            })

            await asyncio.sleep(delay)

            # 尝试重新连接
            await self.connect()
        else:
            logger.error("Max reconnection attempts reached. Giving up.")
            self._status = WebSocketStatus.FAILED

    def _emit_event(self, event_type: EventType, data: Any):
        """发射事件"""
        event = WebSocketEvent(event_type, data)

        # 通知所有注册的处理器
        if event_type in self._handlers:
            for handler in self._handlers[event_type]:
                try:
                    # 调用安全处理器
                    self._safe_call_handler(handler, event)
                except Exception as e:
                    logger.error(f"Error in event handler: {e}", exc_info=True)

    def _safe_call_handler(self, handler, event: WebSocketEvent):
        """安全调用处理器"""
        if asyncio.iscoroutinefunction(handler):
            # 异步处理器使用create_task
            asyncio.create_task(handler(event))
        else:
            # 同步处理器直接调用
            handler(event)
