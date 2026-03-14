#!/usr/bin/env -S uv run --no-project
# /// script
# dependencies = [
#   "lark-oapi>=1.5.3",
#   "python-dotenv>=1.0.0",
#   "pydantic>=2.5.3",
#   "pydantic-settings>=2.0.0",
#   "psutil>=5.9.0"
# ]
# ///

"""
Hook 日志记录器
支持 Claude Code 和 iFlow CLI 的 Hooks 处理
"""
# 标准库
import asyncio
import datetime
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Optional, Union

# 第三方库
from dotenv import load_dotenv

# 添加项目根目录到路径
PROJECT_ROOT = Path(os.path.dirname(os.path.abspath(__file__))).parent
sys.path.insert(0, str(PROJECT_ROOT))

# 本地应用
from src.config.settings import Config, get_settings
# from src.card_manager import create_notification_card  # 将废弃
from src.card_dispatcher import CardDispatcher
from src.exceptions import HookError, HookExecutionError, handle_exception
from src.feishu import FeishuAPI, FeishuAPIError
from src.interfaces.hook_handler import (
    IHookHandler,
    HookEventType,
    HookContext,
    detect_handler,
)
from src.utils.card_id import get_card_id_manager
from src.utils.tmux_utils import get_tmux_last_lines
from src.models import Message, MessageType, MessageDirection, MessageSource
from src.storage import db

# 加载 .env 文件
ENV_FILE = PROJECT_ROOT / ".env"
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)


# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# 日志目录
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "hook_events.log"
JSON_LOG_FILE = LOG_DIR / "hook_events.jsonl"


def _is_test_user(user_id: str) -> bool:
    """判断是否为测试用户"""
    return "test" in user_id.lower()


def record_hook_message(user_id: str, message: str, message_type: str = "notification", feishu_message_id: str = "", card_id: Optional[int] = None):
    """
    记录 Hook 消息到数据库

    Args:
        user_id: 用户 ID
        message: 消息内容
        message_type: 消息类型 (hook notification type: "stop", "prompt", "permission", "notification")
        feishu_message_id: 飞书消息ID
        card_id: 卡片编号
    """
    try:
        # 将 hook 消息类型映射到 MessageType
        # stop/prompt/permission 是 send_feishu_notification 的消息类型参数
        # 在数据库中使用 STATUS 类型存储
        msg = Message(
            user_id=user_id,
            message_type=MessageType.STATUS,  # Hook 通知使用 STATUS 类型
            content=message,
            direction=MessageDirection.DOWNSTREAM,
            is_test=None,  # 使用全局测试模式
            message_source=MessageSource.HOOK,
            feishu_message_id=feishu_message_id or "",
            card_id=card_id
        )
        db.save_message(msg)
        logger.debug(f"Hook 消息已记录：user_id={user_id}, type={message_type}")
    except Exception as e:
        logger.error(f"记录 Hook 消息失败：{e}")


def collect_all_data(handler: IHookHandler, context: HookContext, stdin_data: str) -> dict:
    """收集所有可用的数据"""
    data = {
        "timestamp": datetime.datetime.now().isoformat(),
        "handler": handler.name,
        "hook_event": context.event_type.value,
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "working_directory": os.getcwd(),
        "environment": {},
        "command_line": sys.argv,
        "stdin": stdin_data,
        "stdin_parsed": context.raw_data,
    }

    # 收集相关环境变量
    for key, value in os.environ.items():
        if any(prefix in key.upper() for prefix in [
            "CLAUDE", "IFLOW", "FEISHU", "GIT", "HOME", "PATH"
        ]):
            data["environment"][key] = value

    return data


