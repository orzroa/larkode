"""
MiniMax 异常定义
"""
from typing import Optional, Dict, Any


class MiniMaxError(Exception):
    """MiniMax 基础异常"""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.code = code or "MINIMAX_ERROR"
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error": self.__class__.__name__,
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class MiniMaxAPIError(MiniMaxError):
    """MiniMax API 调用失败"""

    def __init__(self, message: str, status_code: int = 0, response_data: Optional[Dict] = None):
        super().__init__(
            message,
            code="MINIMAX_API_ERROR",
            details={"status_code": status_code, "response": response_data or {}},
        )
        self.status_code = status_code
        self.response_data = response_data or {}


class MiniMaxUploadError(MiniMaxError):
    """MiniMax 文件上传失败"""

    def __init__(self, message: str, file_path: str = ""):
        super().__init__(
            message,
            code="MINIMAX_UPLOAD_ERROR",
            details={"file_path": file_path},
        )


class MiniMaxTimeoutError(MiniMaxError):
    """MiniMax 任务超时"""

    def __init__(self, task_id: str, timeout: int):
        super().__init__(
            f"MiniMax 任务超时: {task_id}",
            code="MINIMAX_TIMEOUT",
            details={"task_id": task_id, "timeout": timeout},
        )


class MiniMaxAuthError(MiniMaxAPIError):
    """MiniMax 认证失败"""

    def __init__(self, message: str = "MiniMax API Key 无效或已过期"):
        super().__init__(message, status_code=401)
        self.code = "MINIMAX_AUTH_ERROR"


class MiniMaxRateLimitError(MiniMaxAPIError):
    """MiniMax 频率限制"""

    def __init__(self, message: str = "请求频率超限，请稍后重试"):
        super().__init__(message, status_code=429)
        self.code = "MINIMAX_RATE_LIMIT"
