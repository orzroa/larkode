"""
模拟 WebSocket 客户端

用于测试
"""
import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from src.interfaces.websocket_types import EventType, WebSocketEvent, WebSocketStatus

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class MockWebSocketClient:
    """模拟WebSocket客户端"""

    def __init__(self, name: str = "mock_client"):
        self.name = name
        self.status = WebSocketStatus.DISCONNECTED
        self._message_queue = asyncio.Queue()
        self._handlers: Dict[EventType, List[Callable[[WebSocketEvent], None]]] = {}
        self._closed = False
        self._connect_delay = 0.1  # 模拟连接延迟
        self._send_delay = 0.05    # 模拟发送延迟

    async def connect(self) -> bool:
        """模拟建立WebSocket连接"""
        if self._closed:
            return False

        self.status = WebSocketStatus.CONNECTING
        await asyncio.sleep(self._connect_delay)

        # 模拟连接成功
        self.status = WebSocketStatus.CONNECTED
        self._emit_event(EventType.CONNECT, {"client": self.name})

        # 启动消息处理协程
        asyncio.create_task(self._process_messages())

        logger.info(f"{self.name} connected successfully")
        return True

    async def disconnect(self) -> bool:
        """模拟断开WebSocket连接"""
        if self.status == WebSocketStatus.DISCONNECTED:
            return True

        self._closed = True
        self.status = WebSocketStatus.DISCONNECTED

        # 发送断开事件
        self._emit_event(EventType.DISCONNECT, {"client": self.name})

        logger.info(f"{self.name} disconnected")
        return True

    async def send_message(self, message: Dict[str, Any]) -> bool:
        """模拟发送消息"""
        if not self.is_connected():
            return False

        # 模拟发送延迟
        await asyncio.sleep(self._send_delay)

        # 模拟消息处理
        await self._message_queue.put(message)
        logger.debug(f"{self.name} sent message: {message}")
        return True

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
        return self.status

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.status == WebSocketStatus.CONNECTED

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

    async def _process_messages(self):
        """处理消息队列"""
        while not self._closed and self.is_connected():
            try:
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)

                # 模拟接收到消息事件
                self._emit_event(EventType.MESSAGE, {
                    "message": message,
                    "timestamp": datetime.now().isoformat()
                })

            except asyncio.TimeoutError:
                continue

    def simulate_message(self, message: Dict[str, Any]):
        """模拟接收消息（测试用）"""
        if not self._closed and self.is_connected():
            self._message_queue.put_nowait(message)

    def simulate_disconnect(self):
        """模拟断开连接（测试用）"""
        self.status = WebSocketStatus.DISCONNECTED
        self._emit_event(EventType.DISCONNECT, {"client": self.name})

    def simulate_error(self, error: str):
        """模拟错误（测试用）"""
        self._emit_event(EventType.ERROR, {"error": error})
