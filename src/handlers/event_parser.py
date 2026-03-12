"""
事件解析器

负责解析和分发平台事件
"""
import asyncio
import json
from typing import Dict, Any, Optional, TYPE_CHECKING, Callable, Awaitable

# 避免循环导入
if TYPE_CHECKING:
    from src.interfaces.im_platform import IIMPlatform, NormalizedMessage

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class EventParser:
    """
    事件解析器

    负责解析平台事件并分发到相应处理器
    """

    def __init__(
        self,
        platform: Optional["IIMPlatform"] = None,
        attachment_handler=None,
        on_execute_command: Optional[Callable[[str, str], Awaitable[None]]] = None,
    ):
        """
        初始化事件解析器

        Args:
            platform: IM 平台实例
            attachment_handler: 附件处理器
            on_execute_command: 执行命令的回调函数
        """
        self.platform = platform
        self._attachment_handler = attachment_handler
        self._on_execute_command = on_execute_command

    def set_attachment_handler(self, handler) -> None:
        """设置附件处理器"""
        self._attachment_handler = handler

    def set_execute_command_callback(self, callback: Callable[[str, str], Awaitable[None]]) -> None:
        """设置执行命令的回调"""
        self._on_execute_command = callback

    async def handle_event(self, event_data: Dict[str, Any]):
        """
        处理平台事件

        Args:
            event_data: 平台事件数据
        """
        logger.debug("handle_event 被调用")
        if self.platform is None:
            # 如果平台不可用，使用原有逻辑
            await self._handle_legacy_event(event_data)
            return

        # 使用平台解析事件
        logger.debug("准备调用 platform.parse_event...")
        try:
            normalized_message = self.platform.parse_event(event_data)
            logger.debug(f"parse_event 返回: {normalized_message}")
        except Exception as e:
            logger.error(f"parse_event 异常: {e}", exc_info=True)
            return

        if normalized_message is None:
            logger.warning("无法解析平台事件")
            return

        # 处理标准化消息
        logger.debug(f"准备调用 _handle_normalized_message，消息类型: {normalized_message.message_type}")
        await self._handle_normalized_message(normalized_message)
        logger.debug("_handle_normalized_message 执行完成")

    async def _handle_legacy_event(self, event_data: Dict[str, Any]):
        """
        处理飞书事件

        Args:
            event_data: 飞书事件数据
        """
        event_type = event_data.get("type")

        if event_type == "im.message.receive_v1":
            await self._handle_message_receive(event_data)
        else:
            logger.warning(f"未知事件类型: {event_type}")

    async def _handle_message_receive(self, event_data: Dict[str, Any]):
        """处理消息接收事件"""
        try:
            event = event_data.get("event", {})
            sender = event.get("sender", {})
            message = event.get("message", {})

            user_id = sender.get("sender_id", {}).get("open_id")
            message_id = message.get("message_id")
            content = message.get("content")
            msg_type = message.get("msg_type")

            if not user_id or not content:
                logger.warning("消息数据不完整")
                return

            # 解析消息内容
            content_data = json.loads(content)

            # 处理图片消息
            if msg_type == "image":
                command = await self._attachment_handler.handle_image_message(user_id, content_data, message_id)
                if command and self._on_execute_command:
                    await self._on_execute_command(user_id, command)
                return

            # 处理语音消息
            if msg_type == "audio":
                command = await self._attachment_handler.handle_voice_message(user_id, content_data, message_id)
                if command and self._on_execute_command:
                    await self._on_execute_command(user_id, command)
                return

            # 处理文本消息
            text = content_data.get("text", "").strip()

            if not text:
                return

            logger.info(f"收到来自用户 {user_id} 的消息: {text}")

            # 异步处理命令（不阻塞）
            # 注意：这里通过回调处理，因为 command_executor 需要访问更多上下文
            from src.handlers.command_executor import command_executor
            # 动态调用，避免循环导入
            asyncio.create_task(self._dispatch_command(user_id, text, message_id))

        except Exception as e:
            logger.error(f"处理消息事件时出错: {e}", exc_info=True)

    async def _dispatch_command(self, user_id: str, command: str, message_id: str = None):
        """分发命令到命令执行器"""
        # 延迟导入避免循环依赖
        from src.handlers.command_executor import command_executor
        await command_executor.process_command(user_id, command, message_id)

    async def _handle_normalized_message(self, normalized_message: "NormalizedMessage"):
        """
        处理标准化消息

        Args:
            normalized_message: 标准化消息对象
        """
        try:
            user_id = normalized_message.user_id
            content = normalized_message.content

            # 根据消息类型处理（图片和文件不需要 content）
            from src.interfaces.im_platform import MessageType as PlatformMessageType

            if normalized_message.message_type == PlatformMessageType.IMAGE:
                logger.info(f"收到图片消息，message_id: {normalized_message.message_id}")
                command = await self._attachment_handler.handle_image_attachment(user_id, normalized_message)
                if command and self._on_execute_command:
                    await self._on_execute_command(user_id, command)
                return
            elif normalized_message.message_type == PlatformMessageType.FILE:
                logger.info(f"收到文件消息，message_id: {normalized_message.message_id}")
                command = await self._attachment_handler.handle_file_attachment(user_id, normalized_message)
                if command and self._on_execute_command:
                    await self._on_execute_command(user_id, command)
                return
            elif normalized_message.message_type == PlatformMessageType.VOICE:
                logger.info(f"收到语音消息，message_id: {normalized_message.message_id}")
                command = await self._attachment_handler.handle_voice_attachment(user_id, normalized_message)
                if command and self._on_execute_command:
                    await self._on_execute_command(user_id, command)
                return

            # 文本消息需要 content
            if not content:
                return

            # 文本或其他类型
            logger.info(f"收到来自用户 {user_id} 的消息: {content}")
            from src.handlers.command_executor import command_executor
            await command_executor.process_command(user_id, content, normalized_message.message_id)

        except Exception as e:
            logger.error(f"处理标准化消息时出错: {e}", exc_info=True)
