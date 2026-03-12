"""
Hook 处理器接口定义
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

# 导入统一异常（如果可用）
try:
    from src.exceptions import BaseAppError, handle_exception
    HAS_NEW_EXCEPTIONS = True
except ImportError:
    HAS_NEW_EXCEPTIONS = False




class HookEventType(Enum):
    """Hook 事件类型"""
    USER_PROMPT_SUBMIT = "UserPromptSubmit"
    STOP = "Stop"
    NOTIFICATION = "Notification"
    PERMISSION_REQUEST = "PermissionRequest"  # Claude Code 兼容
    PRE_TOOL_USE = "PreToolUse"  # 工具使用前（新格式的权限请求）
    POST_TOOL_USE = "PostToolUse"  # 工具使用后
    POST_TOOL_USE_FAILURE = "PostToolUseFailure"  # 工具使用失败
    SUBAGENT_STOP = "SubagentStop"  # 子代理完成
    SESSION_START = "SessionStart"  # 会话开始
    SESSION_END = "SessionEnd"  # 会话结束
    ASK_USER_QUESTION = "AskUserQuestion"  # 独立问答事件
    CONFIG_CHANGE = "ConfigChange"  # 配置变更


@dataclass
class HookContext:
    """Hook 执行上下文"""
    event_type: HookEventType
    session_id: Optional[str] = None
    cwd: Optional[str] = None
    user_prompt: Optional[str] = None
    notification_message: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    last_assistant_message: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HookContext":
        """从字典创建上下文"""
        event_str = data.get("hook_event_name") or data.get("hook_event") or ""
        try:
            event_type = HookEventType(event_str)
        except ValueError:
            event_type = HookEventType.USER_PROMPT_SUBMIT

        # 获取 tool_name 和 tool_input，支持多种命名方式
        tool_name = data.get("tool_name") or data.get("toolName") or ""
        tool_input = data.get("tool_input") or data.get("toolInput") or {}

        return cls(
            event_type=event_type,
            session_id=data.get("session_id"),
            cwd=data.get("cwd"),
            user_prompt=data.get("user_prompt") or data.get("prompt"),
            notification_message=data.get("notification_message"),
            tool_name=tool_name,
            tool_input=tool_input,
            last_assistant_message=data.get("last_assistant_message"),
            raw_data=data,
        )


class IHookHandler(ABC):
    """Hook 处理器接口"""

    @property
    @abstractmethod
    def name(self) -> str:
        """处理器名称 (如 'claude', 'iflow')"""
        pass

    @abstractmethod
    def get_session_id(self) -> Optional[str]:
        """获取会话 ID"""
        pass

    @abstractmethod
    def get_cwd(self) -> Optional[str]:
        """获取工作目录"""
        pass

    @abstractmethod
    def parse_stdin(self, stdin_data: str) -> HookContext:
        """解析 stdin 数据"""
        pass

    @abstractmethod
    def should_handle(self, context: HookContext) -> bool:
        """判断是否应该处理此事件"""
        pass



class DefaultHookHandler(IHookHandler):
    """默认 Hook 处理器 (支持 Claude Code)"""

    @property
    def name(self) -> str:
        return "default"

    def get_session_id(self) -> Optional[str]:
        import os
        # 支持新的 AI_SESSION_ID 和旧的 CLAUDE_SESSION_ID
        return os.getenv("AI_SESSION_ID") or os.getenv("CLAUDE_SESSION_ID")

    def get_cwd(self) -> Optional[str]:
        import os
        # 支持新的 AI_WORKSPACE_DIR 和旧的 CLAUDE_CODE_DIR
        return os.getenv("AI_WORKSPACE_DIR") or os.getenv("CLAUDE_CODE_DIR")

    def parse_stdin(self, stdin_data: str) -> HookContext:
        """默认 AI CLI stdin 格式解析"""
        import json

        data = {}
        if stdin_data and stdin_data.strip():
            try:
                data = json.loads(stdin_data)
            except json.JSONDecodeError:
                pass

        # 使用命令行参数获取事件类型
        import sys
        event_str = data.get("hook_event_name") or (sys.argv[1] if len(sys.argv) > 1 else "")
        try:
            event_type = HookEventType(event_str)
        except ValueError:
            event_type = HookEventType.USER_PROMPT_SUBMIT

        # 获取 tool_name 和 tool_input，支持多种命名方式
        tool_name = data.get("tool_name") or data.get("toolName") or ""
        tool_input = data.get("tool_input") or data.get("toolInput") or {}

        return HookContext(
            event_type=event_type,
            session_id=data.get("session_id"),
            cwd=data.get("cwd"),
            user_prompt=data.get("prompt"),
            tool_name=tool_name,
            tool_input=tool_input,
            last_assistant_message=data.get("last_assistant_message"),
            raw_data=data,
        )

    def should_handle(self, context: HookContext) -> bool:
        """默认处理器处理所有事件"""
        return True




class IFlowHookHandler(IHookHandler):
    """iFlow CLI Hook 处理器"""

    @property
    def name(self) -> str:
        return "iflow"

    def get_session_id(self) -> Optional[str]:
        import os
        return os.getenv("IFLOW_SESSION_ID")

    def get_cwd(self) -> Optional[str]:
        import os
        return os.getenv("IFLOW_CWD")

    def _get_last_assistant_message_from_transcript(self, transcript_path: str) -> Optional[str]:
        """从 transcript 文件读取最后的 assistant 文本消息"""
        import json
        from pathlib import Path

        if not transcript_path:
            return None

        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            return None

        try:
            last_text_message = None
            with open(transcript_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        if entry.get("type") == "assistant":
                            message = entry.get("message", {})
                            content = message.get("content", [])
                            # 查找 text 类型的内容
                            for item in content:
                                if item.get("type") == "text":
                                    text = item.get("text", "")
                                    if text.strip():
                                        last_text_message = text
                    except json.JSONDecodeError:
                        continue
            return last_text_message
        except Exception:
            return None

    def parse_stdin(self, stdin_data: str) -> HookContext:
        """iFlow CLI stdin 格式解析"""
        import json

        data = {}
        if stdin_data and stdin_data.strip():
            try:
                data = json.loads(stdin_data)
            except json.JSONDecodeError:
                pass

        context = HookContext.from_dict(data)

        # iFlow CLI 不传递 last_assistant_message，需要从 transcript 文件读取
        if not context.last_assistant_message:
            transcript_path = data.get("transcript_path", "")
            context.last_assistant_message = self._get_last_assistant_message_from_transcript(transcript_path)

        return context

    def should_handle(self, context: HookContext) -> bool:
        """iFlow CLI 处理所有事件"""
        return True


def detect_handler() -> IHookHandler:
    """自动检测当前环境使用的处理器"""
    import os

    # 优先检测 iFlow CLI 环境
    if any(os.getenv(key) for key in ["IFLOW_CLI", "IFLOW_SESSION_ID", "IFLOW_HOOK_EVENT_NAME"]):
        return IFlowHookHandler()

    # 默认使用默认处理器
    return DefaultHookHandler()

# Alias for backwards compatibility
ClaudeHookHandler = DefaultHookHandler
