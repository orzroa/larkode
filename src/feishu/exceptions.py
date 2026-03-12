"""
飞书模块异常类
"""

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


# 尝试使用统一异常体系，否则使用本地定义
try:
    from src.exceptions import BaseAppError as _BaseAppError, PlatformError, PlatformMessageError

    class FeishuAPIError(PlatformError):
        """飞书 API 基础异常"""
        pass

    class FeishuAPISendError(PlatformMessageError):
        """飞书消息发送异常"""
        pass

    class FeishuAPIUploadError(PlatformError):
        """飞书文件上传异常"""
        pass

except ImportError:
    class FeishuAPIError(Exception):
        """飞书 API 基础异常"""
        pass

    class FeishuAPISendError(FeishuAPIError):
        """飞书消息发送异常"""
        pass

    class FeishuAPIUploadError(FeishuAPIError):
        """飞书文件上传异常"""
        pass
