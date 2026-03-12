"""
AI 助手工厂

用于动态创建不同 AI 助手的实例
"""
from typing import Optional, Dict, Type

from src.interfaces.ai_assistant import (
    IAIAssistantInterface,
    AssistantType,
    AssistantConfig
)

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AIAssistantFactory:
    """AI 助手工厂"""

    # 注册的助手类型：助手类型 -> 助手类
    _assistants: Dict[AssistantType, Type[IAIAssistantInterface]] = {}

    @classmethod
    def register_assistant(
        cls,
        assistant_type: AssistantType,
        assistant_class: Type[IAIAssistantInterface]
    ) -> None:
        """
        注册新助手

        Args:
            assistant_type: 助手类型标识符
            assistant_class: 助手实现类
        """
        cls._assistants[assistant_type] = assistant_class
        logger.info(f"已注册 AI 助手: {assistant_type.value}")

    @classmethod
    def create_assistant(
        cls,
        assistant_type: AssistantType,
        config: AssistantConfig
    ) -> Optional[IAIAssistantInterface]:
        """
        创建 AI 助手实例

        Args:
            assistant_type: 助手类型标识符
            config: 助手配置

        Returns:
            助手实例，如果类型未注册则返回 None
        """
        if assistant_type not in cls._assistants:
            logger.error(f"未知的助手类型: {assistant_type.value}")
            logger.debug(f"已注册的助手: {[t.value for t in cls._assistants.keys()]}")
            return None

        assistant_class = cls._assistants[assistant_type]
        try:
            assistant = assistant_class(config)
            logger.info(f"成功创建助手实例: {assistant_type.value}")
            return assistant
        except Exception as e:
            logger.error(f"创建助手实例失败 ({assistant_type.value}): {e}", exc_info=True)
            return None

    @classmethod
    def create_assistant_by_name(
        cls,
        assistant_type_name: str,
        config: AssistantConfig
    ) -> Optional[IAIAssistantInterface]:
        """
        通过名称创建 AI 助手实例

        Args:
            assistant_type_name: 助手类型名称（字符串）
            config: 助手配置

        Returns:
            助手实例，如果类型未注册则返回 None
        """
        try:
            assistant_type = AssistantType(assistant_type_name)
            return cls.create_assistant(assistant_type, config)
        except ValueError:
            logger.error(f"未知的助手类型名称: {assistant_type_name}")
            return None

    @classmethod
    def get_registered_assistants(cls) -> list:
        """获取所有已注册的助手类型"""
        return [t.value for t in cls._assistants.keys()]

    @classmethod
    def is_assistant_registered(cls, assistant_type: AssistantType) -> bool:
        """检查助手是否已注册"""
        return assistant_type in cls._assistants

    @classmethod
    def unregister_assistant(cls, assistant_type: AssistantType) -> bool:
        """
        注销助手

        Args:
            assistant_type: 助手类型标识符

        Returns:
            是否成功注销
        """
        if assistant_type in cls._assistants:
            del cls._assistants[assistant_type]
            logger.info(f"已注销 AI 助手: {assistant_type.value}")
            return True
        return False
