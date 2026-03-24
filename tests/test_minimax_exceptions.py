"""
MiniMax 异常测试
"""
import pytest

from src.minimax.exceptions import (
    MiniMaxError,
    MiniMaxAPIError,
    MiniMaxAuthError,
    MiniMaxRateLimitError,
    MiniMaxUploadError,
    MiniMaxTimeoutError,
)


class TestMiniMaxExceptions:
    """MiniMax 异常测试"""

    def test_base_exception(self):
        """测试基础异常"""
        err = MiniMaxError("test error")
        assert str(err) == "test error"
        assert err.code == "MINIMAX_ERROR"
        assert err.details == {}

    def test_base_exception_with_details(self):
        """测试带详细信息的异常"""
        err = MiniMaxError("test", code="TEST", details={"key": "value"})
        assert err.code == "TEST"
        assert err.details == {"key": "value"}

    def test_to_dict(self):
        """测试转换为字典"""
        err = MiniMaxError("test error", code="TEST", details={"a": 1})
        d = err.to_dict()
        assert d["error"] == "MiniMaxError"
        assert d["code"] == "TEST"
        assert d["message"] == "test error"
        assert d["details"] == {"a": 1}

    def test_api_error(self):
        """测试 API 错误"""
        err = MiniMaxAPIError("API failed", status_code=500, response_data={"msg": "server error"})
        assert err.status_code == 500
        assert err.response_data == {"msg": "server error"}
        assert err.code == "MINIMAX_API_ERROR"

    def test_auth_error(self):
        """测试认证错误"""
        err = MiniMaxAuthError()
        assert err.code == "MINIMAX_AUTH_ERROR"
        assert err.status_code == 401

    def test_auth_error_with_message(self):
        """测试带消息的认证错误"""
        err = MiniMaxAuthError("Custom auth error")
        assert "Custom auth error" in str(err)

    def test_rate_limit_error(self):
        """测试频率限制错误"""
        err = MiniMaxRateLimitError()
        assert err.code == "MINIMAX_RATE_LIMIT"
        assert err.status_code == 429

    def test_upload_error(self):
        """测试上传错误"""
        err = MiniMaxUploadError("Upload failed", file_path="/path/to/file")
        assert err.code == "MINIMAX_UPLOAD_ERROR"
        assert err.details["file_path"] == "/path/to/file"

    def test_timeout_error(self):
        """测试超时错误"""
        err = MiniMaxTimeoutError(task_id="task-123", timeout=60)
        assert err.code == "MINIMAX_TIMEOUT"
        assert err.details["task_id"] == "task-123"
        assert err.details["timeout"] == 60
