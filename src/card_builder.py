"""
统一卡片构建器 - 只构建业务内容，不包含元数据

此模块提供简单的静态方法来构建各种类型的卡片内容。
所有返回的内容都是纯文本，不包含卡片编号和时间戳。
元数据（编号和时间）由 NormalizedCard 或 CardDispatcher 统一管理。

注意：这是新的简化版本，与 src/interfaces/card_builder.py 中的 IIMCardBuilder 接口不同。
IIMCardBuilder 返回 NormalizedCard，而这里的 UnifiedCardBuilder 只返回纯内容字符串。
"""
from typing import Tuple


class UnifiedCardBuilder:
    """统一卡片构建器 - 只构建纯内容"""

    @staticmethod
    def build_command_card(command: str) -> str:
        """构建命令确认卡片内容

        Args:
            command: 执行的命令

        Returns:
            str: 纯内容
        """
        return f"命令: `{command}`\n状态: 开始处理..."

    @staticmethod
    def build_output_card(output: str, title: str = "输出") -> str:
        """构建输出显示卡片内容

        Args:
            output: 输出内容
            title: 标题（仅在需要时使用）

        Returns:
            str: 纯内容
        """
        return f"{title}:\n\n```\n{output}\n```"

    @staticmethod
    def build_error_card(error: str) -> str:
        """构建错误卡片内容

        Args:
            error: 错误信息

        Returns:
            str: 纯内容
        """
        return f"错误: {error}"

    @staticmethod
    def build_text_card(text: str) -> str:
        """构建文本卡片内容

        Args:
            text: 文本内容

        Returns:
            str: 纯内容
        """
        return text

    @staticmethod
    def build_help_card(help_text: str) -> str:
        """构建帮助卡片内容

        Args:
            help_text: 帮助文本

        Returns:
            str: 纯内容
        """
        return help_text

    @staticmethod
    def build_history_card(history_text: str) -> str:
        """构建历史记录卡片内容

        Args:
            history_text: 历史记录文本

        Returns:
            str: 纯内容
        """
        return history_text

    @staticmethod
    def build_cancel_card(message: str) -> str:
        """构建取消确认卡片内容

        Args:
            message: 消息内容

        Returns:
            str: 纯内容
        """
        return message

    @staticmethod
    def build_download_image_card(message: str) -> str:
        """构建下载图片确认卡片内容

        Args:
            message: 消息内容

        Returns:
            str: 纯内容
        """
        return message

    @staticmethod
    def build_download_voice_card(message: str) -> str:
        """构建下载语音确认卡片内容

        Args:
            message: 消息内容

        Returns:
            str: 纯内容
        """
        return message

    @staticmethod
    def build_file_notification_card(file_name: str) -> str:
        """构建文件通知卡片内容

        Args:
            file_name: 文件名

        Returns:
            str: 纯内容
        """
        return f"完整内容已保存为文件: `{file_name}`"

    @staticmethod
    def build_tmux_card(output: str) -> str:
        """构建截屏卡片内容

        Args:
            output: tmux 输出内容

        Returns:
            str: 纯内容
        """
        return f"屏幕内容:\n\n```\n{output}\n```"

    @staticmethod
    def build_status_card(task_dicts: list) -> str:
        """构建状态卡片内容

        Args:
            task_dicts: 任务字典列表

        Returns:
            str: 纯内容
        """
        if not task_dicts:
            return "没有正在运行的任务"

        content_parts = ["最近任务状态："]
        for task in task_dicts:
            command = task.get("command", "未知命令")
            status = task.get("status", "未知")
            created_at = task.get("created_at", "")
            content_parts.append(f"- `{command}`: {status} ({created_at})")

        return "\n".join(content_parts)


# 便捷函数，保持与旧代码的兼容性
def create_command_card(command: str) -> str:
    """创建命令确认卡片内容"""
    return UnifiedCardBuilder.build_command_card(command)


def create_output_card(output: str, title: str = "输出") -> str:
    """创建输出卡片内容"""
    return UnifiedCardBuilder.build_output_card(output, title)


def create_error_card(error: str) -> str:
    """创建错误卡片内容"""
    return UnifiedCardBuilder.build_error_card(error)


def create_help_card(help_text: str) -> str:
    """创建帮助卡片内容"""
    return UnifiedCardBuilder.build_help_card(help_text)


def create_history_card(history_text: str) -> str:
    """创建历史记录卡片内容"""
    return UnifiedCardBuilder.build_history_card(history_text)


def create_cancel_card(message: str) -> str:
    """创建取消确认卡片内容"""
    return UnifiedCardBuilder.build_cancel_card(message)


def create_download_image_card(message: str) -> str:
    """创建下载图片确认卡片内容"""
    return UnifiedCardBuilder.build_download_image_card(message)


def create_download_voice_card(message: str) -> str:
    """创建下载语音确认卡片内容"""
    return UnifiedCardBuilder.build_download_voice_card(message)


def create_tmux_card(output: str) -> str:
    """创建截屏卡片内容"""
    return UnifiedCardBuilder.build_tmux_card(output)


def create_status_card(task_dicts: list) -> str:
    """创建状态卡片内容"""
    return UnifiedCardBuilder.build_status_card(task_dicts)