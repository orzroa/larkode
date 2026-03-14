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
        # 如果没有传入 AI 助手，使用 Claude Code
        if ai_assistant is None:
            ai_assistant = self._create_default_assistant()

        self.ai_assistant = ai_assistant

    async def start(self):
        """启动（兼容接口，无需操作）"""
        logger.info("命令执行器已就绪")

    async def stop(self):
        """停止（兼容接口，无需操作）"""
        logger.info("命令执行器已停止")

    def _create_default_assistant(self) -> IAIAssistantInterface:
        """
        创建默认的 AI 助手（Claude Code）

        Returns:
            AI 助手接口实例
        """
        try:
            # 注册 Claude Code 助手（如果尚未注册）
            from src.factories.assistant_factory import AIAssistantFactory, AssistantType

            if not AIAssistantFactory.is_assistant_registered(AssistantType.DEFAULT):
                from src.ai_assistants import register_default_assistant
                register_default_assistant()

            # 创建 AI 配置
            from src.interfaces.ai_assistant import AssistantConfig
            workspace = Path(get_settings().CLAUDE_CODE_WORKSPACE_DIR) if get_settings().CLAUDE_CODE_WORKSPACE_DIR else Path.cwd()

            config = AssistantConfig(
                assistant_type=AssistantType.DEFAULT,
                workspace=workspace,
                cli_path=get_settings().CLAUDE_CODE_CLI_PATH,
                use_tmux_executor=True,  # 总是使用 tmux 模式
            )

            # 创建 AI 助手实例
            assistant = AIAssistantFactory.create_assistant(AssistantType.DEFAULT, config)
            if assistant is None:
                logger.error("无法创建 AI 助手实例，使用旧的实现")

                from src.ai_executor import AIInterface, TmuxAIExecutor
                tmux_executor = TmuxAIExecutor(workspace)
                assistant = AIInterface()
                assistant.executor = tmux_executor

            return assistant

        except Exception as e:
            logger.error(f"创建默认助手失败: {e}", exc_info=True)

            from src.ai_executor import AIInterface, TmuxAIExecutor
            workspace = Path(get_settings().CLAUDE_CODE_WORKSPACE_DIR) if get_settings().CLAUDE_CODE_WORKSPACE_DIR else Path.cwd()
            tmux_executor = TmuxAIExecutor(workspace)
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

    def get_assistant_status(self) -> dict:
        """
        获取 AI 助手状态

        Returns:
            助手状态字典
        """
        return self.ai_assistant.get_status()


# 全局命令执行器实例
task_manager = TaskManager()