"""
多平台管理器

管理多个 IM 平台的注册、连接状态和消息广播
支持两种模式：
1. 静态模式：基于配置注册平台，用于 Hooks 通知
2. 动态模式：基于实际连接状态广播，用于 WebSocket 消息
"""
from typing import Dict, Optional, List, Set
from src.interfaces.im_platform import IIMPlatform, NormalizedCard, MessageType

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class MultiPlatformManager:
    """多平台管理器"""

    def __init__(self):
        # 已注册的平台（所有配置的平台）
        self._platforms: Dict[str, IIMPlatform] = {}

        # 连接状态跟踪（实际已连接的平台）
        self._connected_platforms: Dict[str, bool] = {}

        # 平台名称集合
        self._platform_names: Set[str] = set()

    def register_platform(self, name: str, platform: IIMPlatform) -> None:
        """
        注册平台

        Args:
            name: 平台名称（如 "feishu", "slack"）
            platform: 平台实例
        """
        self._platforms[name] = platform
        self._platform_names.add(name)
        # 初始化连接状态为 False
        self._connected_platforms[name] = False

    def unregister_platform(self, name: str) -> Optional[IIMPlatform]:
        """
        注销平台

        Args:
            name: 平台名称

        Returns:
            被注销的平台实例，如果不存在则返回 None
        """
        platform = self._platforms.pop(name, None)
        if name in self._platform_names:
            self._platform_names.remove(name)
        if name in self._connected_platforms:
            del self._connected_platforms[name]
        return platform

    def get_platform(self, name: str) -> Optional[IIMPlatform]:
        """
        获取指定平台

        Args:
            name: 平台名称

        Returns:
            平台实例，如果不存在则返回 None
        """
        return self._platforms.get(name)

    def get_all_platforms(self) -> Dict[str, IIMPlatform]:
        """
        获取所有已注册的平台

        Returns:
            平台名称到平台实例的映射
        """
        return dict(self._platforms)

    def get_connected_platforms(self) -> Dict[str, IIMPlatform]:
        """
        获取所有已连接的平台

        Returns:
            平台名称到平台实例的映射（仅包含已连接的平台）
        """
        return {
            name: platform
            for name, platform in self._platforms.items()
            if self._connected_platforms.get(name, False)
        }

    def is_connected(self, name: str) -> bool:
        """
        检查平台是否已连接

        Args:
            name: 平台名称

        Returns:
            如果平台已连接返回 True，否则返回 False
        """
        return self._connected_platforms.get(name, False)

    def set_connected_status(self, name: str, is_connected: bool) -> None:
        """
        设置平台的连接状态

        Args:
            name: 平台名称
            is_connected: 连接状态
        """
        if name in self._platforms:
            self._connected_platforms[name] = is_connected

    def is_platform_registered(self, name: str) -> bool:
        """
        检查平台是否已注册

        Args:
            name: 平台名称

        Returns:
            如果平台已注册返回 True，否则返回 False
        """
        return name in self._platforms

    def get_platform_names(self) -> List[str]:
        """
        获取所有已注册的平台名称

        Returns:
            平台名称列表
        """
        return sorted(list(self._platform_names))

    # ==================== 广播方法 ====================

    async def broadcast_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
        include_all: bool = False,
    ) -> Dict[str, bool]:
        """
        向所有平台广播消息

        Args:
            user_id: 用户 ID
            content: 消息内容
            message_type: 消息类型
            include_all: 是否包含未连接的平台（False 表示只发送到已连接的平台）

        Returns:
            平台名称到发送结果的映射（True=成功，False=失败）
        """
        results = {}
        platforms_to_send = self._platforms if include_all else self.get_connected_platforms()

        for name, platform in platforms_to_send.items():
            try:
                result = await platform.send_message(user_id, content, message_type)
                results[name] = result
            except Exception as e:
                results[name] = False

        return results

    async def broadcast_card(
        self,
        user_id: str,
        card: NormalizedCard,
        include_all: bool = False,
    ) -> Dict[str, bool]:
        """
        向所有平台广播卡片

        Args:
            user_id: 用户 ID
            card: 标准化卡片
            include_all: 是否包含未连接的平台

        Returns:
            平台名称到发送结果的映射
        """
        logger.info(f"MultiPlatformManager.broadcast_card 开始: user_id={user_id}, card={card.title}, include_all={include_all}")
        logger.info(f"_platforms: {list(self._platforms.keys())}")
        logger.info(f"_connected_platforms: {self._connected_platforms}")
        platforms_to_send = self._platforms if include_all else self.get_connected_platforms()
        logger.info(f"platforms_to_send: {list(platforms_to_send.keys())}")

        results = {}
        for name, platform in platforms_to_send.items():
            try:
                logger.info(f"准备调用 platform.send_card: {name}")
                result = await platform.send_card(user_id, card)
                logger.info(f"platform.send_card 返回: {name}={result}")
                results[name] = result
            except Exception as e:
                logger.error(f"platform.send_card 异常: {name}={e}", exc_info=True)
                results[name] = False

        logger.info(f"broadcast_card 返回: {results}")
        return results

    # ==================== 定向发送方法 ====================

    async def send_to_platform(
        self,
        platform_name: str,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """
        向指定平台发送消息

        Args:
            platform_name: 平台名称
            user_id: 用户 ID
            content: 消息内容
            message_type: 消息类型

        Returns:
            发送成功返回 True，否则返回 False
        """
        platform = self._platforms.get(platform_name)
        if not platform:
            return False

        try:
            return await platform.send_message(user_id, content, message_type)
        except Exception:
            return False

    async def send_card_to_platform(
        self,
        platform_name: str,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """
        向指定平台发送卡片

        Args:
            platform_name: 平台名称
            user_id: 用户 ID
            card: 标准化卡片

        Returns:
            发送成功返回 True，否则返回 False
        """
        platform = self._platforms.get(platform_name)
        if not platform:
            return False

        try:
            return await platform.send_card(user_id, card)
        except Exception:
            return False

    # ==================== 批量发送方法 ====================

    async def send_to_platforms(
        self,
        platform_names: List[str],
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> Dict[str, bool]:
        """
        向指定的多个平台发送消息

        Args:
            platform_names: 平台名称列表
            user_id: 用户 ID
            content: 消息内容
            message_type: 消息类型

        Returns:
            平台名称到发送结果的映射
        """
        results = {}
        for name in platform_names:
            results[name] = await self.send_to_platform(name, user_id, content, message_type)
        return results

    async def send_card_to_platforms(
        self,
        platform_names: List[str],
        user_id: str,
        card: NormalizedCard,
    ) -> Dict[str, bool]:
        """
        向指定的多个平台发送卡片

        Args:
            platform_names: 平台名称列表
            user_id: 用户 ID
            card: 标准化卡片

        Returns:
            平台名称到发送结果的映射
        """
        results = {}
        for name in platform_names:
            results[name] = await self.send_card_to_platform(name, user_id, card)
        return results