def log_event(data: dict, step_info: str = ""):
    """记录事件到日志文件"""
    timestamp = data["timestamp"]
    hook_event = data["hook_event"]
    stdin_parsed = data.get("stdin_parsed", {})

    log_line = f"""
{'=' * 80}
{timestamp} - [{data['handler']}] {hook_event}
{'=' * 80}
[STEP] {step_info if step_info else "事件记录"}
Handler: {data["handler"]}
Event: {hook_event}
Hostname: {data["hostname"]}
Working Directory: {data["working_directory"]}

stdin_parsed:
{json.dumps(stdin_parsed, ensure_ascii=False, indent=2)}
"""
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line)

    # 写入 JSONL 文件
    json_data = {
        "timestamp": timestamp,
        "handler": data["handler"],
        "hook_event": hook_event,
        "stdin_parsed": stdin_parsed,
        "step_info": step_info
    }
    with open(JSON_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(json_data, ensure_ascii=False) + "\n")


async def send_feishu_notification(message: str, message_type: str = "stop", event_name: str = "") -> str:
    """
    发送飞书通知消息

    Args:
        message: 要发送的消息内容
        message_type: 消息类型 ("stop", "prompt", "permission")
        event_name: Hook 事件名称

    Returns:
        str: 发送成功返回消息ID，失败返回空字符串
    """
    # 检测流式输出模式
    streaming_card_id = os.environ.get("LARKODE_STREAMING_MODE")
    if streaming_card_id and message_type == "stop":
        # 流式输出模式：清理环境变量，但仍然发送 stop 卡片作为小结
        logger.info(f"检测到流式输出模式 (card_id={streaming_card_id})，将发送 stop 小结卡片")
        del os.environ["LARKODE_STREAMING_MODE"]
        # 继续执行，发送 stop 卡片

    user_id = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    app_secret = os.getenv("FEISHU_APP_SECRET")

    if not all([user_id, app_secret]):
        logger.warning("飞书配置不完整，跳过发送通知")
        return ""

    try:
        # 使用 FeishuAPI 发送通知（统一入口）
        feishu = FeishuAPI(get_settings().FEISHU_APP_ID, app_secret)

        # 创建 CardDispatcher 实例（临时，每次调用创建）
        card_dispatcher = CardDispatcher(feishu_api=feishu)

        # 创建一个 notification sender wrapper 来适配旧接口
        # 这样可以确保 CardDispatcher 能返回 message_id
        class NotificationSenderWrapper:
            def __init__(self, feishu_api):
                self.feishu_api = feishu_api
                self.last_message_id = ""

            async def send_card(self, user_id, card):
                # 转换为飞书卡片格式
                from src.im_platforms.feishu import FeishuPlatform
                from src.interfaces.im_platform import PlatformConfig

                platform = FeishuPlatform(PlatformConfig(
                    app_id=get_settings().FEISHU_APP_ID,
                    app_secret=app_secret,
                    receive_id_type="open_id"
                ))
                card_json_str = platform._convert_normalized_card_to_feishu(card)

                result = await self.feishu_api.send_interactive_message(user_id, card_json_str, "")
                self.last_message_id = result if result else ""
                return bool(result)

        notification_sender = NotificationSenderWrapper(feishu)
        card_dispatcher.set_notification_sender(notification_sender)

        # 根据 message_type 设置卡片标题和颜色
        card_titles = {
            "stop": "回复完成",
            "prompt": "用户提问",
            "permission": "交互请求"
        }
        card_colors = {
            "stop": "green",
            "prompt": "blue",
            "permission": "orange"
        }

        title = card_titles.get(message_type, "通知")
        template_color = card_colors.get(message_type, "grey")

        # 发送卡片（CardDispatcher 内部会处理文件上传和数据库存储）
        feishu_msg_id, file_key = await card_dispatcher.send_card(
            user_id=user_id,
            card_type=message_type,
            title=title,
            content=message,
            message_type="status",
            template_color=template_color
        )

        logger.info(f"成功发送飞书通知给用户 {user_id}, message_id={feishu_msg_id}")

        # 注意：CardDispatcher 已经自动记录到数据库，无需重复调用 record_hook_message

        return feishu_msg_id if feishu_msg_id else ""

    except FeishuAPIError as api_err:
        logger.error(f"发送飞书通知失败: {api_err}")
        return ""
    except Exception as e:
        logger.error(f"发送飞书通知时出错: {e}")
        return ""


