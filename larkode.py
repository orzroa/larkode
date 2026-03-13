#!/usr/bin/env -S uv run --no-project
# /// script
# dependencies = [
#   "lark-oapi>=1.5.3",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.5.3",
#   "pydantic-settings>=2.0.0",
#   "psutil>=5.9.0",
#   "aiohttp>=3.8.0",
#   "pytest-asyncio>=0.21.0"
# ]
# ///
"""
Larkode - 飞书 AI 助手集成
主入口

依赖 (使用 uv 管理):
    uv pip install -r requirements.txt --system
    或者直接运行: uv run --no-project ai_term_lark.py

外部依赖:
    - Claude Code CLI: npm install -g @anthropic-ai/claude-code
"""
import asyncio
import json
import logging
import os
import signal
import sys
import threading
from pathlib import Path

import lark_oapi as lark

from src.config.settings import get_settings
from src.task_manager import task_manager
from src.message_handler import message_handler
from src.feishu import FeishuAPI
from src.ai_session_manager import session_manager
from src.interaction_manager import interaction_manager, set_interaction_response_file_path
from src.im_platforms.multi_platform_manager import MultiPlatformManager
from src.im_platforms.notification_sender import (
    StaticNotificationSender,
    DynamicBroadcastSender,
)
from src.factories.platform_factory import IMPlatformFactory
from src.interfaces.im_platform import PlatformConfig
from src.handlers.event_handlers import create_event_handlers
from src.handlers.interaction_monitor import InteractionMonitor
from src.api_server import get_api_server

# 配置日志 - 优先使用新的日志系统
try:
    from src.logging_utils import setup_logging
    # 可选：启用结构化日志 (use_structured=True)
    # 默认使用标准格式保持向后兼容
    setup_logging(
        log_dir=get_settings().LOG_DIR,
        log_level=get_settings().LOG_LEVEL,
        use_structured=False,  # 可改为 True 启用 JSON 格式
    )
    print("✅ 使用新的日志配置系统")
except ImportError:
    # 回退到旧配置
    logging.basicConfig(
        level=getattr(logging, get_settings().LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(get_settings().LOG_DIR / 'app.log'),
            logging.StreamHandler()
        ]
    )

logger = logging.getLogger(__name__)

# 全局变量
feishu_api_instance = None
multi_platform_manager = None  # 多平台管理器实例

# 交互文件路径
INTERACTION_REQUEST_FILE = get_settings().LOG_DIR / "interaction_request.json"
INTERACTION_RESPONSE_FILE = get_settings().LOG_DIR / "interaction_response.json"


