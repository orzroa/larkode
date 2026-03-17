"""
工作空间切换命令处理器
处理 #ws 命令，支持显示工作空间列表和切换工作空间
"""
from typing import TYPE_CHECKING, List

from src.config.settings import get_settings
from src.workspace_manager import get_workspace_manager

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.interfaces.im_platform import NormalizedCard


class WorkspaceCommands:
    """工作空间切换命令处理器"""

    def __init__(self):
        """初始化工作空间命令处理器"""
        pass

    async def handle_workspace_command(
        self,
        user_id: str,
        args: str,
        send_message_func
    ):
        """
        处理 #ws 命令

        Args:
            user_id: 用户 ID
            args: 命令参数（可选）
            send_message_func: 发送消息的回调函数
        """
        settings = get_settings()

        # 检查是否启用自动发现
        if not settings.workspace_discovery_enabled:
            await self._send_error(
                user_id,
                "未启用工作空间自动发现\n\n请在 .env 中配置：\nWORKSPACE_DISCOVERY_ENABLED=true",
                send_message_func
            )
            return

        # 检查根目录是否配置
        if not settings.workspace_root_dir or not settings.workspace_root_dir.exists():
            await self._send_error(
                user_id,
                f"工作空间根目录未配置或不存在\n\n请检查配置：\nWORKSPACE_ROOT_DIR={settings.workspace_root_dir}",
                send_message_func
            )
            return

        # 获取工作空间管理器
        workspace_manager = get_workspace_manager()

        # 获取工作空间列表（实时扫描）
        workspaces = workspace_manager.get_workspaces()

        if not workspaces:
            await self._send_error(
                user_id,
                f"未发现任何工作空间\n\n根目录: {settings.workspace_root_dir}\n深度: {settings.workspace_discovery_depth}",
                send_message_func
            )
            return

        # 无参数：显示工作空间列表
        if not args.strip():
            await self._show_workspace_list(user_id, workspaces, send_message_func)
            return

        # 有参数：切换工作空间
        args = args.strip()

        # 尝试按数字序号匹配
        if args.isdigit():
            workspace_index = int(args)

            # 验证序号范围
            if workspace_index < 1 or workspace_index > len(workspaces):
                await self._send_error(
                    user_id,
                    f"无效序号: {workspace_index}\n请输入 1-{len(workspaces)} 之间的数字",
                    send_message_func
                )
                return

            # 获取目标工作空间
            target = workspaces[workspace_index - 1]
            target_path = target.get("path")
        else:
            # 按名称匹配（支持部分匹配，如 "github/larkode" 或 "larkode"）
            matches = []
            for ws in workspaces:
                name = ws.get("name", "")
                # 匹配名称或路径中包含输入字符串（不区分大小写）
                if args.lower() in name.lower() or args.lower() in ws.get("path", "").lower():
                    matches.append(ws)

            if not matches:
                await self._send_error(
                    user_id,
                    f"未找到匹配的工作空间: {args}\n\n请使用 #ws <序号> 或 #ws <名称>",
                    send_message_func
                )
                return

            if len(matches) > 1:
                # 多个匹配，显示总列表中的序号
                # 找出每个匹配工作空间在总列表中的序号
                options = []
                for ws in matches:
                    # 在总列表中查找序号
                    for i, ws_total in enumerate(workspaces, 1):
                        if ws_total.get('path') == ws.get('path'):
                            options.append(f"{i}. {ws.get('name')}")
                            break
                await self._send_error(
                    user_id,
                    f"找到多个匹配的工作空间，请使用 #ws <序号> 选择：\n" + "\n".join(options),
                    send_message_func
                )
                return

            # 唯一匹配
            target = matches[0]
            target_path = target.get("path")

        # 切换工作空间
        success, message = workspace_manager.switch_workspace(target_path)

        if success:
            # 获取工作空间名称用于卡片标题
            workspace_name = target.get('name', target_path)
            await self._send_success(user_id, message, workspace_name, send_message_func)
        else:
            await self._send_error(user_id, message, send_message_func)

    async def _show_workspace_list(
        self,
        user_id: str,
        workspaces: List[dict],
        send_message_func
    ):
        """显示工作空间列表"""
        from src.interfaces.im_platform import NormalizedCard

        settings = get_settings()
        default_path = str(settings.workspace_default_dir) if settings.workspace_default_dir else None

        # 检查默认工作空间是否在列表中
        default_in_list = any(ws['path'] == default_path for ws in workspaces)

        # 构建 Markdown 列表
        lines = []

        if not default_in_list and default_path:
            lines.append("⚠️ **警告**: 默认工作空间不在自动发现范围内")
            lines.append(f"默认工作空间: `{default_path}`")
            lines.append("")

        for i, ws in enumerate(workspaces, 1):
            name = ws.get("name", "未命名")

            # 构造状态标记
            markers = []
            if ws.get("is_running"):
                markers.append("🟢")
            if ws.get("is_current"):
                markers.append("✅")
            if ws.get("is_default"):
                markers.append("**(默认)**")

            marker_str = " ".join(markers)

            # 如果是默认工作空间，整行加粗
            if ws.get("is_default"):
                lines.append(f"**{i}. {name} {marker_str}**")
            elif marker_str:
                lines.append(f"**{i}**. {name} {marker_str}")
            else:
                lines.append(f"**{i}**. {name}")

        content = f"""### 📁 工作空间列表

{chr(10).join(lines)}

---
✅ = 当前工作空间
🟢 = 正在运行
**(默认)** = 配置文件中指定的默认工作空间

💡 使用 `#ws <序号>` 或 `#ws <名称>` 切换工作空间
"""

        card = NormalizedCard(
            card_type="workspace_list",
            title="工作空间",
            content=content,
            template_color="blue"
        )
        await send_message_func(user_id, card=card)

    async def _send_success(
        self,
        user_id: str,
        content: str,
        workspace_name: str,
        send_message_func
    ):
        """发送成功消息"""
        from src.interfaces.im_platform import NormalizedCard

        card = NormalizedCard(
            card_type="success",
            title=f"[{workspace_name}] 成功",
            content=content,
            template_color="green"
        )
        await send_message_func(user_id, card=card)

    async def _send_error(
        self,
        user_id: str,
        error: str,
        send_message_func
    ):
        """发送错误消息"""
        from src.interfaces.im_platform import NormalizedCard

        card = NormalizedCard(
            card_type="error",
            title="错误",
            content=error,
            template_color="red"
        )
        await send_message_func(user_id, card=card)