"""
异常模块单元测试
"""
import pytest
from src.exceptions import (
    BaseAppError,
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    TaskError,
    TaskNotFoundError,
    TaskTimeoutError,
    TaskCancelledError,
    AIError,
    AISessionError,
    StorageError,
    StorageNotFoundError,
    PlatformError,
    PlatformConnectionError,
    handle_exception,
)


class TestBaseAppError:
    """测试基础异常类"""

    def test_base_error_creation(self):
        """测试基础异常创建"""
        error = BaseAppError("测试错误", code="TEST_ERROR")
        assert error.message == "测试错误"
        assert error.code == "TEST_ERROR"
        assert error.details == {}

    def test_base_error_with_details(self):
        """测试带详情的异常"""
        error = BaseAppError("测试错误", code="TEST_ERROR", details={"key": "value"})
        assert error.details == {"key": "value"}

    def test_base_error_to_dict(self):
        """测试异常转字典"""
        error = BaseAppError("测试错误", code="TEST_ERROR", details={"key": "value"})
        result = error.to_dict()

        assert result["error"] == "BaseAppError"
        assert result["code"] == "TEST_ERROR"
        assert result["message"] == "测试错误"
        assert result["details"] == {"key": "value"}


class TestConfigErrors:
    """测试配置相关异常"""

    def test_config_error(self):
        """测试配置错误"""
        error = ConfigError("配置错误")
        assert error.code == "CONFIG_ERROR"

    def test_config_not_found_error(self):
        """测试配置不存在异常"""
        error = ConfigNotFoundError("API_KEY")
        assert error.code == "CONFIG_NOT_FOUND"
        assert error.details["key"] == "API_KEY"

    def test_config_validation_error(self):
        """测试配置验证失败异常"""
        error = ConfigValidationError("API_KEY", "Invalid format")
        assert error.code == "CONFIG_VALIDATION_ERROR"
        assert error.details["key"] == "API_KEY"
        assert error.details["reason"] == "Invalid format"


class TestTaskErrors:
    """测试任务相关异常"""

    def test_task_error(self):
        """测试任务错误"""
        error = TaskError("任务错误")
        assert error.code == "TASK_ERROR"

    def test_task_not_found_error(self):
        """测试任务不存在异常"""
        error = TaskNotFoundError("task123")
        assert error.code == "TASK_NOT_FOUND"
        assert error.details["task_id"] == "task123"

    def test_task_timeout_error(self):
        """测试任务超时异常"""
        error = TaskTimeoutError("task123", 300)
        assert error.code == "TASK_TIMEOUT"
        assert error.details["timeout"] == 300

    def test_task_cancelled_error(self):
        """测试任务取消异常"""
        error = TaskCancelledError("task123")
        assert error.code == "TASK_CANCELLED"


class TestAIErrors:
    """测试 AI 相关异常"""

    def test_ai_error(self):
        """测试 AI 错误"""
        error = AIError("AI 错误")
        assert error.code == "AI_ERROR"

    def test_ai_session_error(self):
        """测试 AI 会话异常"""
        error = AISessionError("session123", "Session not found")
        assert error.code == "AI_SESSION_ERROR"
        assert error.details["session_id"] == "session123"


class TestStorageErrors:
    """测试存储相关异常"""

    def test_storage_error(self):
        """测试存储错误"""
        error = StorageError("存储错误")
        assert error.code == "STORAGE_ERROR"

    def test_storage_not_found_error(self):
        """测试数据不存在异常"""
        error = StorageNotFoundError("users", "user123")
        assert error.code == "STORAGE_NOT_FOUND"
        assert error.details["table"] == "users"


class TestPlatformErrors:
    """测试平台相关异常"""

    def test_platform_error(self):
        """测试平台错误"""
        error = PlatformError("平台错误")
        assert error.code == "PLATFORM_ERROR"

    def test_platform_connection_error(self):
        """测试平台连接异常"""
        error = PlatformConnectionError("feishu", "Connection refused")
        assert error.code == "PLATFORM_CONNECTION_ERROR"
        assert error.details["platform"] == "feishu"


class TestHandleException:
    """测试异常处理工具函数"""

    def test_handle_base_app_error(self):
        """测试处理 BaseAppError"""
        error = ConfigError("测试错误", details={"key": "value"})
        result = handle_exception(error)

        assert result["code"] == "CONFIG_ERROR"
        assert result["message"] == "测试错误"

    def test_handle_standard_exception(self):
        """测试处理标准异常"""
        error = ValueError("测试值错误")
        result = handle_exception(error)

        assert result["code"] == "INTERNAL_ERROR"
        assert result["message"] == "测试值错误"

    def test_handle_exception_with_context(self):
        """测试带上下文的异常处理"""
        error = ConfigError("测试错误")
        context = {"user_id": "user123", "action": "login"}
        result = handle_exception(error, context)

        assert result["context"] == context
