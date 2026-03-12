"""
卡片构建器接口定义（编号统一在内部生成）
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Tuple


class CardBuilderInterface(ABC):
    """卡片构建器接口"""

    @abstractmethod
    def create_command_card(self, command: str, message_number: str) -> str:
        """
        创建命令确认卡片

        Args:
            command: 执行的命令
            message_number: 消息编号

        Returns:
            str: 飞书卡片 JSON 字符串
        """
        pass

    @abstractmethod
    def create_tmux_card(self, output: str) -> Tuple[str, bool, str]:
        """
        创建截屏卡片

        Args:
            output: tmux 输出内容

        Returns:
            Tuple: (card_json, need_file, file_content)
                - card_json: 卡片 JSON 字符串
                - need_file: 是否需要发送文件
                - file_content: 需要写入文件的内容（如果 need_file 为 True）
        """
        pass

    @abstractmethod
    def create_error_card(self, error: str) -> str:
        """
        创建错误卡片

        Args:
            error: 错误信息

        Returns:
            str: 飞书卡片 JSON 字符串
        """
        pass

    @abstractmethod
    def create_help_card(self, help_text: str) -> str:
        """
        创建帮助卡片

        Args:
            help_text: 帮助文本

        Returns:
            str: 飞书卡片 JSON 字符串
        """
        pass

    @abstractmethod
    def create_history_card(self, history_text: str) -> str:
        """
        创建历史记录卡片

        Args:
            history_text: 历史记录文本

        Returns:
            str: 飞书卡片 JSON 字符串
        """
        pass

    @abstractmethod
    def create_cancel_card(self, message: str) -> str:
        """
        创建取消确认卡片

        Args:
            message: 消息内容

        Returns:
            str: 飞书卡片 JSON 字符串
        """
        pass

    @abstractmethod
    def create_download_image_card(self, message: str) -> str:
        """
        创建下载图片确认卡片

        Args:
            message: 消息内容

        Returns:
            str: 飞书卡片 JSON 字符串
        """
        pass