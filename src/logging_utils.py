"""
日志增强模块

提供结构化日志能力，支持上下文追踪。
"""
import logging
import sys
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# 全局上下文变量
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[str]] = ContextVar("user_id", default=None)
_message_number: ContextVar[Optional[str]] = ContextVar("message_number", default=None)


def set_request_id(request_id: str) -> None:
    """设置当前请求 ID"""
    _request_id.set(request_id)


def get_request_id() -> Optional[str]:
    """获取当前请求 ID"""
    return _request_id.get()


def set_user_id(user_id: str) -> None:
    """设置当前用户 ID"""
    _user_id.set(user_id)


def get_user_id() -> Optional[str]:
    """获取当前用户 ID"""
    return _user_id.get()


def set_message_number(message_number: str) -> None:
    """设置当前消息编号"""
    _message_number.set(message_number)


def get_message_number() -> Optional[str]:
    """获取当前消息编号"""
    return _message_number.get()


# 向后兼容别名
set_task_id = set_message_number
get_task_id = get_message_number


def clear_context() -> None:
    """清除所有上下文"""
    _request_id.set(None)
    _user_id.set(None)
    _message_number.set(None)


class StructuredFormatter(logging.Formatter):
    """结构化日志格式化器"""

    def format(self, record: logging.LogRecord) -> str:
        # 添加上下文信息
        extra = {
            "timestamp": datetime.now().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 添加请求上下文
        request_id = _request_id.get()
        user_id = _user_id.get()
        message_number = _message_number.get()

        if request_id:
            extra["request_id"] = request_id
        if user_id:
            extra["user_id"] = user_id
        if message_number:
            extra["message_number"] = message_number

        # 添加异常信息
        if record.exc_info:
            extra["exception"] = self.formatException(record.exc_info)

        # 添加额外字段
        if hasattr(record, "extra_fields"):
            extra.update(record.extra_fields)

        # 构建结构化日志
        import json

        # 尝试将消息作为 JSON 解析
        try:
            msg_data = json.loads(record.getMessage())
            extra["message"] = msg_data
        except (json.JSONDecodeError, ValueError):
            pass

        return json.dumps(extra, ensure_ascii=False, default=str)


class ContextLogger:
    """带上下文的日志记录器"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log_with_context(self, level: int, message: str, extra: Optional[Dict[str, Any]] = None, **kwargs):
        # 构建上下文
        context = {}
        if extra:
            context.update(extra)

        # 添加请求上下文
        request_id = _request_id.get()
        user_id = _user_id.get()
        message_number = _message_number.get()

        if request_id:
            context["request_id"] = request_id
        if user_id:
            context["user_id"] = user_id
        if message_number:
            context["message_number"] = message_number

        # 合并 kwargs 到 extra_fields
        if kwargs:
            context.update(kwargs)

        # 创建日志记录
        extra_fields = {"extra_fields": context}
        self.logger.log(level, message, extra=extra_fields)

    def debug(self, message: str, **kwargs):
        self._log_with_context(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs):
        self._log_with_context(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs):
        self._log_with_context(logging.WARNING, message, **kwargs)

    def error(self, message: str, **kwargs):
        self._log_with_context(logging.ERROR, message, **kwargs)

    def critical(self, message: str, **kwargs):
        self._log_with_context(logging.CRITICAL, message, **kwargs)

    def exception(self, message: str, **kwargs):
        self._log_with_context(logging.ERROR, message, **kwargs)


def setup_logging(
    log_dir: Path = Path("./logs"),
    log_level: str = "INFO",
    use_structured: bool = False,
) -> None:
    """
    配置日志系统

    Args:
        log_dir: 日志目录
        log_level: 日志级别
        use_structured: 是否使用结构化日志
    """
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)

    # 配置根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))

    # 清除现有处理器
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)

    if use_structured:
        # 使用结构化格式化器
        formatter = StructuredFormatter()
    else:
        # 使用标准格式化器
        formatter = logging.Formatter(
            "[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器（统一日志到 app.log）
    file_handler = logging.FileHandler(log_dir / "app.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # 错误日志单独文件
    error_handler = logging.FileHandler(log_dir / "error.log", encoding="utf-8")
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)


def get_logger(name: str) -> ContextLogger:
    """
    获取带上下文的日志记录器

    Args:
        name: 日志记录器名称

    Returns:
        ContextLogger 实例
    """
    return ContextLogger(name)


def get_module_logger(name: str) -> ContextLogger:
    """
    获取模块级别的日志记录器（简化版，无需 try/except）

    这是一个便捷函数，用于简化模块级别的 logger 获取。
    如果 logging_utils 不可用，会自动回退到标准 logging。

    用法：
        from src.logging_utils import get_module_logger
        logger = get_module_logger(__name__)

    Args:
        name: 日志记录器名称（通常传入 __name__）

    Returns:
        ContextLogger 实例
    """
    return get_logger(name)