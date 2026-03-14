"""
AI 高级接口和日志读取器
"""
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class AIInterface:
    """AI 高级接口"""

    def __init__(self, workspace: Optional[Path] = None, session_id: Optional[str] = None):
        # 延迟导入，避免循环依赖
        from src.ai_executor.base import AIExecutor
        self.executor = AIExecutor(workspace)

    async def execute_command(self, command: str, session_id: Optional[str] = None) -> tuple[bool, str]:
        """
        执行命令并返回结果

        Args:
            command: 命令内容
            session_id: 可选的 session ID，用于动态设置 executor 的 session

        Returns:
            (是否成功, 结果)
        """
        result_lines = []

        try:
            # 如果传入了 session_id 且 executor 支持，设置它
            if session_id and hasattr(self.executor, '_session_id'):
                self.executor._session_id = session_id

            async for output in self.executor.execute_command(command):
                result_lines.append(output)

            full_result = "\n".join(result_lines)

            # 获取格式化的结果（如果有）
            formatted_result = full_result
            if hasattr(self.executor, '_formatted_results'):
                # 使用第一个可用的格式化结果
                if self.executor._formatted_results:
                    _, formatted_result = self.executor._formatted_results.popitem()

            return True, formatted_result

        except Exception as e:
            error_msg = str(e)
            logger.error(f"命令执行失败: {error_msg}", exc_info=True)
            return False, error_msg

    def cancel(self) -> bool:
        """取消当前执行"""
        return self.executor.cancel_task("current")

    def is_running(self) -> bool:
        """检查是否在执行"""
        return self.executor.is_task_running("current")