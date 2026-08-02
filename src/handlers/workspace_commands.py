"""
工作空间切换命令处理器
处理 #ws 命令，支持显示工作空间列表和切换工作空间

导航模式：
- 当存在 depth >= 2 的工作空间（即名称含 "/"），自动启用两级导航：
  * Level 1：按一级目录分组的选项卡
  * Level 2：组内工作空间列表 + 顶部"整个一级目录"选项
- 否则保持原有的扁平列表行为
"""
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

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


def _group_workspaces(workspaces: List[dict]) -> Dict[str, List[dict]]:
    """
    按 name 第一段（'/' 之前）分组工作空间。

    示例：
        [
          {'name': 'github', ...},
          {'name': 'github/larkode', ...},
          {'name': 'github/aiTermLark', ...},
        ]
        => {'github': [...]}
    """
    groups: Dict[str, List[dict]] = {}
    for ws in workspaces:
        name = ws.get("name", "") or ""
        group_key = name.split("/", 1)[0] if "/" in name else name
        groups.setdefault(group_key, []).append(ws)
    return groups


def _use_two_level_nav(workspaces: List[dict]) -> bool:
    """
    是否启用两级导航：只要任一工作空间名称含 "/" 就启用。
    否则（全部 depth=1）保持扁平列表行为。
    """
    return any("/" in (ws.get("name") or "") for ws in workspaces)


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

        # 无参数：决定显示方式
        if not args.strip():
            if _use_two_level_nav(workspaces):
                await self._show_workspace_groups(user_id, workspaces, send_message_func)
            else:
                await self._show_workspace_list(user_id, workspaces, send_message_func)
            return

        # 有参数
        args = args.strip()
        groups = _group_workspaces(workspaces)

        # 精确匹配一级目录名 → 进入 level-2
        if args in groups:
            await self._show_workspace_group_contents(
                user_id, args, workspaces, send_message_func
            )
            return

        # 数字序号
        if args.isdigit():
            workspace_index = int(args)
            if workspace_index < 1 or workspace_index > len(workspaces):
                await self._send_error(
                    user_id,
                    f"无效序号: {workspace_index}\n请输入 1-{len(workspaces)} 之间的数字",
                    send_message_func
                )
                return
            target = workspaces[workspace_index - 1]
            target_path = target.get("path")
        else:
            # 按名称/路径匹配
            matches = []
            for ws in workspaces:
                name = ws.get("name", "")
                if args.lower() in name.lower() or args.lower() in ws.get("path", "").lower():
                    matches.append(ws)

            if not matches:
                await self._send_error(
                    user_id,
                    f"未找到匹配的工作空间: {args}\n\n请使用 #ws <序号> 或 #ws <一级目录名>",
                    send_message_func
                )
                return

            if len(matches) > 1:
                options = []
                for ws in matches:
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

            target = matches[0]
            target_path = target.get("path")

        success, message = workspace_manager.switch_workspace(target_path)
        if success:
            workspace_name = target.get('name', target_path)
            await self._send_success(user_id, message, workspace_name, send_message_func)
        else:
            await self._send_error(user_id, message, send_message_func)

    async def _show_workspace_groups(
        self,
        user_id: str,
        workspaces: List[dict],
        send_message_func,
        page: int = 1,
    ):
        """Level 1：按一级目录显示（选项卡形式）"""
        from src.option_card import OptionCardData, OptionItem, build_option_card

        groups = _group_workspaces(workspaces)
        items: List[OptionItem] = []

        # 按组名排序
        for group_name in sorted(groups.keys()):
            members = groups[group_name]
            # 当前判断：组内有任一 workspace 处于 current
            is_current = any(ws.get("is_current") for ws in members)
            # running 判断
            running_count = sum(1 for ws in members if ws.get("is_running"))
            label = f"{group_name}/"
            markers = []
            if running_count:
                markers.append(f"🟢×{running_count}" if running_count > 1 else "🟢")
            if is_current:
                markers.append("✅")
            if markers:
                label = f"{label} ({' '.join(markers)})"
            items.append(OptionItem(
                key=group_name,
                label=label,
                is_current=is_current,
            ))

        total_groups = len(items)
        total_ws = len(workspaces)
        header_note = (
            f"共 **{total_groups}** 个一级目录（合计 {total_ws} 个工作空间）"
            f"\n点击进入目录查看下属工作空间 · 🟢 正在运行 · ✅ 当前"
        )

        card_data = build_option_card(OptionCardData(
            title="📁 工作空间（按目录）",
            category="ws_group",
            items=items,
            page=page,
            header_note=header_note,
            max_label_len=22,
        ))
        await send_message_func(user_id, card=card_data)

    async def _show_workspace_group_contents(
        self,
        user_id: str,
        group_name: str,
        workspaces: List[dict],
        send_message_func,
        page: int = 1,
    ):
        """
        Level 2：显示组内工作空间 + 顶部"整个一级目录"选项。

        实现策略：
        - 渲染两张 column_set：先一张 1 列的"整个一级目录"按钮行，再一张 N 列的工作空间按钮行
        - 工作空间列表翻页时，"整个一级目录"按钮固定在第一页
        """
        from src.option_card import (
            OptionCardData, OptionItem, build_option_card, _make_button, _make_button_row
        )

        # 过滤出本组的工作空间（depth>=2 的下属；排除与 group_name 同名的 depth=1 父项，
        # 避免与顶部"整个 <group>/"按钮重复）
        members = [
            ws for ws in workspaces
            if (ws.get("name") or "").split("/", 1)[0] == group_name
            and ws.get("name") != group_name
        ]
        # 找到一级目录条目（depth=1，同名）
        parent_ws = next(
            (ws for ws in workspaces if ws.get("name") == group_name),
            None,
        )

        # 构造工作空间按钮 items
        # key 使用完整工作空间名（depth>=2 时含 "/"），保证全局唯一。
        # label 只显示子工作空间名（一级目录已在卡片标题里），
        # 序号由 build_option_card 自动加上。
        ws_items: List[OptionItem] = []
        for ws in members:
            full_name = ws.get("name", "未命名")
            short_name = full_name[len(group_name) + 1:] if full_name.startswith(group_name + "/") else full_name
            markers = []
            if ws.get("is_running"):
                markers.append("🟢")
            if ws.get("is_current"):
                markers.append("✅")
            if ws.get("is_default"):
                markers.append("默认")
            label = short_name
            if markers:
                label = f"{label} ({' '.join(markers)})"
            ws_items.append(OptionItem(
                key=full_name,
                label=label,
                is_current=bool(ws.get("is_current")),
            ))

        # 构建选项卡：level-2 不分页（page_size 给一个很大的值，total_pages 始终 = 1）
        card = build_option_card(OptionCardData(
            title=f"📂 {group_name}/",
            category="ws",
            items=ws_items,
            page=1,
            page_size=999,
            header_note=(
                f"共 **{len(members)}** 个工作空间"
                + (f" · ✅ 当前" if parent_ws and parent_ws.get("is_current") else "")
            ),
            max_label_len=22,
        ))

        # 在 body.elements 最前面（紧跟 summary 之后）插入"整个一级目录"按钮行
        # 找到分隔摘要的 hr 之后、第一个 column_set 之前的位置
        elements = card["body"]["elements"]
        insert_idx = None
        for idx, el in enumerate(elements):
            if el.get("tag") == "column_set":
                insert_idx = idx
                break
        if insert_idx is None:
            # 没有 column_set（空列表场景），直接 append
            insert_idx = len(elements)

        # 构造"整个一级目录"按钮
        is_parent_current = bool(parent_ws and parent_ws.get("is_current"))
        is_parent_running = bool(parent_ws and parent_ws.get("is_running"))
        parent_label = f"📁 整个 {group_name}/"
        markers = []
        if is_parent_running:
            markers.append("🟢")
        if is_parent_current:
            markers.append("✅")
        if markers:
            parent_label = f"{parent_label} ({' '.join(markers)})"

        parent_button = _make_button(
            {"opt": "select", "cat": "ws_parent", "key": group_name, "page": page},
            parent_label,
            "primary" if is_parent_current else "default",
        )
        parent_row = _make_button_row([parent_button])

        # 在第一个 column_set 之前插入 hr + parent_row
        elements.insert(insert_idx, {"tag": "hr"})
        elements.insert(insert_idx + 1, parent_row)

        await send_message_func(user_id, card=card)

    async def _show_workspace_list(
        self,
        user_id: str,
        workspaces: List[dict],
        send_message_func,
        page: int = 1,
    ):
        """扁平显示工作空间列表（当全部为 depth=1 时使用）"""
        from src.option_card import OptionCardData, OptionItem, build_option_card

        items = []
        for i, ws in enumerate(workspaces, 1):
            name = ws.get("name", "未命名")
            markers = []
            if ws.get("is_running"):
                markers.append("🟢")
            if ws.get("is_current"):
                markers.append("✅")
            if ws.get("is_default"):
                markers.append("默认")
            label = name
            if markers:
                label = f"{name} ({' '.join(markers)})"
            items.append(OptionItem(
                key=str(i),
                label=label,
                is_current=bool(ws.get("is_current")),
            ))

        card_data = build_option_card(OptionCardData(
            title="📁 工作空间",
            category="ws",
            items=items,
            page=page,
            header_note="点击按钮切换工作空间 · 🟢 正在运行 · ✅ 当前 · 默认 工作空间",
        ))
        await send_message_func(user_id, card=card_data)

    # --------------------- 回调入口 ---------------------

    async def show_workspace_option_card(
        self,
        user_id: str,
        send_message_func,
        page: int = 1,
    ):
        """公开方法：按页码展示工作空间选项卡（用于卡片回调）。

        两级导航时显示 level-1（一级目录）；扁平模式时显示工作空间列表。
        """
        try:
            settings = get_settings()
            if not settings.workspace_discovery_enabled:
                return
            if not settings.workspace_root_dir or not settings.workspace_root_dir.exists():
                return
            workspace_manager = get_workspace_manager()
            workspaces = workspace_manager.get_workspaces()
            if not workspaces:
                return
            if _use_two_level_nav(workspaces):
                await self._show_workspace_groups(user_id, workspaces, send_message_func, page=page)
            else:
                await self._show_workspace_list(user_id, workspaces, send_message_func, page=page)
        except Exception as e:
            logger.error(f"展示工作空间选项卡失败: {e}", exc_info=True)

    async def show_workspace_group_contents_option_card(
        self,
        user_id: str,
        group_name: str,
        send_message_func,
        page: int = 1,
    ):
        """公开方法：按页码展示指定一级目录的内容（用于卡片回调）"""
        try:
            settings = get_settings()
            if not settings.workspace_discovery_enabled:
                return
            if not settings.workspace_root_dir or not settings.workspace_root_dir.exists():
                return
            workspace_manager = get_workspace_manager()
            workspaces = workspace_manager.get_workspaces()
            if not workspaces:
                return
            await self._show_workspace_group_contents(
                user_id, group_name, workspaces, send_message_func, page=page
            )
        except Exception as e:
            logger.error(f"展示工作空间组内容失败: {e}", exc_info=True)

    async def handle_workspace_select(
        self,
        user_id: str,
        key: str,
        send_message_func,
    ):
        """处理选项卡回调：按 key 切换工作空间。

        key 形式：
        - "1", "2", ...：扁平列表的全局 1-based 索引
        - "github/larkode" 等：完整工作空间名（level-2 按钮）
        """
        try:
            workspace_manager = get_workspace_manager()
            workspaces = workspace_manager.get_workspaces()
            if not workspaces:
                await self._send_error(user_id, "当前没有可用的工作空间", send_message_func)
                return

            target = None

            if key.isdigit():
                index = int(key)
                if index < 1 or index > len(workspaces):
                    await self._send_error(
                        user_id,
                        f"无效序号: {index}\n请输入 1-{len(workspaces)} 之间的数字",
                        send_message_func,
                    )
                    return
                target = workspaces[index - 1]
            else:
                # 优先精确匹配 name
                for ws in workspaces:
                    if ws.get("name") == key:
                        target = ws
                        break
                if target is None:
                    # 回退到子串匹配
                    matches = [ws for ws in workspaces
                               if key.lower() in (ws.get("name", "") or "").lower()]
                    if len(matches) == 1:
                        target = matches[0]
                    elif len(matches) > 1:
                        lines = []
                        for i, ws_total in enumerate(workspaces, 1):
                            if any(ws_total is m for m in matches):
                                lines.append(f"  {i}. {ws_total.get('name')}")
                        await self._send_error(
                            user_id,
                            f"找到多个匹配的工作空间，请提供完整名称:\n" + "\n".join(lines),
                            send_message_func,
                        )
                        return
                    else:
                        await self._send_error(
                            user_id,
                            f"未找到匹配的工作空间: {key}",
                            send_message_func,
                        )
                        return

            target_path = target.get("path")
            success, message = workspace_manager.switch_workspace(target_path)
            workspace_name = target.get("name", target_path)
            if success:
                await self._send_success(user_id, message, workspace_name, send_message_func)
            else:
                await self._send_error(user_id, message, send_message_func)
        except Exception as e:
            logger.error(f"切换工作空间失败: {e}", exc_info=True)
            await self._send_error(user_id, f"切换失败: {e}", send_message_func)

    async def handle_workspace_parent_select(
        self,
        user_id: str,
        group_name: str,
        send_message_func,
    ):
        """处理选项卡回调：切换到一级目录（level-2 顶部按钮）"""
        try:
            settings = get_settings()
            workspace_manager = get_workspace_manager()
            workspaces = workspace_manager.get_workspaces()

            # 优先复用 depth=1 的 workspace 条目（保留 is_running/is_current 信息）
            parent_ws = next(
                (ws for ws in workspaces if ws.get("name") == group_name),
                None,
            )
            if parent_ws:
                target_path = parent_ws.get("path")
                display_name = group_name
            else:
                # depth=1 不存在（理论上不应该），兜底用 root_dir/group_name
                target_path = str(settings.workspace_root_dir / group_name)
                display_name = group_name

            success, message = workspace_manager.switch_workspace(target_path)
            if success:
                await self._send_success(user_id, message, display_name, send_message_func)
            else:
                await self._send_error(user_id, message, send_message_func)
        except Exception as e:
            logger.error(f"切换到一级目录失败: {e}", exc_info=True)
            await self._send_error(user_id, f"切换失败: {e}", send_message_func)

    async def _show_workspace_list_fallback(
        self,
        user_id: str,
        workspaces: List[dict],
        send_message_func,
    ):
        """文本列表 fallback（飞书服务端不支持按钮时使用）"""
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