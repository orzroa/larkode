"""
命令执行器（简化版）

负责命令的执行，移除了 Task 状态管理
"""
import asyncio
from pathlib import Path
from typing import Optional, AsyncGenerator

from src.config.settings import get_settings
from src.interfaces.ai_assistant import IAIAssistantInterface

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class TaskManager:
    """
    命令执行器（简化版）

    不再创建和追踪 Task，直接执行命令
    """

    def __init__(self, ai_assistant: Optional[IAIAssistantInterface] = None):
        """
        初始化命令执行器

        Args:
            ai_assistant: AI 助手接口实例，如果为 None 则使用 Claude Code
        """
        # 如果没有传入 AI 助手，根据配置创建后端。
        if ai_assistant is None:
            ai_assistant = self._create_default_assistant()

        self.ai_assistant = ai_assistant

    async def start(self):
        """启动当前 Agent 后端。"""
        start = getattr(self.ai_assistant, "start", None)
        if start:
            result = start()
            if asyncio.iscoroutine(result):
                await result
        logger.info("命令执行器已就绪")

    async def stop(self):
        """停止当前 Agent 后端。"""
        stop = getattr(self.ai_assistant, "stop", None)
        if stop:
            result = stop()
            if asyncio.iscoroutine(result):
                await result
        logger.info("命令执行器已停止")

    def _create_default_assistant(self) -> IAIAssistantInterface:
        """
        根据配置创建 Agent 后端

        Returns:
            AI 助手接口实例
        """
        backend = "claude_code"
        try:
            from src.factories.assistant_factory import AIAssistantFactory, AssistantType
            settings = get_settings()
            backend = settings.get_agent_backend()
            assistant_type = AssistantType(backend)

            if not AIAssistantFactory.is_assistant_registered(assistant_type):
                if assistant_type == AssistantType.CODEX:
                    from src.ai_assistants import register_codex_assistant
                    register_codex_assistant()
                else:
                    from src.ai_assistants import register_default_assistant
                    register_default_assistant()

            # 创建 AI 配置（不传入 workspace，由 AI 助手动态获取）
            from src.interfaces.ai_assistant import AssistantConfig
            from src.workspace_manager import get_workspace_manager

            config = AssistantConfig(
                assistant_type=assistant_type,
                workspace=None,  # 不固定 workspace，让 AI 助手动态获取
                cli_path=(
                    settings.CODEX_CLI_PATH
                    if assistant_type == AssistantType.CODEX
                    else settings.CLAUDE_CODE_CLI_PATH
                ),
                use_tmux_executor=True,  # 总是使用 tmux 模式
            )

            # 创建 AI 助手实例
            assistant = AIAssistantFactory.create_assistant(assistant_type, config)
            if assistant is None:
                if assistant_type == AssistantType.CODEX:
                    raise RuntimeError("无法创建 Codex 助手实例")
                logger.error("无法创建 Claude Code 助手实例，使用旧的实现")

                from src.ai_executor import AIInterface, TmuxAIExecutor
                tmux_executor = TmuxAIExecutor()  # 不固定 workspace，让执行器动态获取
                assistant = AIInterface()
                assistant.executor = tmux_executor

            return assistant

        except Exception as e:
            logger.error(f"创建默认助手失败: {e}", exc_info=True)

            # Codex 配置错误必须显式失败，不能静默启动 Claude Code。
            if backend == "codex":
                raise

            from src.ai_executor import AIInterface, TmuxAIExecutor

            # 创建不固定 workspace 的执行器
            tmux_executor = TmuxAIExecutor()
            assistant = AIInterface()
            assistant.executor = tmux_executor
            return assistant

    async def execute_command(self, user_id: str, command: str) -> AsyncGenerator[str, None]:
        """
        执行命令，流式返回输出

        Args:
            user_id: 用户 ID（用于日志追踪）
            command: 命令内容

        Yields:
            执行输出
        """
        logger.info(f"开始执行命令: {command[:50]}...")

        # 直接调用 AI 助手执行，不再创建 Task
        async for output in self.ai_assistant.execute_command(command, user_id):
            yield output

    def cancel(self) -> bool:
        """
        取消当前执行

        Returns:
            是否成功取消
        """
        return self.ai_assistant.cancel()

    async def cancel_async(self) -> bool:
        """等待后端确认取消请求；旧后端回退到同步 cancel。"""
        cancel_async = getattr(self.ai_assistant, "cancel_async", None)
        if cancel_async:
            return bool(await cancel_async())
        return self.cancel()

    def get_assistant_status(self) -> dict:
        """
        获取 AI 助手状态

        Returns:
            助手状态字典
        """
        return self.ai_assistant.get_status()


# 全局命令执行器实例
task_manager = TaskManager()
