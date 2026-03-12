"""
本地 HTTP API 服务器

用于集成测试：通过 HTTP 接口模拟接收消息事件
"""
import asyncio
import json
import os
from typing import Optional, Dict, Any
from aiohttp import web

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class APIServer:
    """HTTP API 服务器"""

    def __init__(self, host: str = "127.0.0.1", port: int = 18080):
        self.host = host
        self.port = port
        self.app: Optional[web.Application] = None
        self.runner: Optional[web.AppRunner] = None
        self.site: Optional[web.TCPSite] = None

        # 消息处理器（通过 set_handler 设置）
        self._message_handler = None

    def set_message_handler(self, handler):
        """设置消息处理器"""
        self._message_handler = handler

    def _setup_routes(self):
        """设置路由"""
        self.app.router.add_post("/api/test-command", self.handle_test_command)
        self.app.router.add_post("/api/simulate-message", self.handle_simulate_message)
        self.app.router.add_get("/api/health", self.handle_health)
        self.app.router.add_get("/api/status", self.handle_status)

    async def handle_health(self, request: web.Request) -> web.Response:
        """健康检查端点"""
        return web.json_response({"status": "ok"})

    async def handle_status(self, request: web.Request) -> web.Response:
        """状态查询端点"""
        return web.json_response({
            "status": "running",
            "message_handler": "attached" if self._message_handler else "not_attached"
        })

    async def handle_test_command(self, request: web.Request) -> web.Response:
        """
        测试命令端点 - 模拟接收消息

        请求体:
        {
            "user_id": "ou_xxx",
            "command": "#help",
            "is_test": true  // 可选，默认 true
        }
        """
        try:
            data = await request.json()
            user_id = data.get("user_id")
            command = data.get("command")
            is_test = data.get("is_test", True)  # 默认测试模式

            if not user_id or not command:
                return web.json_response(
                    {"error": "user_id and command are required"},
                    status=400
                )

            logger.info(f"收到测试命令请求: user_id={user_id}, command={command}, is_test={is_test}")

            # 构造飞书事件格式
            event_data = {
                "type": "im.message.receive_v1",
                "event": {
                    "message": {
                        "message_id": f"om_{user_id}_{command[:10]}",
                        "msg_type": "text",
                        "content": json.dumps({"text": command})
                    },
                    "sender": {
                        "sender_id": {
                            "open_id": user_id
                        }
                    }
                },
                "is_test": is_test
            }

            # 调用消息处理器
            if self._message_handler:
                await self._message_handler.handle_event(event_data)
                return web.json_response({"status": "processed", "user_id": user_id, "command": command})
            else:
                return web.json_response(
                    {"error": "message handler not attached"},
                    status=500
                )

        except json.JSONDecodeError:
            return web.json_response({"error": "invalid json"}, status=400)
        except Exception as e:
            logger.error(f"处理测试命令时出错: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def handle_simulate_message(self, request: web.Request) -> web.Response:
        """
        模拟消息端点 - 直接传入完整事件数据

        请求体:
        {
            "event": { ... }
        }
        """
        try:
            data = await request.json()
            event_data = data.get("event")

            if not event_data:
                return web.json_response(
                    {"error": "event is required"},
                    status=400
                )

            logger.info(f"收到模拟消息请求: {event_data.get('type', 'unknown')}")

            # 调用消息处理器
            if self._message_handler:
                await self._message_handler.handle_event(event_data)
                return web.json_response({"status": "processed"})
            else:
                return web.json_response(
                    {"error": "message handler not attached"},
                    status=500
                )

        except Exception as e:
            logger.error(f"处理模拟消息时出错: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)

    async def start(self):
        """启动 API 服务器"""
        self.app = web.Application()
        self._setup_routes()

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()

        self.site = web.TCPSite(self.runner, self.host, self.port)
        await self.site.start()

        logger.info(f"API 服务器已启动: http://{self.host}:{self.port}")

    async def stop(self):
        """停止 API 服务器"""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("API 服务器已停止")


# 全局 API 服务器实例
_api_server: Optional[APIServer] = None


def get_api_server() -> APIServer:
    """获取全局 API 服务器实例"""
    global _api_server
    if _api_server is None:
        port = int(os.getenv("API_SERVER_PORT", "18080"))
        host = os.getenv("API_SERVER_HOST", "127.0.0.1")
        _api_server = APIServer(host=host, port=port)
    return _api_server


async def start_api_server(message_handler=None):
    """启动 API 服务器（便捷函数）"""
    server = get_api_server()
    if message_handler:
        server.set_message_handler(message_handler)
    await server.start()
    return server
