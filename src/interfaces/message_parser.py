"""
消息解析接口定义
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class MessageParserInterface(ABC):
    """消息解析器接口"""

    @abstractmethod
    def parse_message(self, event_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        解析飞书消息事件

        Args:
            event_data: 原始事件数据

        Returns:
            Dict: 包含用户ID、消息内容、消息ID等信息的字典
            None: 如果数据不完整
        """
        pass

    @abstractmethod
    def is_slash_command(self, content: str) -> bool:
        """判断是否是斜杠命令"""
        pass

    @abstractmethod
    def parse_command(self, command: str) -> Dict[str, Any]:
        """
        解析命令

        Args:
            command: 命令字符串

        Returns:
            Dict: 包含命令类型和参数的字典
                {
                    "command": str,  # 命令名（如 /status）
                    "args": str,     # 参数字符串
                    "full_command": str  # 完整命令
                }
        """
        pass