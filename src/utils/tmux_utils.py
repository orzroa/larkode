"""
Tmux 工具函数
"""
import subprocess

from src.config.settings import get_settings
from src.utils.text_utils import clean_tmux_output

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


def get_tmux_last_lines(lines: int = 200) -> str:
    """
    获取 tmux pane 的最后几行输出

    使用 tmux capture-pane -S -<行数> 直接获取最后 N 行

    Args:
        lines: 获取的行数（默认200）

    Returns:
        str: 清理后的 tmux 输出
    """
    try:
        session_name = get_settings().TMUX_SESSION_NAME or "cc"

        # 使用 -S -<行数> 直接获取最后 N 行
        capture_cmd = [
            "tmux", "capture-pane", "-p", "-t",
            f"{session_name}", "-e", "-S", f"-{lines}"
        ]
        result = subprocess.run(capture_cmd, capture_output=True, text=True)

        if not result.stdout:
            return "tmux 无输出"

        # 使用通用函数清理输出
        output = clean_tmux_output(result.stdout)

        # 移除空行
        lines_list = [l for l in output.strip().split('\n') if l.strip()]

        return '\n'.join(lines_list)

    except Exception as e:
        logger.error(f"读取 tmux 输出失败: {e}")
        return f"读取失败: {str(e)}"
