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
from src.ai_executor.interface import AIInterface

# 导出 subprocess, time, psutil 以保持测试兼容
__all__ = ['subprocess', 'time', 'psutil']


class TmuxAIExecutor:
    """
    通过 tmux 发送命令到 AI session
    保持完整的上下文和对话历史

    特性：
    - 动态获取当前工作空间，支持工作空间切换
    - 自动重启崩溃的 AI 进程
    - 支持流式输出和传统输出模式
    """

    def __init__(self, workspace: Optional[Path] = None):
        """
        初始化执行器

        Args:
            workspace: 工作空间路径（可选，不提供则动态获取当前工作空间）
        """
        # 不在初始化时固定 workspace，而是动态获取
        self._initial_workspace = workspace

        # 初始化会话管理器（延迟初始化，在执行时才创建）
        self._session_manager: Optional[TmuxSessionManager] = None

        # 自动重启配置
        self._auto_restart_enabled = get_settings().AI_AUTO_RESTART_ENABLED
        self._max_restart_attempts = get_settings().AI_MAX_RESTART_ATTEMPTS
        self._restart_delay = get_settings().AI_RESTART_DELAY
        self._restart_count = 0

        self._formatted_results: dict = {}
        self._did_restart_ai = False

    def _get_current_workspace(self) -> Path:
        """
        获取当前工作空间路径

        总是动态获取当前工作空间，忽略初始化时传入的 workspace

        Returns:
            Path: 工作空间路径
        """
        # 优先从 WorkspaceManager 动态获取当前工作空间
        try:
            from src.workspace_manager import get_workspace_manager
            workspace_manager = get_workspace_manager()
            current_workspace = workspace_manager.get_current_workspace()
            if current_workspace:
                logger.info(f"从 WorkspaceManager 获取到当前工作空间: {current_workspace}")
                return Path(current_workspace)
            else:
                logger.warning("WorkspaceManager 返回空的工作空间")
        except Exception as e:
            # 获取失败时记录错误（测试环境可能没有 WorkspaceManager）
            logger.error(f"从 WorkspaceManager 获取工作空间失败: {e}", exc_info=True)

        # Fallback: 如果动态获取失败，使用初始化时传入的 workspace
        if self._initial_workspace:
            logger.warning(f"使用初始化时的工作空间作为 fallback: {self._initial_workspace}")
            return self._initial_workspace

        # Final fallback: 当前工作目录
        logger.warning(f"使用当前工作目录作为 fallback: {Path.cwd()}")
        return Path.cwd()

    def _get_session_manager(self) -> TmuxSessionManager:
        """
        获取当前工作空间对应的 session 管理器

        Returns:
            TmuxSessionManager: session 管理器实例
        """
        current_workspace = self._get_current_workspace()
        return TmuxSessionManager(workspace=current_workspace)

    @property
    def workspace(self) -> Path:
        """工作空间属性（兼容旧代码）"""
        return self._get_current_workspace()

    def _check_tmux_session(self) -> bool:
        return self._get_session_manager()._check_tmux_session()

    def _check_ai_running_in_session(self) -> bool:
        return self._get_session_manager()._check_ai_running_in_session()

    def _create_tmux_session(self) -> bool:
        return self._get_session_manager()._create_tmux_session()

    def _ensure_tmux_session(self) -> tuple[bool, bool]:
        return self._get_session_manager()._ensure_tmux_session()

    def _start_ai_in_existing_session(self) -> bool:
        return self._get_session_manager()._start_ai_in_existing_session()

    def _check_ai_process_health(self) -> bool:
        """检查 AI 进程健康状态"""
        session_manager = self._get_session_manager()
        if not session_manager._check_tmux_session():
            logger.warning(f"tmux session '{session_manager._tmux_session}' 不存在")
            return False
        if not session_manager._check_ai_running_in_session():
            logger.warning(f"AI 进程在 tmux session '{session_manager._tmux_session}' 中未运行")
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
        streaming: bool = False,
        streaming_manager = None,
        user_id: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        执行命令（通过 tmux）

        Args:
            command: 要执行的命令
            workspace: 工作目录（可选，不提供则使用当前工作空间）
            streaming: 是否启用流式输出
            streaming_manager: 流式输出管理器 (StreamingOutputManager)
            user_id: 用户 ID（流式输出需要）

        Yields:
            str: 命令输出
        """
        # 使用指定的 workspace 或当前工作空间
        work_dir = workspace or self.workspace
        if not work_dir or not work_dir.exists():
            yield f"错误: 工作目录不存在: {work_dir}"
            return

        # 获取当前工作空间对应的 session 管理器
        session_manager = TmuxSessionManager(workspace=work_dir)

        # 打印关键信息
        logger.info(f"========== 命令执行信息 ==========")
        logger.info(f"命令: {command}")
        logger.info(f"工作空间: {work_dir}")
        logger.info(f"Session 名称: {session_manager._tmux_session}")
        logger.info(f"==================================")

        logger.info(f"开始 tmux 执行命令: {command}")

        # 流式输出模式
        if streaming and streaming_manager and user_id:
            logger.info("启用流式输出模式")

            try:
                # 确保 session 存在
                just_started = False
                if self._auto_restart_enabled:
                    success, just_started = session_manager._ensure_tmux_session()
                    if not success:
                        yield "错误: 无法创建 tmux session"
                        return
                    if just_started:
                        yield "⚠️ 检测到 AI 进程未运行，已自动启动"
                        yield ""
                        logger.info("  → 等待 AI 初始化...")
                        time.sleep(5)

                # 创建卡片实体
                card_id = await streaming_manager.start_streaming(
                    user_id,
                    "正在处理...",
                    title="命令处理",
                    template_color="blue"
                )

                if card_id:
                    # 发送命令
                    async for output in session_manager.send_command(command, skip_ensure=True):
                        # 不 yield 输出，因为会通过卡片实时显示
                        pass

                    # 创建监控任务
                    async def run_monitor():
                        try:
                            final_output = await session_manager.monitor_output(
                                callback=lambda content, is_last: asyncio.create_task(
                                    streaming_manager.finish_streaming(card_id, content)
                                ) if is_last else asyncio.create_task(
                                    streaming_manager.update_content(card_id, content)
                                ),
                                timeout=get_settings().streaming_timeout
                            )
                            return final_output
                        except asyncio.CancelledError:
                            logger.info(f"监控任务被取消: {card_id}")
                            raise

                    # 启动监控任务
                    monitor_task = asyncio.create_task(run_monitor())

                    # 注册监控任务（用于后续取消）
                    streaming_manager.register_monitor_task(monitor_task)

                    # 等待监控任务完成
                    try:
                        final_output = await monitor_task
                    except asyncio.CancelledError:
                        logger.info(f"监控任务已取消，跳过后续处理")
                        return

                    # 设置环境变量，通知 Hook 跳过发送
                    os.environ["LARKODE_STREAMING_MODE"] = card_id

                    yield f"命令已发送到 AI，正在实时显示结果"

                else:
                    # 卡片创建失败，降级到传统模式
                    logger.warning("卡片创建失败，降级到传统模式")
                    async for output in session_manager.send_command(command, skip_ensure=True):
                        yield output

            except Exception as e:
                logger.error(f"流式输出执行时出错: {e}", exc_info=True)
                yield f"\n执行出错: {str(e)}"

        # 传统模式
        else:
            output_lines = []
            try:
                # 检查是否需要重启 AI（执行前），并获取是否刚刚启动了 AI
                just_started = False
                if self._auto_restart_enabled:
                    success, just_started = session_manager._ensure_tmux_session()
                    if not success:
                        yield "错误: 无法创建 tmux session"
                        return
                    if just_started:
                        yield "⚠️ 检测到 AI 进程未运行，已自动启动"
                        yield ""
                        # 等待 AI 完全初始化
                        logger.info("  → 等待 AI 初始化...")
                        time.sleep(5)

                async for output in session_manager.send_command(command, skip_ensure=True):
                    output_lines.append(output)
                    yield output

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


# 别名（测试中使用）
TmuxClaudeCodeExecutor = TmuxAIExecutor