"""
平台命令处理器
处理 #help, #cancel, #history, #shot, #model 等平台命令
未识别的命令返回 False
"""
import json
import os
import subprocess
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from src.handlers.ccr_commands import CCRCommands
from src.handlers.workspace_commands import WorkspaceCommands
from src.config.settings import get_settings
# 避免循环导入
if TYPE_CHECKING:
    from src.interfaces.im_platform import IIMCardBuilder, NormalizedCard
    from src.im_platforms.notification_sender import INotificationSender
    from src.task_manager import TaskManager
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
class PlatformCommands:
    """平台命令处理器"""
    def __init__(
        self,
        task_manager: "TaskManager",
        card_builder: Optional["IIMCardBuilder"] = None,
        feishu=None,
        send_via_sender=None,
        card_dispatcher: Optional["CardDispatcher"] = None,
    ):
        """
        初始化平台命令处理器
        Args:
            task_manager: 任务管理器实例
            card_builder: 卡片构建器实例（已废弃，保留兼容性）
            feishu: 飞书 API 实例
            send_via_sender: 发送消息的回调函数
            card_dispatcher: 卡片发送器（新架构）
        """
        self.tm = task_manager
        self.card_builder = card_builder
        self.feishu = feishu
        self._send_via_sender = send_via_sender
        self.card_dispatcher = card_dispatcher
    def set_send_callback(self, send_via_sender):
        """设置发送回调函数"""
        self._send_via_sender = send_via_sender
    async def handle_command(self, user_id: str, command: str) -> bool:
        """
        处理平台系统命令
        Args:
            user_id: 用户 ID
            command: 命令内容
        Returns:
            bool: True 表示已识别并处理，False 表示未识别（上游应转为 AI 命令）
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        match cmd:
            case "#help":
                await self._cmd_help(user_id)
            case "#cancel":
                await self._cmd_cancel(user_id, args)
            case "#history":
                await self._cmd_history(user_id, args)
            case "#shot":
                await self._cmd_shot(user_id, args)
            case "#model":
                await self._cmd_model(user_id, args)
            case "#ws":
                await self._cmd_workspace(user_id, args)
            case "#mm":
                await self._cmd_minimax(user_id, args)
            case _:
                return False
        return True

    async def _cmd_model(self, user_id: str, args: str):
        """处理 #model 命令 - CCR 模型切换"""
        ccr = CCRCommands()
        await ccr.handle_model_command(user_id, args, self._send_via_sender)

    async def _cmd_workspace(self, user_id: str, args: str):
        """处理 #ws 命令 - 工作空间切换"""
        workspace_cmd = WorkspaceCommands()
        await workspace_cmd.handle_workspace_command(
            user_id, args, self._send_via_sender
        )

    async def _cmd_minimax(self, user_id: str, args: str):
        """处理 #mm 命令 - MiniMax 多媒体"""
        from src.config.settings import get_settings

        settings = get_settings()
        if not settings.minimax_enabled:
            await self._send_error(user_id, "MiniMax 功能未启用")
            return
        if not settings.minimax_api_key:
            await self._send_error(user_id, "MiniMax API Key 未配置，请设置 MINIMAX_API_KEY 环境变量")
            return

        try:
            from src.minimax.client import get_minimax_client
            from src.minimax.feishu_delivery import MiniMaxFeishuDelivery
            from src.minimax.commands import MiniMaxCommands

            client = get_minimax_client()
            delivery = MiniMaxFeishuDelivery(self.feishu, self.card_dispatcher)

            mm_commands = MiniMaxCommands(
                client=client,
                delivery=delivery,
            )

            await mm_commands.handle_command(user_id, args)

        except Exception as e:
            logger.error(f"处理 MiniMax 命令失败: {e}", exc_info=True)
            await self._send_error(user_id, f"MiniMax 命令处理失败: {e}")

    async def _cmd_help(self, user_id: str):
        """显示帮助信息"""
        help_text = """


---

📝 **执行 Claude Code 命令**
直接发送任何命令，或以 / 开头的命令，将作为 Claude Code 指令执行


---

❌ **#cancel**
取消当前运行


---

📜 **#history** `[数量]`
查看历史消息（默认10条）


---

📷 **#shot** `[行数]`
查看截屏（默认200行，可指定如 #shot 500）


---

🤖 **#model** `[序号/完整格式]`
查看或切换 CCR 模型（无参数显示列表）


---

📁 **#ws** `[序号]`
查看或切换工作空间（无参数显示列表，有参数按序号切换）



---

🎨 **#mm** `[子命令]`
MiniMax 多媒体能力（#mm help 查看详情）



---

❓ **#help**
显示此帮助信息"""
        if self.card_dispatcher:
            from src.card_builder import UnifiedCardBuilder
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="help",
                title="帮助",
                content=help_text,
                message_type="response",
                template_color="grey"
            )
        elif self.card_builder:
            from src.interfaces.im_platform import NormalizedCard
            card = NormalizedCard(
                card_type="help",
                title="帮助",
                content=help_text,
                template_color="blue"
            )
            await self._send_via_sender(user_id, card=card)
    async def _cmd_cancel(self, user_id: str, args: str):
        """发送 ESC 到 tmux"""
        # 获取当前工作空间的 session 名称
        try:
            from src.workspace_manager import get_workspace_manager
            workspace_manager = get_workspace_manager()
            current_workspace = workspace_manager.get_current_workspace()

            if current_workspace:
                session_name = workspace_manager._get_session_name(current_workspace)
            else:
                # 没有当前工作空间，使用默认
                session_name = "cc"
        except Exception as e:
            logger.warning(f"获取当前工作空间失败: {e}，使用默认 session 'cc'")
            session_name = "cc"
        # 发送 ESC 到 tmux session
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", f"{session_name}", "Escape"],
                check=True
            )
        except subprocess.CalledProcessError as e:
            error_msg = f"发送 ESC 失败: {e}"
            logger.error(error_msg)
            await self._send_error(user_id, error_msg)
            return
        # 发送确认消息
        if self.card_dispatcher:
            from src.card_builder import UnifiedCardBuilder
            content = UnifiedCardBuilder.build_cancel_card("已发送 ESC 到 Claude")
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="cancel",
                title="取消",
                content=content,
                message_type="response",
                template_color="grey"
            )
        elif self.card_builder:
            from src.interfaces.im_platform import NormalizedCard
            card = NormalizedCard(
                card_type="cancel",
                title="取消",
                content="已发送 ESC 到 Claude",
                template_color="grey"
            )
            await self._send_via_sender(user_id, card=card)
    async def _cmd_history(self, user_id: str, args: str = ""):
        """查看历史消息（只显示用户发送的上行消息）
        Args:
            user_id: 用户 ID
            args: 可选的数量参数，如 "5"
        """
        from src.storage import db
        from src.models import MessageDirection
        # 解析参数：如果提供数量参数则使用，否则使用默认值
        if args.strip().isdigit():
            limit = int(args.strip())
        else:
            limit = 10
        # 只获取用户发送的上行消息
        messages = db.get_messages_by_direction(
            MessageDirection.UPSTREAM, user_id=user_id, limit=limit
        )
        content_parts = []
        for i, msg in enumerate(messages, 1):
            # 每条消息作为一个段落
            entry = f"{i}. 🕒 `{msg.created_at.strftime('%Y-%m-%d %H:%M')}` {msg.content}"
            content_parts.append(entry)
        # 用分隔线连接所有消息，前后用多个空行隔开避免影响 Markdown 格式
        content = "\n\n---\n\n" + "\n\n---\n\n".join(content_parts)
        if self.card_dispatcher:
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="history",
                title="历史消息",
                content=content,
                message_type="response",
                template_color="grey"
            )
        elif self.card_builder:
            from src.interfaces.im_platform import NormalizedCard
            card = NormalizedCard(
                card_type="history",
                title="历史消息",
                content=content,
                template_color="grey"
            )
            await self._send_via_sender(user_id, card=card)
    async def _cmd_shot(self, user_id: str, args: str):
        """读取 tmux 输出
        Args:
            user_id: 用户 ID
            args: 可选的行数参数，如 "500"
        """
        from src.utils.tmux_utils import get_tmux_last_lines
        logger.info(f"开始处理 #shot 命令，用户: {user_id}, 参数: {args}")
        # 解析参数：如果提供行数参数则使用，否则使用配置中的默认值
        if args.strip().isdigit():
            lines = int(args.strip())
        else:
            lines = get_settings().TMUX_CAPTURE_LINES
        logger.info(f"获取截屏行数: {lines}")
        tmux_output = get_tmux_last_lines(lines)
        logger.info(f"获取到 tmux 输出，长度: {len(tmux_output)} 字符")
        if self.card_builder:
            await self._cmd_shot_with_builder(user_id, tmux_output)
        else:
            await self._cmd_shot_legacy(user_id, tmux_output)
    async def _cmd_shot_with_builder(self, user_id: str, tmux_output: str):
        """使用 card_dispatcher 处理截屏命令"""
        if self.card_dispatcher:
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="tmux",
                title="截屏",
                content=tmux_output,
                message_type="response",
                template_color="grey"
            )
            logger.info("使用 card_dispatcher 发送卡片")
        else:
            # Fallback to card_builder
            from src.interfaces.im_platform import NormalizedCard
            card = NormalizedCard(
                card_type="tmux",
                title="截屏",
                content=f"屏幕内容:\n\n```\n{tmux_output}\n```",
                template_color="grey"
            )
            logger.info("使用 card_builder 发送卡片")
            result = await self._send_via_sender(user_id, card=card)
            logger.info(f"卡片发送结果: {result}")

    async def _cmd_shot_legacy(self, user_id: str, tmux_output: str):
        """使用 card_builder 处理截屏命令（已废弃，仅作兼容保留）"""
        logger.warning("_cmd_shot_legacy 已废弃，使用 _cmd_shot_with_builder")
        await self._cmd_shot_with_builder(user_id, tmux_output)

    async def _send_error(self, user_id: str, error: str):
        """发送错误消息"""
        if self.card_builder:
            card = self.card_builder.create_error_card(error)
            await self._send_via_sender(user_id, card=card)
        else:
            from src.card_builder import create_error_card
            card = create_error_card(error)
            await self._send_via_sender(user_id, message=json.dumps(card, ensure_ascii=False))
