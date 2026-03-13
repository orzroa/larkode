"""
命令执行器

负责命令的处理和执行
"""
import json
import os
from typing import Optional, TYPE_CHECKING, Any

from src.models import Message, MessageType, MessageDirection, MessageSource
from src.storage import db

# 避免循环导入
if TYPE_CHECKING:
    from src.interfaces.im_platform import IIMPlatform, IIMCardBuilder
    from src.card_dispatcher import CardDispatcher

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class CommandExecutor:
    """
    命令执行器

    负责处理和执行用户命令
    """

    def __init__(
        self,
        task_manager=None,
        card_builder: Optional["IIMCardBuilder"] = None,
        platform: Optional["IIMPlatform"] = None,
        feishu_api=None,
        message_sender=None,
        card_dispatcher: Optional["CardDispatcher"] = None,
    ):
        """
        初始化命令执行器

        Args:
            task_manager: 命令执行器（简化版，不再管理任务状态）
            card_builder: 卡片构建器（已废弃，保留兼容性）
            platform: IM 平台实例
            feishu_api: 飞书 API 实例
            message_sender: 消息发送器
            card_dispatcher: 卡片发送器（新架构）
        """
        self.tm = task_manager
        self.card_builder = card_builder
        self.platform = platform
        self.feishu = feishu_api
        self._message_sender = message_sender
        self.card_dispatcher = card_dispatcher
        self._current_platform: Optional[str] = None
        self._platform_commands = None

    def set_message_sender(self, sender) -> None:
        """设置消息发送器"""
        self._message_sender = sender

    def set_card_builder(self, card_builder: "IIMCardBuilder") -> None:
        """设置卡片构建器"""
        self.card_builder = card_builder

    def set_platform_commands(self, commands) -> None:
        """设置平台命令处理器"""
        self._platform_commands = commands

    def set_current_platform(self, platform_name: str) -> None:
        """设置当前平台"""
        self._current_platform = platform_name

    def _is_test_user(self, user_id: str) -> bool:
        """判断是否为测试用户"""
        return "test" in user_id.lower()

    async def process_command(self, user_id: str, command: str, message_id: str = None):
        """
        处理命令

        Args:
            user_id: 用户 ID
            command: 命令内容
            message_id: 飞书消息 ID
        """
        try:
            # 确定是否为平台命令
            is_platform_command = False
            if self.platform:
                is_platform_command = self.platform.is_platform_command(command)
            else:
                is_platform_command = command.startswith("#")

            if is_platform_command:
                # 平台系统命令 - 使用子处理器处理
                logger.info(f"识别为平台系统命令：{command}")
                if self._platform_commands:
                    await self._platform_commands.handle_command(user_id, command)
            else:
                # AI 助手命令 - 保存消息并执行
                logger.info(f"识别为 AI 助手命令：{command}")
                msg_id = None
                if message_id:
                    msg = Message(
                        user_id=user_id,
                        message_type=MessageType.COMMAND,
                        content=command,
                        direction=MessageDirection.UPSTREAM,
                        is_test=None,  # 使用全局测试模式
                        message_source=MessageSource.FEISHU,
                        feishu_message_id=message_id,
                    )
                    msg_id = db.save_message(msg)
                await self.execute_command(user_id, command, msg_id)

        except Exception as e:
            logger.error(f"处理命令时出错：{e}", exc_info=True)
            await self.send_error(user_id, f"命令处理失败：{str(e)}")

    async def execute_command(self, user_id: str, command: str, seq_id: Optional[int] = None):
        """
        执行 AI 助手 命令

        Args:
            user_id: 用户 ID
            command: 命令内容
            seq_id: 消息序列号（可选）
        """
        # 检查是否启用流式输出
        from src.config.settings import get_settings
        settings = get_settings()
        streaming_enabled = os.getenv("STREAMING_ENABLED", str(settings.STREAMING_ENABLED)).lower() == "true"

        # 流式输出管理器
        streaming_manager = None

        # 如果已有活跃的流式卡片，先停止它并添加说明
        global _current_streaming_manager
        if _current_streaming_manager is not None:
            try:
                await _current_streaming_manager.stop_with_message("**已停止更新，请查看最新响应卡片**")
            except Exception:
                pass
            _current_streaming_manager = None

        # 发送确认消息
        if self.card_dispatcher:
            if streaming_enabled:
                # 使用流式输出
                from src.streaming_output import StreamingOutputManager
                from src.feishu import FeishuAPI

                feishu = FeishuAPI(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)
                streaming_manager = StreamingOutputManager(
                    user_id=user_id,
                    feishu_api=feishu,
                    card_dispatcher=self.card_dispatcher
                )
                # 保存到全局变量，确保只有一个活跃的流式卡片
                _current_streaming_manager = streaming_manager
                # 创建初始卡片
                await streaming_manager.start(title="AI 响应中...", template_color="blue")
            else:
                # 普通模式
                from src.card_builder import UnifiedCardBuilder
                content = UnifiedCardBuilder.build_command_card(command)
                await self.card_dispatcher.send_card(
                    user_id=user_id,
                    card_type="command",
                    title="命令确认",
                    content=content,
                    message_type="response",
                    template_color="grey"
                )
        else:
            # Fallback to card_builder
            if self.card_builder:
                card = self.card_builder.create_command_card(command)
                await self._message_sender.send(user_id, card=card)

        # 定义流式回调
        async def streaming_callback(content: str, is_last: bool):
            if streaming_manager:
                await streaming_manager.on_chunk(content, is_last)

        # 执行命令
        try:
            # 如果有流式管理器，传递回调
            if streaming_manager:
                async for _ in self.tm.execute_command_streaming(user_id, command, streaming_callback):
                    pass
            else:
                async for _ in self.tm.execute_command(user_id, command):
                    pass  # 输出由 AI 助手处理
        except Exception as e:
            logger.error(f"执行命令失败：{e}", exc_info=True)
            await self.send_error(user_id, f"执行失败：{str(e)}")
        finally:
            # 关闭流式管理器
            if streaming_manager:
                await streaming_manager.close()
                if _current_streaming_manager is streaming_manager:
                    _current_streaming_manager = None

    async def send_error(self, user_id: str, error: str):
        """
        发送错误消息

        Args:
            user_id: 用户 ID
            error: 错误信息
        """
        if self._message_sender:
            await self._message_sender.send_error(user_id, error)


# 全局命令执行器实例（需要外部初始化）
command_executor: Optional[CommandExecutor] = None

# 全局流式输出管理器（确保只有一个活跃的流式卡片）
_current_streaming_manager: Optional[Any] = None