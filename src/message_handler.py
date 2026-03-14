"""
消息处理器

使用抽象层处理来自不同 IM 平台的消息
支持多平台接入和广播模式
"""
import asyncio
from typing import Optional, TYPE_CHECKING

from src.models import Message, MessageType
from src.storage import db
from src.config.settings import get_settings
from src.task_manager import task_manager

# 避免循环导入
if TYPE_CHECKING:
    from src.interfaces.im_platform import IIMPlatform, IIMCardBuilder, NormalizedCard, NormalizedMessage
    from src.im_platforms.notification_sender import INotificationSender
    from src.card_dispatcher import CardDispatcher

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class MessageHandler:
    """
    消息处理器

    使用抽象层处理来自不同 IM 平台的消息
    支持多平台接入和广播模式
    """

    def __init__(
        self,
        platform: Optional["IIMPlatform"] = None,
        card_builder: Optional["IIMCardBuilder"] = None,
        multi_platform_manager: Optional["MultiPlatformManager"] = None,
        notification_sender: Optional["INotificationSender"] = None,
    ):
        """
        初始化消息处理器

        Args:
            platform: IM 平台实例，如果为 None 则使用飞书平台
            card_builder: 卡片构建器实例，如果为 None 则使用飞书卡片构建器
            multi_platform_manager: 多平台管理器，用于多平台场景
            notification_sender: 通知发送器，用于发送消息
        """
        self._multi_platform_manager = multi_platform_manager
        self._notification_sender = notification_sender

        # 如果没有传入平台，使用飞书平台
        if platform is None:
            from src.factories.platform_factory import IMPlatformFactory
            from src.interfaces.im_platform import PlatformConfig

            # 注册飞书平台（如果尚未注册）
            if not IMPlatformFactory.is_platform_registered("feishu"):
                from src.im_platforms import register_feishu_platform
                register_feishu_platform()

            # 使用 IM_PLATFORM 配置创建平台
            platform_type = get_settings().IM_PLATFORM

            # 根据平台类型创建相应配置
            if platform_type == "feishu":
                config = PlatformConfig(
                    app_id=get_settings().FEISHU_APP_ID,
                    app_secret=get_settings().FEISHU_APP_SECRET,
                    domain=get_settings().FEISHU_MESSAGE_DOMAIN,
                    receive_id_type=get_settings().FEISHU_MESSAGE_RECEIVE_ID_TYPE,
                )
            else:
                config = PlatformConfig()

            platform = IMPlatformFactory.create_platform(platform_type, config)

        self.platform = platform
        self.tm = task_manager

        # 如果没有传入卡片构建器，使用平台的默认卡片构建器
        if card_builder is None and platform is not None:
            from src.factories.platform_factory import IMPlatformFactory
            card_builder = IMPlatformFactory.create_card_builder(get_settings().IM_PLATFORM)

        self.card_builder = card_builder
        from src.feishu import FeishuAPI
        self.feishu = FeishuAPI(get_settings().FEISHU_APP_ID, get_settings().FEISHU_APP_SECRET)

        # 当前处理消息的来源平台
        self._current_platform: Optional[str] = None

        # 初始化子处理器
        self._init_sub_handlers()

    def _init_sub_handlers(self):
        """初始化子处理器"""
        # 导入子处理器
        from src.handlers.message_sender import MessageSender
        from src.handlers.event_parser import EventParser
        from src.handlers.command_executor import CommandExecutor
        from src.handlers.platform_commands import PlatformCommands
        from src.handlers.attachment_handler import AttachmentHandler
        from src.card_dispatcher import CardDispatcher

        # 0. 创建 CardDispatcher（统一卡片发送入口）
        self._card_dispatcher = CardDispatcher(
            platform=self.platform,
            feishu_api=self.feishu,
            notification_sender=self._notification_sender,
        )

        # 1. 消息发送器
        self._message_sender = MessageSender(
            notification_sender=self._notification_sender,
            platform=self.platform,
            feishu_api=self.feishu,
            card_builder=self.card_builder,
            card_dispatcher=self._card_dispatcher,
        )

        # 2. 平台命令处理器
        self._platform_commands = PlatformCommands(
            task_manager=self.tm,
            card_builder=self.card_builder,
            feishu=self.feishu,
            send_via_sender=self._message_sender.send,
            card_dispatcher=self._card_dispatcher,
        )

        # 3. 附件处理器
        self._attachment_handler = AttachmentHandler(
            platform=self.platform,
            card_builder=self.card_builder,
            feishu=self.feishu,
            send_via_sender=self._message_sender.send,
            card_dispatcher=self._card_dispatcher,
        )

        # 4. 命令执行器
        self._command_executor = CommandExecutor(
            task_manager=self.tm,
            card_builder=self.card_builder,
            platform=self.platform,
            feishu_api=self.feishu,
            message_sender=self._message_sender,
            card_dispatcher=self._card_dispatcher,
        )
        self._command_executor.set_platform_commands(self._platform_commands)
        self._command_executor.set_current_platform(self._current_platform)

        # 设置命令执行器的实例到模块级变量，供 event_parser 使用
        from src.handlers import command_executor as cmd_exec_module
        cmd_exec_module.command_executor = self._command_executor

        # 5. 事件解析器
        self._event_parser = EventParser(
            platform=self.platform,
            attachment_handler=self._attachment_handler,
            on_execute_command=self._command_executor.execute_command,
        )

    def set_current_platform(self, platform_name: str) -> None:
        """
        设置当前处理消息的来源平台

        Args:
            platform_name: 平台名称
        """
        self._current_platform = platform_name
        self._command_executor.set_current_platform(platform_name)

    def get_current_platform(self) -> Optional[str]:
        """
        获取当前处理消息的来源平台

        Returns:
            平台名称，如果未设置则返回 None
        """
        return self._current_platform

    def set_notification_sender(self, sender: "INotificationSender") -> None:
        """
        设置通知发送器

        Args:
            sender: 通知发送器实例
        """
        self._notification_sender = sender
        self._message_sender.set_notification_sender(sender)
        # 更新子处理器的发送回调
        self._platform_commands.set_send_callback(self._message_sender.send)
        self._attachment_handler.set_send_callback(self._message_sender.send)

    async def handle_event(self, event_data: dict):
        """
        处理平台事件（委托给事件解析器）

        Args:
            event_data: 平台事件数据
        """
        await self._event_parser.handle_event(event_data)

    async def _send_via_sender(
        self,
        user_id: str,
        card: Optional[dict] = None,
        message: Optional[str] = None,
    ) -> bool:
        """
        通过消息发送器发送消息或卡片（向后兼容）

        Args:
            user_id: 用户 ID
            card: 卡片内容
            message: 文本消息

        Returns:
            发送成功返回 True，否则返回 False
        """
        return await self._message_sender.send(user_id, card=card, message=message)

    async def _send_error(self, user_id: str, error: str):
        """
        发送错误消息（委托给命令执行器）

        Args:
            user_id: 用户 ID
            error: 错误信息
        """
        await self._command_executor.send_error(user_id, error)


# 全局消息处理器实例
message_handler = MessageHandler()
