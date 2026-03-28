"""
飞书模块异常类
"""

from src.exceptions import PlatformError, PlatformMessageError
from src.logging_utils import get_logger

logger = get_logger(__name__)


class FeishuAPIError(PlatformError):
    """飞书 API 基础异常"""
    pass


class FeishuAPISendError(PlatformMessageError):
    """飞书消息发送异常"""
    pass


class FeishuAPIUploadError(PlatformError):
    """飞书文件上传异常"""
    pass
