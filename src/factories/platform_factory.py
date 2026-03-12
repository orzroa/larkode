"""
IM 平台工厂

用于动态创建不同 IM 平台的实例
"""
from typing import Optional, Dict, Type, Tuple

from src.interfaces.im_platform import IIMPlatform, IIMCardBuilder, PlatformConfig

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class IMPlatformFactory:
    """IM 平台工厂"""

    # 注册的平台类型：平台名称 -> (平台类, 卡片构建器类)
    _platforms: Dict[str, Tuple[Type[IIMPlatform], Type[IIMCardBuilder]]] = {}

    @classmethod
    def register_platform(
        cls,
        platform_type: str,
        platform_class: Type[IIMPlatform],
        card_builder_class: Type[IIMCardBuilder]
    ) -> None:
        """
        注册新平台

        Args:
            platform_type: 平台类型标识符（如 "feishu", "slack"）
            platform_class: 平台实现类
            card_builder_class: 卡片构建器类
        """
        cls._platforms[platform_type] = (platform_class, card_builder_class)
        logger.info(f"已注册平台: {platform_type}")

    @classmethod
    def create_platform(cls, platform_type: str, config: PlatformConfig) -> Optional[IIMPlatform]:
        """
        创建 IM 平台实例

        Args:
            platform_type: 平台类型标识符
            config: 平台配置

        Returns:
            平台实例，如果类型未注册则返回 None
        """
        if platform_type not in cls._platforms:
            logger.error(f"未知的平台类型: {platform_type}")
            logger.debug(f"已注册的平台: {list(cls._platforms.keys())}")
            return None

        platform_class, _ = cls._platforms[platform_type]
        try:
            platform = platform_class(config)
            logger.info(f"成功创建平台实例: {platform_type}")
            return platform
        except Exception as e:
            logger.error(f"创建平台实例失败 ({platform_type}): {e}", exc_info=True)
            return None

    @classmethod
    def create_card_builder(cls, platform_type: str) -> Optional[IIMCardBuilder]:
        """
        创建卡片构建器实例

        Args:
            platform_type: 平台类型标识符

        Returns:
            卡片构建器实例，如果类型未注册则返回 None
        """
        if platform_type not in cls._platforms:
            logger.error(f"未知的平台类型: {platform_type}")
            return None

        _, card_builder_class = cls._platforms[platform_type]
        try:
            card_builder = card_builder_class()
            logger.info(f"成功创建卡片构建器实例: {platform_type}")
            return card_builder
        except Exception as e:
            logger.error(f"创建卡片构建器实例失败 ({platform_type}): {e}", exc_info=True)
            return None

    @classmethod
    def get_registered_platforms(cls) -> list:
        """获取所有已注册的平台类型"""
        return list(cls._platforms.keys())

    @classmethod
    def is_platform_registered(cls, platform_type: str) -> bool:
        """检查平台是否已注册"""
        return platform_type in cls._platforms

    @classmethod
    def unregister_platform(cls, platform_type: str) -> bool:
        """
        注销平台

        Args:
            platform_type: 平台类型标识符

        Returns:
            是否成功注销
        """
        if platform_type in cls._platforms:
            del cls._platforms[platform_type]
            logger.info(f"已注销平台: {platform_type}")
            return True
        return False
