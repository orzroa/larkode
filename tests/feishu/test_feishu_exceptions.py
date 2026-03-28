"""
测试飞书异常类
"""
import pytest
from unittest.mock import patch
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestFeishuExceptions:
    """测试飞书异常类"""

    def test_feishu_api_error_with_base_import(self):
        """测试 FeishuAPIError 使用基础异常"""
        from src.feishu.exceptions import FeishuAPIError

        error = FeishuAPIError("test error")
        assert str(error) == "test error"

    def test_feishu_api_send_error(self):
        """测试 FeishuAPISendError"""
        from src.feishu.exceptions import FeishuAPISendError

        # PlatformMessageError 需要 platform 和 reason 参数
        error = FeishuAPISendError("feishu", "send failed")
        assert "send failed" in str(error)

    def test_feishu_api_upload_error(self):
        """测试 FeishuAPIUploadError"""
        from src.feishu.exceptions import FeishuAPIUploadError

        error = FeishuAPIUploadError("upload failed")
        assert str(error) == "upload failed"

    def test_feishu_api_error_inheritance(self):
        """测试异常继承关系"""
        from src.feishu.exceptions import (
            FeishuAPIError, FeishuAPISendError, FeishuAPIUploadError
        )
        from src.exceptions import PlatformError

        # 检查继承关系
        api_error = FeishuAPIError("test")
        upload_error = FeishuAPIUploadError("test")

        assert isinstance(api_error, PlatformError)
        assert isinstance(upload_error, PlatformError)

    def test_feishu_api_error_to_dict(self):
        """测试异常 to_dict 方法"""
        from src.feishu.exceptions import FeishuAPIError

        error = FeishuAPIError("test error")
        result = error.to_dict()

        assert "error" in result
        assert "message" in result
        assert result["message"] == "test error"