def build_permission_message(context: Union[HookContext, str], tool_input: Optional[dict] = None) -> str:
    """构建交互请求消息

    Args:
        context: HookContext 对象或 tool_name 字符串
        tool_input: 工具输入参数（当 context 是字符串时必需）

    Returns:
        str: 构建的消息
    """
    # 兼容两种调用方式
    if isinstance(context, HookContext):
        tool_name = context.tool_name or ""
        tool_input = context.tool_input or {}
    else:
        tool_name = context
        tool_input = tool_input or {}

    return _build_permission_content(tool_name, tool_input)


def build_permission_request_message(tool_name: str, tool_input: dict) -> str:
    """构建交互请求消息（兼容测试的简化版本）

    Args:
        tool_name: 工具名称（如 "Bash", "Write", "AskUserQuestion"）
        tool_input: 工具输入参数

    Returns:
        str: 构建的消息字符串
    """
    return _build_permission_content(tool_name, tool_input)


def _build_permission_content(tool_name: str, tool_input: dict) -> str:
    """构建权限请求消息的核心逻辑

    Args:
        tool_name: 工具名称
        tool_input: 工具输入参数

    Returns:
        str: 构建的消息
    """
    if tool_name == "AskUserQuestion":
        questions = tool_input.get("questions", [])
        if not questions:
            return "Claude Code 需要您的选择"

        message_parts = []
        for q in questions:
            question = q.get("question", "")
            header = q.get("header", "")
            options = q.get("options", [])
            is_multi = q.get("multiSelect", False)

            if header:
                message_parts.append(f"**{header}**")
            if question:
                message_parts.append(question)

            if options:
                for j, opt in enumerate(options):
                    label = opt.get("label", "")
                    description = opt.get("description", "")
                    if description:
                        message_parts.append(f"{j + 1}. {label} - {description}")
                    elif label:
                        message_parts.append(f"{j + 1}. {label}")

                message_parts.append("")
                message_parts.append("(" + ("多选" if is_multi else "单选") + ")")

        return "\n".join(message_parts).strip()

    # 其他工具（Bash、ExitPlanMode、Edit 等）统一显示 tmux 屏幕内容
    else:
        # 获取 tmux 输出
        tmux_output = get_tmux_last_lines(50)
        return f"屏幕内容:\n\n```\n{tmux_output}\n```"


