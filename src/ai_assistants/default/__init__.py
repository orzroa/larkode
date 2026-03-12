"""
Default AI 助手实现

实现 IAIAssistantInterface 接口，提供 AI 助手的命令执行功能
"""
# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

import asyncio
from typing import AsyncGenerator, Optional, Dict, Any
from pathlib import Path

from src.interfaces.ai_assistant import (
    IAIAssistantInterface,
    ISessionManager,
    SessionStatus,
    AssistantConfig,
    SessionInfo,
)
from src.ai_executor import TmuxAIExecutor
from src.ai_session_manager import AISessionManager
from src.config.settings import Config, get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class DefaultSessionManager(ISessionManager):
    """Default AI 会话管理器实现"""

    def __init__(self, config: AssistantConfig):
        self.config = config
        self._session_manager = AISessionManager()

    def find_running_session(self) -> Optional[SessionInfo]:
        """查找当前运行的会话"""
        try:
            session_id = self._session_manager.find_running_session()
            if session_id:
                return SessionInfo(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE,
                    workspace=self.config.workspace
                )
            return None
        except Exception as e:
            logger.error(f"查找运行中的会话失败: {e}", exc_info=True)
            return None

    def ensure_session(self) -> Optional[SessionInfo]:
        """确保有可用会话"""
        try:
            session_id = self._session_manager.get_session()
            if session_id:
                return SessionInfo(
                    session_id=session_id,
                    status=SessionStatus.ACTIVE,
                    workspace=self.config.workspace
                )
            return None
        except Exception as e:
            logger.error(f"确保会话失败: {e}", exc_info=True)
            return None


class DefaultAIInterface(IAIAssistantInterface):
    """Default AI 高级接口实现"""

    def __init__(self, config: AssistantConfig, use_tmux_executor: bool = True):
        """
        初始化 Default AI 接口

        Args:
            config: 助手配置
            use_tmux_executor: 是否使用 tmux 执行器（默认 True）
        """
        self.config = config
        self.use_tmux_executor = use_tmux_executor

        # 创建会话管理器
        self.session_manager = DefaultSessionManager(config)

        # 确保有会话
        session_info = self.session_manager.ensure_session()
        if session_info:
            logger.info(f"使用 AI 会话: {session_info.session_id}")

        # 创建执行器（总是使用 tmux 模式）
        workspace = config.workspace or get_settings().CLAUDE_CODE_WORKSPACE_DIR
        self.executor = TmuxAIExecutor(workspace)

        self._is_running = False

    async def execute_command(
        self,
        command: str,
    ) -> AsyncGenerator[str, None]:
        """
        执行命令并流式输出

        Args:
            command: 要执行的命令

        Yields:
            str: 命令输出
        """
        logger.info(f"开始执行命令: {command}")

        self._is_running = True
        try:
            async for output in self.executor.execute_command(
                command,
                self.config.workspace
            ):
                yield output

        except Exception as e:
            logger.error(f"执行命令时出错: {e}", exc_info=True)
            yield f"\n执行出错: {str(e)}"
        finally:
            self._is_running = False

    def cancel(self) -> bool:
        """取消当前执行"""
        try:
            result = self.executor.cancel_task("current")
            logger.info(f"已尝试取消执行")
            return result
        except Exception as e:
            logger.error(f"取消执行失败: {e}", exc_info=True)
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取助手状态"""
        try:
            session_info = self.session_manager.find_running_session()

            return {
                "assistant_type": "default",
                "session_id": session_info.session_id if session_info else None,
                "session_status": session_info.status.value if session_info else SessionStatus.INACTIVE.value,
                "workspace": str(self.config.workspace),
                "executor_type": "tmux" if self.use_tmux_executor else "direct",
                "is_running": self._is_running,
                "config": self.config.to_dict(),
            }
        except Exception as e:
            logger.error(f"获取状态失败: {e}", exc_info=True)
            return {
                "assistant_type": "default",
                "error": str(e)
            }


def register_default_assistant():
    """注册 Default AI 助手到工厂"""
    from src.factories.assistant_factory import AIAssistantFactory, AssistantType

    def create_default_assistant(config: AssistantConfig) -> DefaultAIInterface:
        """创建 Default AI 助手实例的工厂函数"""
        use_tmux = config.extra.get("use_tmux_executor", True)
        return DefaultAIInterface(config, use_tmux_executor=use_tmux)

    # 注册助手（同时注册 default 和 claude_code 两个类型）
    AIAssistantFactory.register_assistant(AssistantType.DEFAULT, create_default_assistant)
    AIAssistantFactory.register_assistant(AssistantType.CLAUDE_CODE, create_default_assistant)


ClaudeCodeSessionManager = DefaultSessionManager
ClaudeCodeInterface = DefaultAIInterface