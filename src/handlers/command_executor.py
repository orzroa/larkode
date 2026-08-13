"""
命令执行器

负责命令的处理和执行
"""
import asyncio
import json
from html import escape
from typing import Optional, TYPE_CHECKING

from src.models import Message, MessageType, MessageDirection, MessageSource
from src.storage import db
from src.config.settings import get_settings

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

        set_request_handler = getattr(
            getattr(self.tm, "ai_assistant", None),
            "set_server_request_handler",
            None,
        )
        if set_request_handler:
            set_request_handler(self._handle_codex_server_request)

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
                    handled = await self._platform_commands.handle_command(user_id, command)
                    if not handled:
                        # 未识别的平台命令必须 fail closed，避免拼写错误把控制平面仓库
                        # 变成 Agent 的可写工作区。
                        logger.warning(f"拒绝未识别的平台命令：{command}")
                        await self.send_error(user_id, "未知命令，请输入 #help 查看帮助")
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

    async def _execute_in_larkode_space(self, user_id: str, command: str):
        """
        在 larkode 空间执行 AI 命令（临时切换空间，执行后切回）

        Args:
            user_id: 用户 ID
            command: AI 命令内容
        """
        from src.workspace_manager import get_workspace_manager

        logger.info(f"临时切换到 larkode 空间执行命令: {command}")

        settings = get_settings()
        larkode_path = settings.workspace_default_dir

        workspace_manager = get_workspace_manager()
        original_workspace = workspace_manager.get_current_workspace()

        try:
            # 临时切换到 larkode 空间（如果原本不是）
            if original_workspace != larkode_path:
                workspace_manager.switch_workspace(larkode_path)
            # 复用 execute_command 逻辑
            await self.execute_command(user_id, command)
        except Exception as e:
            logger.error(f"在 larkode 空间执行命令失败: {e}", exc_info=True)
            await self.send_error(user_id, f"执行失败: {e}")
        finally:
            # 恢复原工作空间（如果原本不是 larkode）
            if original_workspace and original_workspace != larkode_path:
                workspace_manager.switch_workspace(original_workspace)
                logger.info(f"已恢复原工作空间: {original_workspace}")

    async def execute_command(self, user_id: str, command: str, seq_id: Optional[int] = None):
        """
        执行 AI 助手 命令

        Args:
            user_id: 用户 ID
            command: 命令内容
            seq_id: 消息序列号（可选）
        """
        # 发送确认消息（根据配置）
        if get_settings().SHOW_COMMAND_CONFIRMATION_CARD:
            if self.card_dispatcher:
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

        # 捕获任务开始时的工作区，避免执行期间切换 #ws 后完成卡标题漂移。
        workspace_path = None
        try:
            from src.workspace_manager import get_workspace_manager
            workspace_path = get_workspace_manager().get_current_workspace()
        except Exception:
            pass

        # 执行命令
        try:
            output_parts = []
            async for output in self.tm.execute_command(user_id, command):
                if output:
                    output_parts.append(output)

            # Claude Code 的最终内容仍由 Hook 发送；Codex 没有这条旧链路，
            # 因此先发送聚合后的最终回复。后续 Presenter 会接管两者。
            status = self.tm.get_assistant_status()
            if status.get("assistant_type") == "codex" and output_parts:
                content = "".join(output_parts).strip()
                outcome = status.get("last_outcome", "success")
                if outcome == "error":
                    card_type, title, color, message_type = "error", "执行失败", "red", "error"
                elif outcome == "cancelled":
                    card_type, title, color, message_type = "cancel", "已取消", "grey", "status"
                else:
                    card_type, title, color, message_type = "stop", "回复完成", "green", "response"
                if self.card_dispatcher:
                    await self.card_dispatcher.send_card(
                        user_id=user_id,
                        card_type=card_type,
                        title=title,
                        content=content,
                        message_type=message_type,
                        template_color=color,
                        workspace_path=workspace_path,
                    )
                elif self._message_sender:
                    await self._message_sender.send(user_id, message=content)
        except Exception as e:
            logger.error(f"执行命令失败：{e}", exc_info=True)
            await self.send_error(user_id, f"执行失败：{str(e)}")

    async def send_error(self, user_id: str, error: str):
        """
        发送错误消息

        Args:
            user_id: 用户 ID
            error: 错误信息
        """
        if self._message_sender:
            await self._message_sender.send_error(user_id, error)

    async def _handle_codex_server_request(
        self, request: dict, user_id: str
    ) -> Optional[dict]:
        """以飞书卡片处理 Codex 命令/文件审批。"""
        method = request.get("method", "")
        if method not in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        } or not (self.card_dispatcher or self.feishu):
            return None

        from src.agent.approval import codex_approval_broker

        params = request.get("params", {})
        title = "Codex 命令审批" if "commandExecution" in method else "Codex 文件修改审批"
        network = params.get("networkApprovalContext") or {}
        command = params.get("command") or params.get("grantRoot")
        network_target = ""
        if network:
            host = network.get("host") or network.get("hostname") or "未知主机"
            protocol = network.get("protocol") or "network"
            port = network.get("port")
            network_target = f"{protocol}://{host}{f':{port}' if port else ''}"
        command = command or "（未提供详情）"
        item = params.get("_item") or {}
        changes = item.get("changes") or item.get("diff")
        reason = params.get("reason") or "Codex 请求继续执行"
        cwd = params.get("cwd")

        def safe_code(value) -> str:
            # HTML escape 不会阻止 Markdown 围栏逃逸；拆开连续反引号。
            return escape(str(value)).replace("```", "``\u200b`")

        details = (
            f"**原因：**\n```text\n{safe_code(reason)}\n```"
        )
        if network_target:
            details += f"\n\n**网络目标：**\n```text\n{safe_code(network_target)}\n```"
        details += f"\n\n**命令/授权内容：**\n```text\n{safe_code(command)}\n```"
        if cwd:
            details += f"\n\n**目录：**\n```text\n{safe_code(cwd)}\n```"
        changes_too_large = False
        if changes:
            if isinstance(changes, (dict, list)):
                changes_text = json.dumps(changes, ensure_ascii=False, indent=2)
            else:
                changes_text = str(changes)
            changes_too_large = len(changes_text) > 4000
            shown = changes_text[:4000]
            details += f"\n\n**变更：**\n```diff\n{safe_code(shown)}\n```"
            if changes_too_large:
                details += "\n⚠️ 变更详情超过卡片安全展示上限，已禁止通过该卡片批准。"

        def button(text: str, decision: str, button_type: str = "default") -> dict:
            return {
                "tag": "button",
                "text": {"tag": "plain_text", "content": text},
                "type": button_type,
                "value": {
                    "action": "codex_approval",
                    "approval_id": approval_id,
                    "decision": decision,
                },
            }

        available = set(params.get("availableDecisions") or ["accept", "decline"])
        button_specs = []
        if "accept" in available and not changes_too_large:
            button_specs.append(("允许一次", "accept", "primary"))
        if "acceptForSession" in available and not changes_too_large:
            button_specs.append(("本会话允许", "acceptForSession", "default"))
        if "decline" in available:
            button_specs.append(("拒绝", "decline", "danger"))
        elif "cancel" in available:
            button_specs.append(("取消", "cancel", "danger"))
        if not button_specs:
            logger.error(f"审批请求没有可安全处理的 decision: {sorted(available)}")
            return None
        approval_id, future = codex_approval_broker.create(
            user_id, {decision for _, decision, _ in button_specs}
        )
        columns = [
            {"tag": "column", "width": "weighted", "weight": 1,
             "elements": [button(text, decision, kind)]}
            for text, decision, kind in button_specs
            if decision in available
        ]
        timeout_decision = "decline" if "decline" in available else (
            "cancel" if "cancel" in available else None
        )
        card = {
            "schema": "2.0",
            "config": {"update_multi": True},
            "header": {
                "title": {"tag": "plain_text", "content": title},
                "template": "orange",
            },
            "body": {"elements": [
                {"tag": "markdown", "content": details},
                {"tag": "column_set", "flex_mode": "stretch", "columns": columns},
            ]},
        }

        try:
            if self.card_dispatcher:
                sent = await self.card_dispatcher.send_interactive_card(
                    user_id, card, message_type="status", workspace_path=cwd
                )
            else:
                sent = await self.feishu.send_message(
                    user_id, json.dumps(card, ensure_ascii=False)
                )
            if not sent:
                return None
            decision = await asyncio.wait_for(
                future, timeout=get_settings().codex_approval_timeout
            )
            return {"decision": decision}
        except asyncio.TimeoutError:
            return {"decision": timeout_decision} if timeout_decision else None
        finally:
            codex_approval_broker.cancel(approval_id)


# 全局命令执行器实例（需要外部初始化）
command_executor: Optional[CommandExecutor] = None
