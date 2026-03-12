"""
工厂模式实现包

包含用于动态创建平台和助手的工厂类
"""
from src.factories.platform_factory import IMPlatformFactory
from src.factories.assistant_factory import AIAssistantFactory

__all__ = [
    "IMPlatformFactory",
    "AIAssistantFactory",
]
