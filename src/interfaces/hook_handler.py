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
        """处理器名称。"""
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




def detect_handler() -> IHookHandler:
    """返回 Claude Code Hook 处理器。Codex 使用 App Server 事件。"""
    return DefaultHookHandler()

# Alias for backwards compatibility
ClaudeHookHandler = DefaultHookHandler
