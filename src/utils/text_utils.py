"""
文本处理工具函数
"""
import re

# ANSI 转义序列正则表达式
ANSI_ESCAPE = re.compile(r'\x1B\[[0-?;]*[0-?]*m')
ANSI_ESCAPE_EXTENDED = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def clean_ansi_codes(text: str) -> str:
    """清理 ANSI 转义序列

    Args:
        text: 包含 ANSI 转义序列的文本

    Returns:
        str: 清理后的文本
    """
    return ANSI_ESCAPE.sub('', text)


def clean_ansi_codes_extended(text: str) -> str:
    """清理 ANSI 转义序列（扩展版本，支持更多序列）

    Args:
        text: 包含 ANSI 转义序列的文本

    Returns:
        str: 清理后的文本
    """
    return ANSI_ESCAPE_EXTENDED.sub('', text)


def clean_tmux_output(output: str) -> str:
    """清理 tmux 输出中的控制字符

    Args:
        output: tmux 原始输出

    Returns:
        str: 清理后的输出
    """
    # 清理 ANSI 转义序列
    output = clean_ansi_codes(output)

    # 移除 tmux 特有的标记
    output = output.replace('\x1b[?2004l', '')
    output = output.replace('\x0f', '')

    return output.strip()
