"""
消息发送器

负责所有消息/卡片的发送逻辑，并记录所有下发的消息
"""
import json
from typing import Optional, Union, TYPE_CHECKING

# 避免循环导入
if TYPE_CHECKING:
    from src.interfaces.im_platform import IIMPlatform, IIMCardBuilder, NormalizedCard
    from src.im_platforms.notification_sender import INotificationSender
    from src.card_dispatcher import CardDispatcher
else:
    # 运行时导入
    from src.interfaces.im_platform import NormalizedCard

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class MessageSender:
    """
    消息发送器

    负责通过通知发送器或平台发送消息/卡片，并记录所有下发的消息
    """

    def __init__(
        self,
        notification_sender: Optional["INotificationSender"] = None,
        platform: Optional["IIMPlatform"] = None,
        feishu_api=None,
        card_builder: Optional["IIMCardBuilder"] = None,
        card_dispatcher: Optional["CardDispatcher"] = None,
    ):
        """
        初始化消息发送器

        Args:
            notification_sender: 通知发送器
            platform: IM 平台实例
            feishu_api: 飞书 API 实例
            card_builder: 卡片构建器（已废弃，保留兼容性）
            card_dispatcher: 卡片发送器（新架构）
        """
        self._notification_sender = notification_sender
        self.platform = platform
        self.feishu = feishu_api
        self.card_builder = card_builder
        self.card_dispatcher = card_dispatcher

    def set_notification_sender(self, sender: "INotificationSender") -> None:
        """设置通知发送器"""
        self._notification_sender = sender

    def set_card_builder(self, card_builder: "IIMCardBuilder") -> None:
        """设置卡片构建器"""
        self.card_builder = card_builder

    def _get_message_id_from_notification_sender(self, msg_type: str = "card") -> str:
        """从 notification_sender 获取 message_id"""
        if not self._notification_sender:
            return ""

        # DynamicBroadcastSender 有 last_message_id 属性
        if hasattr(self._notification_sender, 'last_message_id'):
            return self._notification_sender.last_message_id

        return ""

    async def send(
        self,
        user_id: str,
        card: Optional[Union[dict, "NormalizedCard"]] = None,
        message: Optional[str] = None,
        message_type: str = "response",
    ) -> bool:
        """
        发送消息或卡片，并记录到数据库

        Args:
            user_id: 用户 ID
            card: 卡片内容（dict 或 NormalizedCard）
            message: 文本消息
            message_type: 消息类型（response, status, error）

        Returns:
            发送成功返回 True，否则返回 False
        """
        from src.models import Message, MessageType, MessageDirection, MessageSource
        from src.storage import db

        logger.debug(f"send 被调用：user_id={user_id}, card_type={type(card) if card else None}, message={bool(message)}")
        logger.debug(f"_notification_sender: {self._notification_sender}")
        logger.debug(f"self.platform: {self.platform}")
        logger.debug(f"self.feishu: {self.feishu}")

        # 构建消息内容
        content = ""
        if card is not None:
            if isinstance(card, NormalizedCard):
                # 使用纯内容存储（不包含元数据）
                content = card.get_pure_content()
            elif isinstance(card, dict):
                content = json.dumps(card, ensure_ascii=False)
        elif message is not None:
            content = message
        else:
            content = ""

        # 先发送消息，获取飞书返回的 message_id
        feishu_msg_id = ""
        notification_sent = False  # 标记是否已通过 notification_sender 发送

        # 如果有专门的发送器，使用发送器
        if self._notification_sender:
            logger.debug("使用 notification_sender 发送")
            # 转换为 NormalizedCard（如果是 dict）
            normalized_card = None
            if card is not None:
                if isinstance(card, NormalizedCard):
                    normalized_card = card
                elif isinstance(card, dict):
                    # 对于 dict 类型的卡片，暂时跳过，使用平台发送
                    pass

            if normalized_card is not None:
                result = await self._notification_sender.send_card(user_id, normalized_card)
                notification_sent = True
                logger.debug(f"notification_sender.send_card 返回：{result}")
                if not result:
                    return result
                # 尝试从 notification_sender 获取 message_id
                feishu_msg_id = self._get_message_id_from_notification_sender("card")
            elif message is not None:
                result = await self._notification_sender.send_message(user_id, message)
                notification_sent = True
                logger.debug(f"notification_sender.send_message 返回：{result}")
                if not result:
                    return result
                # 尝试从 notification_sender 获取 message_id
                feishu_msg_id = self._get_message_id_from_notification_sender("message")

            # 如果已经通过 notification_sender 发送成功，不再走回退逻辑
            if notification_sent:
                logger.debug("notification_sender 发送成功，跳过回退逻辑")

        # 回退到平台发送器（仅当没有通过 notification_sender 发送时）
        if not notification_sent and not feishu_msg_id:
            logger.info("使用回退逻辑（平台发送器）")
            if card is not None:
                if isinstance(card, dict):
                    logger.debug("使用 feishu.send_message 发送 dict 卡片")
                    feishu_msg_id = await self.feishu.send_message(user_id, json.dumps(card, ensure_ascii=False)) or ""
                    logger.debug(f"feishu.send_message 返回：{feishu_msg_id}")
                elif isinstance(card, NormalizedCard):
                    logger.debug("使用 platform.send_card 发送 NormalizedCard")
                    feishu_msg_id = await self.platform.send_card(user_id, card) or ""
                    logger.debug(f"platform.send_card 返回：{feishu_msg_id}")

            if message is not None and not feishu_msg_id:
                logger.debug("使用 platform.send_message 发送文本消息")
                feishu_msg_id = await self.platform.send_message(user_id, message) or ""
                logger.debug(f"platform.send_message 返回：{feishu_msg_id}")

        # 发送成功后记录消息（下行消息）
        if feishu_msg_id or content:
            # 提取 card_id（如果发送的是卡片）
            card_id = None
            if card is not None and isinstance(card, NormalizedCard):
                card_id = card.card_id

            msg = Message(
                user_id=user_id,
                message_type=MessageType(message_type),
                content=content,
                direction=MessageDirection.DOWNSTREAM,
                is_test=None,  # 使用全局测试模式
                message_source=MessageSource.FEISHU,
                feishu_message_id=feishu_msg_id or "",
                card_id=card_id
            )
            db.save_message(msg)

        return True

    async def send_error(self, user_id: str, error: str):
        """
        发送错误消息

        Args:
            user_id: 用户 ID
            error: 错误信息
        """
        if self.card_builder:
            from src.interfaces.im_platform import NormalizedCard
            card = self.card_builder.create_error_card(error)
            await self.send(user_id, card=card, message_type="error")
        else:
            # 使用 CardDispatcher
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