def send_escape_to_tmux() -> bool:
    """发送 ESC 到 tmux session，取消 AI 等待状态

    Returns:
        bool: 是否发送成功
    """
    # 测试模式下跳过，避免中断测试进程
    if os.getenv("SKIP_TMUX_ESCAPE") or os.getenv("PYTEST_CURRENT_TEST"):
        logger.info("测试模式：跳过发送 ESC 到 tmux")
        return True

    import subprocess
    from src.config.settings import Config, get_settings

    session_name = get_settings().TMUX_SESSION_NAME or "cc"
    try:
        subprocess.run(
            ["tmux", "send-keys", "-t", f"{session_name}", "Escape"],
            check=True,
            capture_output=True
        )
        logger.info(f"已发送 ESC 到 tmux session: {session_name}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"发送 ESC 失败: {e}")
        return False
    except FileNotFoundError:
        logger.warning("tmux 命令未找到")
        return False


async def handle_event(handler: IHookHandler, context: HookContext, data: dict):
    """处理 Hook 事件

    根据事件类型发送相应的飞书通知：
    - USER_PROMPT_SUBMIT: 发送用户提问通知
    - STOP: 发送完成通知
    - NOTIFICATION: 发送通知卡片
    - PERMISSION_REQUEST: 发送权限请求卡片
    - PRE_TOOL_USE: 发送工具使用前权限请求（新格式）
    - POST_TOOL_USE: 记录工具使用结果
    - POST_TOOL_USE_FAILURE: 发送工具使用失败通知
    - SUBAGENT_STOP: 发送子代理完成通知

    Args:
        handler: Hook 处理器实例
        context: Hook 上下文
        data: 事件数据

    Returns:
        None
    """

    # UserPromptSubmit: 发送用户提问通知
    if context.event_type == HookEventType.USER_PROMPT_SUBMIT:
        # 检查是否启用了显示用户提问卡片
        if not get_settings().SHOW_USER_PROMPT_CARD:
            logger.debug("用户提问卡片已禁用，跳过发送")
            return

        if context.user_prompt:
            success = await send_feishu_notification(
                context.user_prompt, "prompt", context.event_type.value
            )
            if success:
                log_event(data, "发送用户提问通知")

    # Stop: 发送完成通知
    elif context.event_type == HookEventType.STOP:
        message = context.last_assistant_message or "已完成响应"
        success = await send_feishu_notification(message, "stop", context.event_type.value)
        if success:
            log_event(data, "发送完成通知")

    # SubagentStop: 发送子代理完成通知
    elif context.event_type == HookEventType.SUBAGENT_STOP:
        message = context.last_assistant_message or "子代理已完成"
        success = await send_feishu_notification(message, "stop", context.event_type.value)
        if success:
            log_event(data, "发送子代理完成通知")

    # PreToolUse: 发送工具使用前权限请求（新格式）
    elif context.event_type == HookEventType.PRE_TOOL_USE:
        tool_name = context.tool_name or ""
        tool_input = context.tool_input or {}
        # AskUserQuestion 需要发送 ESC，其他工具（如 Bash）正常等待用户选择
        if tool_name == "AskUserQuestion":
            log_event(data, "发送 ESC 取消等待")
            send_escape_to_tmux()
        message = build_permission_message(context, tool_input)
        log_event(data, "发送工具使用前权限请求")
        await send_feishu_notification(message, "permission", context.event_type.value)

    # PostToolUseFailure: 发送工具使用失败通知
    elif context.event_type == HookEventType.POST_TOOL_USE_FAILURE:
        tool_name = context.tool_name or ""
        tool_result = context.tool_input or {}
        message = f"**工具执行失败**\n\n工具：{tool_name}\n\n结果：\n```{json.dumps(tool_result, ensure_ascii=False, indent=2)}```"
        log_event(data, "发送工具使用失败通知")
        asyncio.run(send_feishu_notification(message, "permission", context.event_type.value))

    # PostToolUse: 记录工具使用结果（可选发送通知）
    elif context.event_type == HookEventType.POST_TOOL_USE:
        log_event(data, "记录工具使用结果")
        # 可选：如果需要发送通知，可以取消下面注释
        # tool_name = context.tool_name or ""
        # tool_result = context.tool_input or {}
        # message = f"工具 {tool_name} 执行完成"
        # asyncio.run(send_feishu_notification(message, "permission", context.event_type.value))

    # Notification / PermissionRequest: 发送通知卡片
    elif context.event_type in (HookEventType.NOTIFICATION, HookEventType.PERMISSION_REQUEST):
        # PermissionRequest: 只有 AskUserQuestion（单选/多选）才发送 ESC 取消等待
        if context.event_type == HookEventType.PERMISSION_REQUEST:
            tool_name = context.tool_name or ""
            tool_input = context.tool_input or {}
            # AskUserQuestion 需要发送 ESC，其他（如 Bash）正常等待用户选择
            if tool_name == "AskUserQuestion":
                log_event(data, "发送 ESC 取消等待")
                send_escape_to_tmux()
            message = build_permission_message(context, tool_input)
        else:
            message = context.notification_message or "收到通知"
        log_event(data, "发送通知卡片")
        await send_feishu_notification(message, "permission", context.event_type.value)


async def main():
    """主函数

    自动检测处理器，解析 stdin，收集数据并处理事件。

    Returns:
        None
    """
    # 自动检测处理器
    handler = detect_handler()

    # 读取 stdin
    stdin_data = None
    if not sys.stdin.isatty():
        try:
            stdin_data = sys.stdin.read()
        except Exception:
            pass

    # 解析上下文
    context = handler.parse_stdin(stdin_data or "{}")

    # 收集数据
    data = collect_all_data(handler, context, stdin_data)

    # 记录日志
    log_event(data)

    # 处理事件
    await handle_event(handler, context, data)


if __name__ == '__main__':
    asyncio.run(main())