class ClaudeFeishuService:
    """Claude Feishu 服务"""

    def __init__(self):
        global feishu_api_instance, multi_platform_manager
        feishu_api_instance = FeishuAPI(get_settings().FEISHU_APP_ID, get_settings().FEISHU_APP_SECRET)
        self._shutdown_event = asyncio.Event()
        self._ws_clients = {}  # platform_name -> ws_client
        self._ws_threads = {}  # platform_name -> ws_thread
        self._multi_platform_manager = MultiPlatformManager()
        multi_platform_manager = self._multi_platform_manager
        self._tasks: list[asyncio.Task] = []
        self._interaction_monitor_task: asyncio.Task = None

        # 创建事件处理器
        self._do_p2_im_message_receive_v1, self._do_p2_card_action_trigger = create_event_handlers(
            interaction_manager, feishu_api_instance
        )

        # 创建交互监控器
        self._interaction_monitor = InteractionMonitor(interaction_manager)

    async def _initialize_multi_platform(self):
        """初始化多平台支持"""
        # 注册所有平台到工厂
        self._register_all_platforms()

        # 获取启用的平台列表
        enabled_platforms = get_settings().get_enabled_platforms()
        logger.info(f"启用的平台: {enabled_platforms}")

        # 创建平台实例并注册到多平台管理器
        for platform_name in enabled_platforms:
            await self._initialize_platform(platform_name)

        # 更新全局消息处理器，传入多平台管理器和广播发送器
        if enabled_platforms:
            broadcast_sender = DynamicBroadcastSender(self._multi_platform_manager)
            message_handler.set_notification_sender(broadcast_sender)
            logger.info("已启用多平台广播模式")
        else:
            logger.warning("未启用任何 IM 平台")

    def _register_all_platforms(self):
        """注册所有平台到工厂"""
        # 注册飞书平台
        if not IMPlatformFactory.is_platform_registered("feishu"):
            from src.im_platforms import register_feishu_platform
            register_feishu_platform()

        # 注册 Slack 平台（如果已实现）
        if get_settings().is_platform_enabled("slack"):
            try:
                from src.im_platforms import register_slack_platform
                if not IMPlatformFactory.is_platform_registered("slack"):
                    register_slack_platform()
            except ImportError:
                logger.warning("Slack 平台未实现，跳过注册")

        # 注册钉钉平台（如果已实现）
        if get_settings().is_platform_enabled("dingtalk"):
            try:
                from src.im_platforms import register_dingtalk_platform
                if not IMPlatformFactory.is_platform_registered("dingtalk"):
                    register_dingtalk_platform()
            except ImportError:
                logger.warning("钉钉平台未实现，跳过注册")

    async def _initialize_platform(self, platform_name: str):
        """
        初始化指定平台

        Args:
            platform_name: 平台名称
        """
        try:
            platform_config = get_settings().get_platform_config(platform_name)
            if not platform_config:
                logger.warning(f"平台 {platform_name} 配置缺失，跳过初始化")
                return

            # 创建平台配置对象
            if platform_name == "feishu":
                config = PlatformConfig(
                    app_id=platform_config["app_id"],
                    app_secret=platform_config["app_secret"],
                    domain=platform_config["message_domain"],
                    receive_id_type=platform_config["message_receive_id_type"],
                )
            elif platform_name == "slack":
                config = PlatformConfig(
                    app_id=platform_config["app_id"],
                    app_secret=platform_config["signing_secret"],
                    # Slack 可能需要不同的配置格式
                    bot_token=platform_config.get("bot_token", ""),
                )
            elif platform_name == "dingtalk":
                config = PlatformConfig(
                    app_id=platform_config["app_key"],
                    app_secret=platform_config["app_secret"],
                )
            else:
                logger.warning(f"未知的平台: {platform_name}")
                return

            # 创建平台实例
            platform = IMPlatformFactory.create_platform(platform_name, config)
            if platform:
                self._multi_platform_manager.register_platform(platform_name, platform)
                logger.info(f"平台 {platform_name} 已注册")

                # 获取 WebSocket 客户端（如果有）
                ws_client = platform.get_websocket_client()
                if ws_client:
                    self._ws_clients[platform_name] = {
                        "client": ws_client,
                        "platform": platform,
                    }
                    logger.info(f"平台 {platform_name} 的 WebSocket 客户端已准备好")
                else:
                    # 对于没有 WebSocket 的平台，标记为已连接
                    self._multi_platform_manager.set_connected_status(platform_name, True)
                    logger.info(f"平台 {platform_name} 不使用 WebSocket，已标记为已连接")

        except Exception as e:
            logger.error(f"初始化平台 {platform_name} 时出错: {e}", exc_info=True)

    def _create_static_notification_sender(self) -> StaticNotificationSender:
        """
        创建静态通知发送器（用于 Hooks）

        Returns:
            StaticNotificationSender 实例
        """
        # 使用配置的默认平台（通常是飞书）
        default_platform = self._multi_platform_manager.get_platform("feishu")
        if not default_platform:
            # 回退到使用全局 feishu_api_instance
            from src.im_platforms.feishu import FeishuPlatform
            feishu_platform = FeishuPlatform(get_settings().FEISHU_APP_ID, get_settings().FEISHU_APP_SECRET)
            return StaticNotificationSender(feishu_platform)

        return StaticNotificationSender(default_platform)

    async def start(self):
        """启动服务"""
        logger.info("Claude Feishu Integration 启动中...")

        # 设置交互响应文件路径
        set_interaction_response_file_path(INTERACTION_RESPONSE_FILE)

        # 初始化多平台支持
        await self._initialize_multi_platform()

        # 启动任务管理器
        await task_manager.start()
        logger.info("任务管理器已启动")

        # 为每个有 WebSocket 的平台启动客户端
        for platform_name, ws_info in self._ws_clients.items():
            await self._start_platform_websocket(platform_name, ws_info)

        logger.info(f"服务已启动，已注册平台: {self._multi_platform_manager.get_platform_names()}")

        # 启动交互请求监控任务
        self._interaction_monitor_task = asyncio.create_task(
            self._interaction_monitor.monitor_interaction_requests()
        )
        logger.info("交互请求监控已启动")

        # 启动本地 HTTP API 服务器（用于集成测试）
        # 通过环境变量控制，默认不启动
        test_mode = os.getenv("TEST_MODE_ENABLED", "false").lower() == "true"
        if test_mode:
            api_server = get_api_server()
            api_server.set_message_handler(message_handler)
            await api_server.start()
            logger.info("API 服务器已启动（测试模式）")

        # 等待关闭信号
        await self._shutdown_event.wait()

        # 清理任务
        logger.info("正在关闭服务...")
        await self.stop()

    async def _start_platform_websocket(self, platform_name: str, ws_info: dict):
        """
        启动指定平台的 WebSocket 客户端

        Args:
            platform_name: 平台名称
            ws_info: WebSocket 信息字典
        """
        try:
            # 对于飞书平台，使用官方 SDK 的 WebSocket 客户端
            if platform_name == "feishu":
                # 创建事件处理器
                event_handler = lark.EventDispatcherHandler.builder(
                    "",  # encrypt_key (空字符串用于本地开发)
                    ""   # verification_token (空字符串用于本地开发)
                ) \
                    .register_p2_im_message_receive_v1(self._do_p2_im_message_receive_v1) \
                    .register_p2_card_action_trigger(self._do_p2_card_action_trigger) \
                    .build()

                # 创建 WebSocket 客户端
                ws_client = lark.ws.Client(
                    get_settings().FEISHU_APP_ID,
                    get_settings().FEISHU_APP_SECRET,
                    event_handler=event_handler,
                    log_level=lark.LogLevel.INFO
                )

                # 在独立线程中运行 WebSocket 客户端
                ws_thread = threading.Thread(
                    target=self._run_websocket,
                    args=(ws_client, platform_name),
                    daemon=True
                )
                ws_thread.start()

                self._ws_threads[platform_name] = ws_thread
                logger.info(f"平台 {platform_name} 的 WebSocket 客户端已启动")

            # 其他平台可以在这里添加处理逻辑

        except Exception as e:
            logger.error(f"启动平台 {platform_name} 的 WebSocket 时出错: {e}", exc_info=True)

    def _run_websocket(self, ws_client, platform_name: str):
        """
        运行 WebSocket 客户端 (在独立线程中)

        Args:
            ws_client: WebSocket 客户端实例
            platform_name: 平台名称
        """
        try:
            logger.info(f"平台 {platform_name} 的 WebSocket 客户端启动...")
            ws_client.start()
            # 连接成功，更新连接状态
            self._multi_platform_manager.set_connected_status(platform_name, True)
            logger.info(f"平台 {platform_name} 已连接")
        except Exception as e:
            logger.error(f"平台 {platform_name} 的 WebSocket 客户端出错: {e}", exc_info=True)
            # 连接失败，更新连接状态
            self._multi_platform_manager.set_connected_status(platform_name, False)
        finally:
            # WebSocket 客户端退出时触发关闭
            if not self._shutdown_event.is_set():
                self._shutdown_event.set()

    async def stop(self):
        """停止服务"""
        self._shutdown_event.set()

        # 停止 API 服务器
        api_server = get_api_server()
        await api_server.stop()

        # 停止交互监控任务
        if self._interaction_monitor_task and not self._interaction_monitor_task.done():
            self._interaction_monitor_task.cancel()
            try:
                await self._interaction_monitor_task
            except asyncio.CancelledError:
                pass
            logger.info("交互请求监控已停止")

        # 停止所有 WebSocket 客户端
        for platform_name, ws_thread in self._ws_threads.items():
            # 更新连接状态
            self._multi_platform_manager.set_connected_status(platform_name, False)

            # 等待线程结束
            if ws_thread and ws_thread.is_alive():
                ws_thread.join(timeout=5)
                logger.info(f"平台 {platform_name} 的 WebSocket 线程已停止")

        # 取消所有任务
        for task in self._tasks:
            if not task.done():
                task.cancel()

        # 等待任务结束
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # 停止任务管理器
        await task_manager.stop()

        logger.info("服务已关闭")


def handle_shutdown(service: ClaudeFeishuService):
    """处理关闭信号"""
    logger.info("收到关闭信号")
    service._shutdown_event.set()


async def main():
    """主函数"""
    service = ClaudeFeishuService()

    # 设置信号处理
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: handle_shutdown(service))

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("收到键盘中断")
    finally:
        await service.stop()


if __name__ == '__main__':
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        logger.info("服务已关闭")
        sys.exit(0)
