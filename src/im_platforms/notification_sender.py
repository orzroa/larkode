"""
通知发送器抽象层

提供两种发送模式：
1. StaticNotificationSender - 静态配置模式（Hooks）
2. DynamicBroadcastSender - 动态广播模式（WebSocket）
3. PlatformTargetedSender - 平台定向发送模式
"""
from abc import ABC, abstractmethod
from typing import Optional
from src.interfaces.im_platform import IIMPlatform, NormalizedCard, MessageType
from src.im_platforms.multi_platform_manager import MultiPlatformManager

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class INotificationSender(ABC):
    """通知发送器接口"""

    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """发送消息"""
        pass

    @abstractmethod
    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """发送卡片"""
        pass


class StaticNotificationSender(INotificationSender):
    """
    静态配置模式发送器

    特点：
    - 使用静态配置（从环境变量读取）
    - 发送到预配置的用户/平台
    - 不检查连接状态，直接按配置发送
    - 适用于 Hooks 通知场景

    使用场景：
    - hook_handler.py 触发的通知
    - 需要固定发送到特定用户的场景
    """

    def __init__(self, platform: IIMPlatform):
        """
        初始化静态发送器

        Args:
            platform: 目标平台实例
        """
        self._platform = platform

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """发送消息到配置的用户"""
        try:
            return await self._platform.send_message(user_id, content, message_type)
        except Exception as e:
            logger.error(f"发送消息失败: user_id={user_id}, error={e}")
            return False

    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """发送卡片到配置的用户"""
        try:
            return await self._platform.send_card(user_id, card)
        except Exception as e:
            logger.error(f"发送卡片失败: user_id={user_id}, error={e}")
            return False


class DynamicBroadcastSender(INotificationSender):
    """
    动态广播模式发送器

    特点：
    - 使用 MultiPlatformManager 管理多个平台
    - 广播到所有已连接的平台
    - 尊重连接状态，只发送到已连接的平台
    - 适用于 WebSocket 消息场景

    使用场景：
    - 实时接收和响应 IM 消息
    - 需要将响应广播到所有已连接平台
    - 动态平台上下线场景
    """

    def __init__(
        self,
        manager: MultiPlatformManager,
    ):
        """
        初始化动态广播发送器

        Args:
            manager: 多平台管理器
        """
        self._manager = manager
        # 默认广播到所有已注册平台（包括未连接的）
        self._broadcast_all = True
        # 保存最后一次发送的 message_id
        self._last_message_id: str = ""

    @property
    def last_message_id(self) -> str:
        """获取最后一次发送的 message_id"""
        return self._last_message_id

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """广播消息到所有已连接平台"""
        results = await self._manager.broadcast_message(
            user_id, content, message_type, include_all=self._broadcast_all
        )
        # 保存 message_id
        for msg_id in results.values():
            if msg_id:
                self._last_message_id = msg_id
                break
        # 只要有一个平台成功就返回 True
        return any(results.values())

    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """广播卡片到所有已连接平台"""
        logger.info(f"DynamicBroadcastSender.send_card 开始: user_id={user_id}, card={card.title}")

        results = await self._manager.broadcast_card(
            user_id, card, include_all=self._broadcast_all
        )

        logger.info(f"broadcast_card 返回: {results}")

        # 保存 message_id
        for msg_id in results.values():
            if msg_id:
                self._last_message_id = msg_id
                break

        # 只要有一个平台成功就返回 True
        result = any(results.values())
        logger.info(f"any(results.values())={result}")

        return result


class PlatformTargetedSender(INotificationSender):
    """
    平台定向发送器

    特点：
    - 发送到指定的单个平台
    - 记录消息来源平台信息
    - 用于需要精确控制发送目标的场景

    使用场景：
    - 回复特定平台的消息
    - 需要跟踪消息来源的场景
    - 多平台独立对话场景
    """

    def __init__(self, platform_name: str, manager: MultiPlatformManager):
        """
        初始化平台定向发送器

        Args:
            platform_name: 目标平台名称
            manager: 多平台管理器
        """
        self._platform_name = platform_name
        self._manager = manager

    @property
    def platform_name(self) -> str:
        """获取目标平台名称"""
        return self._platform_name

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """发送消息到指定平台"""
        return await self._manager.send_to_platform(
            self._platform_name, user_id, content, message_type
        )

    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """发送卡片到指定平台"""
        return await self._manager.send_card_to_platform(self._platform_name, user_id, card)


class MultiPlatformTargetedSender(INotificationSender):
    """
    多平台定向发送器

    特点：
    - 发送到指定的多个平台
    - 支持灵活的平台选择策略
    - 用于需要选择部分平台发送的场景

    使用场景：
    - 需要发送到特定几个平台
    - 根据业务规则选择平台
    - 分组广播场景
    """

    def __init__(self, platform_names: list[str], manager: MultiPlatformManager):
        """
        初始化多平台定向发送器

        Args:
            platform_names: 目标平台名称列表
            manager: 多平台管理器
        """
        self._platform_names = platform_names
        self._manager = manager

    @property
    def platform_names(self) -> list[str]:
        """获取目标平台名称列表"""
        return self._platform_names.copy()

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """发送消息到指定平台列表"""
        results = await self._manager.send_to_platforms(
            self._platform_names, user_id, content, message_type
        )
        return any(results.values())

    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """发送卡片到指定平台列表"""
        results = await self._manager.send_card_to_platforms(
            self._platform_names, user_id, card
        )
        return any(results.values())
