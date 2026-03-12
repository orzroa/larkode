"""
统一异常定义模块

提供项目统一的异常体系，便于错误处理和日志追踪。
"""
from typing import Optional, Any, Dict


class BaseAppError(Exception):
    """应用基础异常类"""

    def __init__(self, message: str, code: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


# ==================== 配置相关异常 ====================

class ConfigError(BaseAppError):
    """配置相关异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="CONFIG_ERROR", details=details)


class ConfigNotFoundError(ConfigError):
    """配置项不存在"""
    def __init__(self, key: str):
        super().__init__(f"配置项不存在: {key}", details={"key": key})
        self.code = "CONFIG_NOT_FOUND"


class ConfigValidationError(ConfigError):
    """配置验证失败"""
    def __init__(self, key: str, reason: str):
        super().__init__(f"配置验证失败: {key}", details={"key": key, "reason": reason})
        self.code = "CONFIG_VALIDATION_ERROR"


# ==================== 消息处理异常 ====================

class MessageError(BaseAppError):
    """消息处理基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="MESSAGE_ERROR", details=details)


class MessageParseError(MessageError):
    """消息解析失败"""
    def __init__(self, raw_message: str, reason: str):
        super().__init__(f"消息解析失败: {reason}", details={"raw_message": raw_message[:100], "reason": reason})
        self.code = "MESSAGE_PARSE_ERROR"


class MessageHandleError(MessageError):
    """消息处理失败"""
    def __init__(self, message_id: str, reason: str):
        super().__init__(f"消息处理失败: {reason}", details={"message_id": message_id, "reason": reason})
        self.code = "MESSAGE_HANDLE_ERROR"


# ==================== 任务管理异常 ====================

class TaskError(BaseAppError):
    """任务管理基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="TASK_ERROR", details=details)


class TaskNotFoundError(TaskError):
    """任务不存在"""
    def __init__(self, task_id: str):
        super().__init__(f"任务不存在: {task_id}", details={"task_id": task_id})
        self.code = "TASK_NOT_FOUND"


class TaskTimeoutError(TaskError):
    """任务执行超时"""
    def __init__(self, task_id: str, timeout: int):
        super().__init__(f"任务执行超时: {task_id}", details={"task_id": task_id, "timeout": timeout})
        self.code = "TASK_TIMEOUT"


class TaskCancelledError(TaskError):
    """任务被取消"""
    def __init__(self, task_id: str):
        super().__init__(f"任务被取消: {task_id}", details={"task_id": task_id})
        self.code = "TASK_CANCELLED"


# ==================== AI 执行异常 ====================

class AIError(BaseAppError):
    """AI 执行基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="AI_ERROR", details=details)


class AISessionError(AIError):
    """AI 会话异常"""
    def __init__(self, session_id: str, reason: str):
        super().__init__(f"AI 会话错误: {reason}", details={"session_id": session_id, "reason": reason})
        self.code = "AI_SESSION_ERROR"


class AIExecutionError(AIError):
    """AI 命令执行失败"""
    def __init__(self, command: str, reason: str):
        super().__init__(f"AI 命令执行失败: {reason}", details={"command": command, "reason": reason})
        self.code = "AI_EXECUTION_ERROR"


class AIRestartError(AIError):
    """AI 进程重启失败"""
    def __init__(self, reason: str, attempts: int):
        super().__init__(f"AI 进程重启失败: {reason}", details={"reason": reason, "attempts": attempts})
        self.code = "AI_RESTART_ERROR"


# ==================== 存储相关异常 ====================

class StorageError(BaseAppError):
    """存储层基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="STORAGE_ERROR", details=details)


class StorageNotFoundError(StorageError):
    """数据不存在"""
    def __init__(self, table: str, key: str):
        super().__init__(f"数据不存在: {table}.{key}", details={"table": table, "key": key})
        self.code = "STORAGE_NOT_FOUND"


class StorageWriteError(StorageError):
    """数据写入失败"""
    def __init__(self, table: str, reason: str):
        super().__init__(f"数据写入失败: {reason}", details={"table": table, "reason": reason})
        self.code = "STORAGE_WRITE_ERROR"


# ==================== 平台相关异常 ====================

class PlatformError(BaseAppError):
    """平台基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="PLATFORM_ERROR", details=details)


class PlatformConnectionError(PlatformError):
    """平台连接失败"""
    def __init__(self, platform: str, reason: str):
        super().__init__(f"{platform} 连接失败: {reason}", details={"platform": platform, "reason": reason})
        self.code = "PLATFORM_CONNECTION_ERROR"


class PlatformMessageError(PlatformError):
    """平台消息发送失败"""
    def __init__(self, platform: str, reason: str):
        super().__init__(f"{platform} 消息发送失败: {reason}", details={"platform": platform, "reason": reason})
        self.code = "PLATFORM_MESSAGE_ERROR"


# ==================== Hook 异常 ====================

class HookError(BaseAppError):
    """Hook 基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="HOOK_ERROR", details=details)


class HookExecutionError(HookError):
    """Hook 执行失败"""
    def __init__(self, hook_name: str, reason: str):
        super().__init__(f"Hook 执行失败: {hook_name}", details={"hook_name": hook_name, "reason": reason})
        self.code = "HOOK_EXECUTION_ERROR"


# ==================== 网络/WebSocket 异常 ====================

class NetworkError(BaseAppError):
    """网络相关基础异常"""
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, code="NETWORK_ERROR", details=details)


class WebSocketError(NetworkError):
    """WebSocket 异常"""
    def __init__(self, reason: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(f"WebSocket 错误: {reason}", details=details)
        self.code = "WEBSOCKET_ERROR"


class WebSocketConnectionError(WebSocketError):
    """WebSocket 连接失败"""
    def __init__(self, url: str, reason: str):
        super().__init__(f"WebSocket 连接失败: {reason}", details={"url": url, "reason": reason})
        self.code = "WEBSOCKET_CONNECTION_ERROR"


# ==================== 工具函数 ====================

def handle_exception(e: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    将异常转换为统一的字典格式

    Args:
        e: 异常对象
        context: 额外的上下文信息

    Returns:
        包含错误信息的字典
    """
    if isinstance(e, BaseAppError):
        result = e.to_dict()
    else:
        result = {
            "error": e.__class__.__name__,
            "code": "INTERNAL_ERROR",
            "message": str(e),
            "details": {},
        }

    if context:
        result["context"] = context

    return result
