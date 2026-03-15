"""
日志工具单元测试
"""
import pytest
import json
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestLoggingUtils:
    """测试日志工具模块"""

    def test_get_logger(self):
        """测试获取日志记录器"""
        from src.logging_utils import get_logger

        logger = get_logger("test")
        assert logger is not None
        assert logger.logger.name == "test"

    def test_context_variables(self):
        """测试上下文变量"""
        from src.logging_utils import (
            set_user_id, get_user_id,
            set_task_id, get_task_id,
            set_request_id, get_request_id,
            clear_context
        )

        # 测试 user_id
        set_user_id("user123")
        assert get_user_id() == "user123"

        # 测试 task_id
        set_task_id("task456")
        assert get_task_id() == "task456"

        # 测试 request_id
        set_request_id("req789")
        assert get_request_id() == "req789"

        # 测试 clear_context
        clear_context()
        assert get_user_id() is None
        assert get_task_id() is None
        assert get_request_id() is None

    def test_context_logger_info(self):
        """测试 ContextLogger info 方法"""
        from src.logging_utils import get_logger, set_user_id, clear_context

        logger = get_logger("test_info")
        set_user_id("test_user")

        # 不应该抛出异常
        logger.info("测试消息", action="test")

        clear_context()

    def test_context_logger_error(self):
        """测试 ContextLogger error 方法"""
        from src.logging_utils import get_logger, set_task_id, clear_context

        logger = get_logger("test_error")
        set_task_id("test_task")

        logger.error("错误消息", error_code=500)

        clear_context()


class TestWorkspaceFormatter:
    """测试 WorkspaceFormatter"""

    def test_format_with_workspace(self):
        """测试带工作空间的格式化"""
        from src.logging_utils import WorkspaceFormatter

        formatter = WorkspaceFormatter(
            fmt='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Mock workspace_manager
        with patch('src.workspace_manager.get_workspace_manager') as mock_wm:
            mock_wm.return_value.get_current_workspace.return_value = "/home/test/myproject"

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="test message",
                args=(),
                exc_info=None
            )

            formatted = formatter.format(record)
            # 应该包含工作空间名称
            assert "myproject" in formatted
            assert "test message" in formatted

    def test_format_without_workspace(self):
        """测试无工作空间的格式化"""
        from src.logging_utils import WorkspaceFormatter

        formatter = WorkspaceFormatter(
            fmt='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Mock workspace_manager 返回 None
        with patch('src.workspace_manager.get_workspace_manager') as mock_wm:
            mock_wm.return_value.get_current_workspace.return_value = None

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="test message",
                args=(),
                exc_info=None
            )

            formatted = formatter.format(record)
            # 应该包含默认工作空间名称
            assert "default" in formatted
            assert "test message" in formatted

    def test_format_with_exception(self):
        """测试 workspace_manager 抛出异常的情况"""
        from src.logging_utils import WorkspaceFormatter

        formatter = WorkspaceFormatter(
            fmt='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Mock workspace_manager 抛出异常
        with patch('src.workspace_manager.get_workspace_manager') as mock_wm:
            mock_wm.side_effect = Exception("test error")

            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="test message",
                args=(),
                exc_info=None
            )

            formatted = formatter.format(record)
            # 应该包含默认工作空间名称（异常被捕获）
            assert "default" in formatted
            assert "test message" in formatted


class TestSetupLogging:
    """测试日志配置"""

    def test_setup_logging_standard(self):
        """测试标准日志配置"""
        from src.logging_utils import setup_logging
        import logging

        # 不应该抛出异常
        setup_logging(
            log_dir=Path("./logs"),
            log_level="INFO",
            use_structured=False
        )

        # 验证日志级别
        assert logging.getLogger().level == logging.INFO

    def test_setup_logging_structured(self):
        """测试结构化日志配置"""
        from src.logging_utils import setup_logging
        import logging

        setup_logging(
            log_dir=Path("./logs"),
            log_level="DEBUG",
            use_structured=True
        )

        assert logging.getLogger().level == logging.DEBUG
