"""
AI 助手执行器接口
"""
import asyncio
import os
import subprocess
import time
import psutil
from pathlib import Path
from typing import Optional, AsyncGenerator

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# 导出基础类
from src.ai_executor.base import AIExecutor
from src.ai_executor.tmux_session import TmuxSessionManager
from src.ai_executor.process_monitor import ProcessMonitor
from src.ai_executor.interface import AIInterface, AILogReader

# 导出 subprocess, time, psutil 以保持测试兼容
__all__ = ['subprocess', 'time', 'psutil']


class TmuxAIExecutor:
    """
    通过 tmux 发送命令到 AI session
    保持完整的上下文和对话历史
    """

    TMUX_SESSION_NAME = "cc"

    def __init__(self, workspace: Optional[Path] = None):
        # 初始化会话管理器
        self._session_manager = TmuxSessionManager(workspace)

        # 暴露 workspace 属性（兼容旧代码）
        self.workspace = self._session_manager.workspace

        # 自动重启配置（保持直接属性访问，兼容测试）
        self._auto_restart_enabled = get_settings().AI_AUTO_RESTART_ENABLED
        self._max_restart_attempts = get_settings().AI_MAX_RESTART_ATTEMPTS
        self._restart_delay = get_settings().AI_RESTART_DELAY
        self._restart_count = 0

        self._formatted_results: dict = {}
        self._did_restart_ai = False

    def _check_tmux_session(self) -> bool:
        return self._session_manager._check_tmux_session()

    def _check_ai_running_in_session(self) -> bool:
        return self._session_manager._check_ai_running_in_session()

    def _create_tmux_session(self) -> bool:
        return self._session_manager._create_tmux_session()

    def _ensure_tmux_session(self) -> tuple[bool, bool]:
        return self._session_manager._ensure_tmux_session()

    def _start_ai_in_existing_session(self) -> bool:
        return self._session_manager._start_ai_in_existing_session()

    def _check_ai_process_health(self) -> bool:
        """检查 AI 进程健康状态"""
        if not self._check_tmux_session():
            logger.warning(f"tmux session '{self._session_manager._tmux_session}' 不存在")
            return False
        if not self._check_ai_running_in_session():
            logger.warning(f"AI 进程在 tmux session '{self._session_manager._tmux_session}' 中未运行")
            return False
        return True

    def _monitor_and_restart_if_needed(self) -> bool:
        """监控并按需重启 AI"""
        # 如果自动重启功能未启用，直接返回
        if not self._auto_restart_enabled:
            return False

        # 检查进程健康状态
        if self._check_ai_process_health():
            # 进程健康，重置重启计数
            self._restart_count = 0
            return False

        # 进程崩溃，检查是否达到最大重启次数
        if self._restart_count >= self._max_restart_attempts:
            logger.error(f"AI 崩溃次数达到上限 ({self._max_restart_attempts})，停止自动重启")
            return False

        # 尝试重启 AI
        logger.warning(f"检测到 AI 进程崩溃，尝试重启（第 {self._restart_count + 1}/{self._max_restart_attempts} 次）")
        time.sleep(self._restart_delay)

        # 使用 _ensure_tmux_session 来决定是创建新 session 还是在现有 session 中启动 AI
        # 这样如果 tmux 存在但 AI 不在，只会启动 AI，不会杀掉 tmux
        success, just_started = self._ensure_tmux_session()
        if success:
            self._restart_count += 1
            if just_started:
                logger.info(f"AI 进程重启成功（第 {self._restart_count} 次）")
            return True
        else:
            logger.error("AI 进程重启失败")
            return False

    async def execute_command(
        self,
        command: str,
        workspace: Optional[Path] = None,
        streaming_callback=None,
    ) -> AsyncGenerator[str, None]:
        """
        执行命令（通过 tmux）

        Args:
            command: 要执行的命令
            workspace: 工作目录
            streaming_callback: 流式回调函数，签名: callback(content: str, is_last: bool) -> None

        Yields:
            str: 命令输出
        """
        work_dir = workspace or self.workspace

        if not work_dir or not work_dir.exists():
            yield f"错误: 工作目录不存在: {work_dir}"
            return

        logger.info(f"开始 tmux 执行命令: {command}")

        output_lines = []
        try:
            # 检查是否需要重启 AI（执行前），并获取是否刚刚启动了 AI
            just_started = False
            if self._auto_restart_enabled:
                success, just_started = self._session_manager._ensure_tmux_session()
                if not success:
                    yield "错误: 无法创建 tmux session"
                    return
                if just_started:
                    yield "⚠️ 检测到 AI 进程未运行，已自动启动"
                    yield ""
                    # 等待 AI 完全初始化
                    logger.info("  → 等待 AI 初始化...")
                    time.sleep(5)

            # 发送命令到 tmux
            async for output in self._session_manager.send_command(command, skip_ensure=True):
                output_lines.append(output)
                yield output

            # 如果有流式回调，启动异步输出捕获并等待完成
            if streaming_callback:
                logger.info("启动异步流式输出捕获并等待完成")
                import asyncio

                # 立即开始捕获，不需要等待 AI 输出
                await self._session_manager.capture_output_async(
                    streaming_callback,
                    0.3,  # poll_interval
                    300.0,  # max_wait
                )

            # 生成格式化摘要
            formatted_result = '\n'.join(output_lines)
            max_length = int(os.getenv("CARD_MAX_LENGTH", str(get_settings().CARD_MAX_LENGTH)))
            if len(formatted_result) > max_length:
                formatted_result = formatted_result[:max_length] + "\n... (内容过长，已截断)"

        except Exception as e:
            logger.error(f"tmux 执行命令时出错: {e}", exc_info=True)
            yield f"\n执行出错: {str(e)}"

    def cancel_task(self, task_id: str) -> bool:
        """取消当前执行"""
        logger.info(f"tmux 模式下取消执行")
        return False

    def is_task_running(self, task_id: str) -> bool:
        """检查是否在执行"""
        return False


# 别名（兼容旧代码）
TmuxClaudeCodeExecutor = TmuxAIExecutor
ClaudeCodeInterface = AIInterface
ClaudeCodeLogReader = AILogReader