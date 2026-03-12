"""
附件处理器

处理图片和文件消息
"""
import json
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.models import Message, MessageType
from src.storage import db

# 避免循环导入
if TYPE_CHECKING:
    from src.interfaces.im_platform import IIMPlatform, IIMCardBuilder, NormalizedMessage, NormalizedCard
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


class AttachmentHandler:
    """附件处理器"""

    def __init__(
        self,
        platform: Optional["IIMPlatform"] = None,
        card_builder: Optional["IIMCardBuilder"] = None,
        feishu=None,
        send_via_sender=None,
        card_dispatcher: Optional["CardDispatcher"] = None,
    ):
        """
        初始化附件处理器

        Args:
            platform: IM 平台实例
            card_builder: 卡片构建器实例（已废弃，保留兼容性）
            feishu: 飞书 API 实例
            send_via_sender: 发送消息的回调函数
            card_dispatcher: 卡片发送器（新架构）
        """
        self.platform = platform
        self.card_builder = card_builder
        self.feishu = feishu
        self._send_via_sender = send_via_sender
        self.card_dispatcher = card_dispatcher

    def set_send_callback(self, send_via_sender):
        """设置发送回调函数"""
        self._send_via_sender = send_via_sender

    async def handle_image_message(self, user_id: str, content_data: Dict[str, Any], message_id: str):
        """
        处理图片消息（飞书原生格式）

        Args:
            user_id: 用户 ID
            content_data: 消息内容数据
            message_id: 消息 ID
        """
        try:
            image_key = content_data.get("image_key")
            if not image_key:
                logger.warning("图片消息没有 image_key")
                await self._send_error(user_id, "图片消息格式错误")
                return

            logger.info(f"收到图片，image_key: {image_key}")

            # 发送确认消息（使用 CardDispatcher）
            if self.card_dispatcher:
                from src.card_builder import UnifiedCardBuilder
                content = UnifiedCardBuilder.build_text_card("正在下载图片...")
                await self.card_dispatcher.send_card(
                    user_id=user_id,
                    card_type="download_image",
                    title="下载图片",
                    content=content,
                    message_type="response",
                    template_color="grey"
                )
            else:
                logger.warning("CardDispatcher 不可用，跳过发送确认消息")

            # 下载图片
            image_path = await self.platform.download_file(message_id, image_key)
            if not image_path:
                await self._send_error(user_id, "下载图片失败")
                return

            # 将图片路径作为命令传递给 AI 助手
            command = f"Read the image at {image_path}"

            # 保存消息
            from src.models import MessageDirection, MessageSource
            msg = Message(
                user_id=user_id,
                message_type=MessageType.COMMAND,
                content=f"[图片: {image_path.name}] {command}",
                direction=MessageDirection.UPSTREAM,
                is_test=None,
                message_source=MessageSource.FEISHU,
                feishu_message_id=message_id
            )
            db.save_message(msg)

            # 返回命令供外部执行
            return command

        except Exception as e:
            logger.error(f"处理图片消息时出错: {e}", exc_info=True)
            await self._send_error(user_id, f"处理图片失败: {str(e)}")
            return None

    async def handle_image_attachment(self, user_id: str, normalized_message: "NormalizedMessage"):
        """
        处理图片附件（使用抽象层）

        Args:
            user_id: 用户 ID
            normalized_message: 标准化消息对象
        """
        try:
            if not normalized_message.attachments:
                await self._send_error(user_id, "图片附件数据缺失")
                return

            image_key = normalized_message.attachments[0].get("image_key")
            if not image_key:
                await self._send_error(user_id, "图片附件格式错误")
                return

            logger.info(f"收到图片，image_key: {image_key}")

            # 下载图片
            image_path = await self.platform.download_file(
                normalized_message.message_id,
                image_key
            )

            if not image_path:
                await self._send_error(user_id, "下载图片失败")
                return

            # 将图片路径作为命令传递给 AI 助手
            command = f"Read the image at {image_path}"

            # 保存消息
            from src.models import MessageDirection, MessageSource
            msg = Message(
                user_id=user_id,
                message_type=MessageType.COMMAND,
                content=f"[图片: {image_path.name}] {command}",
                direction=MessageDirection.UPSTREAM,
                is_test=None,
                message_source=MessageSource.FEISHU,
                feishu_message_id=normalized_message.message_id
            )
            db.save_message(msg)

            # 返回命令供外部执行
            return command

        except Exception as e:
            logger.error(f"处理图片附件时出错: {e}", exc_info=True)
            await self._send_error(user_id, f"处理图片失败: {str(e)}")
            return None

    async def handle_file_attachment(self, user_id: str, normalized_message: "NormalizedMessage"):
        """
        处理文件附件

        Args:
            user_id: 用户 ID
            normalized_message: 标准化消息对象
        """
        try:
            if not normalized_message.attachments:
                await self._send_error(user_id, "文件附件数据缺失")
                return

            file_key = normalized_message.attachments[0].get("file_key")
            if not file_key:
                await self._send_error(user_id, "文件附件格式错误")
                return

            logger.info(f"收到文件，file_key: {file_key}")

            # 下载文件
            file_path = await self.platform.download_file(
                normalized_message.message_id,
                file_key
            )

            if not file_path:
                await self._send_error(user_id, "下载文件失败")
                return

            # 将文件路径作为命令传递给 AI 助手
            command = f"Read the file at {file_path}"

            # 保存消息
            from src.models import MessageDirection, MessageSource
            msg = Message(
                user_id=user_id,
                message_type=MessageType.COMMAND,
                content=f"[文件: {file_path.name}] {command}",
                direction=MessageDirection.UPSTREAM,
                is_test=None,
                message_source=MessageSource.FEISHU,
                feishu_message_id=normalized_message.message_id
            )
            db.save_message(msg)

            # 返回命令供外部执行
            return command

        except Exception as e:
            logger.error(f"处理文件附件时出错: {e}", exc_info=True)
            await self._send_error(user_id, f"处理文件失败: {str(e)}")
            return None

    async def _send_error(self, user_id: str, error: str):
        """发送错误消息"""
        # 优先使用 CardDispatcher
        if self.card_dispatcher:
            from src.card_builder import UnifiedCardBuilder
            content = UnifiedCardBuilder.build_error_card(error)
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="error",
                title="错误",
                content=content,
                message_type="error",
                template_color="red"
            )
        elif self.card_builder:
            from src.interfaces.im_platform import NormalizedCard
            card = NormalizedCard(
                card_type="error",
                title="错误",
                content=error,
                template_color="red"
            )
            await self._send_via_sender(user_id, card=card)
        else:
            from src.card_manager import create_error_card
            card = create_error_card(error)
            await self._send_via_sender(user_id, message=json.dumps(card, ensure_ascii=False))

    async def handle_voice_message(self, user_id: str, content_data: Dict[str, Any], message_id: str):
        """
        处理语音消息（飞书原生格式）

        Args:
            user_id: 用户 ID
            content_data: 消息内容数据
            message_id: 消息 ID
        """
        try:
            file_key = content_data.get("file_key")
            if not file_key:
                logger.warning("语音消息没有 file_key")
                await self._send_error(user_id, "语音消息格式错误")
                return

            logger.info(f"收到语音，file_key: {file_key}")

            # 发送确认消息（使用 CardDispatcher）
            if self.card_dispatcher:
                from src.card_builder import UnifiedCardBuilder
                content = UnifiedCardBuilder.build_text_card("正在下载语音...")
                await self.card_dispatcher.send_card(
                    user_id=user_id,
                    card_type="download_voice",
                    title="下载语音",
                    content=content,
                    message_type="response",
                    template_color="grey"
                )
            else:
                logger.warning("CardDispatcher 不可用，跳过发送确认消息")

            # 下载语音文件
            voice_path = await self.platform.download_file(message_id, file_key)
            if not voice_path:
                await self._send_error(user_id, "下载语音失败")
                return

            # 将语音路径作为命令传递给 AI 助手
            command = f"Listen to the audio at {voice_path}"

            # 保存消息
            from src.models import MessageDirection, MessageSource
            msg = Message(
                user_id=user_id,
                message_type=MessageType.COMMAND,
                content=f"[语音: {voice_path.name}] {command}",
                direction=MessageDirection.UPSTREAM,
                is_test=None,
                message_source=MessageSource.FEISHU,
                feishu_message_id=message_id
            )
            db.save_message(msg)

            # 返回命令供外部执行
            return command

        except Exception as e:
            logger.error(f"处理语音消息时出错: {e}", exc_info=True)
            await self._send_error(user_id, f"处理语音失败: {str(e)}")
            return None

    async def handle_voice_attachment(self, user_id: str, normalized_message: "NormalizedMessage"):
        """
        处理语音附件（使用抽象层）

        Args:
            user_id: 用户 ID
            normalized_message: 标准化消息对象
        """
        try:
            if not normalized_message.attachments:
                await self._send_error(user_id, "语音附件数据缺失")
                return

            file_key = normalized_message.attachments[0].get("file_key")
            if not file_key:
                await self._send_error(user_id, "语音附件格式错误")
                return

            logger.info(f"收到语音，file_key: {file_key}")

            # 下载语音文件
            voice_path = await self.platform.download_file(
                normalized_message.message_id,
                file_key
            )

            if not voice_path:
                await self._send_error(user_id, "下载语音失败")
                return

            # 将语音路径作为命令传递给 AI 助手
            command = f"Listen to the audio at {voice_path}"

            # 保存消息
            from src.models import MessageDirection, MessageSource
            msg = Message(
                user_id=user_id,
                message_type=MessageType.COMMAND,
                content=f"[语音: {voice_path.name}] {command}",
                direction=MessageDirection.UPSTREAM,
                is_test=None,
                message_source=MessageSource.FEISHU,
                feishu_message_id=normalized_message.message_id
            )
            db.save_message(msg)

            # 返回命令供外部执行
            return command

        except Exception as e:
            logger.error(f"处理语音附件时出错: {e}", exc_info=True)
            await self._send_error(user_id, f"处理语音失败: {str(e)}")
            return None
