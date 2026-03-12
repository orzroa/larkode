"""
集成测试：飞书图片上传下载完整流程
"""
import pytest
import asyncio
import json
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.feishu.file_ops import upload_image, download_file
from src.config.settings import get_settings


class TestImageUploadDownload:
    """测试飞书图片上传下载完整流程"""

    def setup_method(self):
        """设置测试环境"""
        self.save_dir = PROJECT_ROOT / "uploads"
        self.save_dir.mkdir(parents=True, exist_ok=True)
        # 使用素材目录中的金黄色五角星测试图片
        self.test_image_path = PROJECT_ROOT / "tests" / "fixtures" / "images" / "yellow_star.png"

    def teardown_method(self):
        """清理测试环境"""
        if self.save_dir.exists():
            import shutil
            shutil.rmtree(self.save_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_upload_and_download_yellow_star(self):
        """测试上传金黄色五角星图片后再下载的完整流程"""
        settings = get_settings()

        # 确认测试图片存在
        assert self.test_image_path.exists(), f"测试图片不存在: {self.test_image_path}"
        print(f"\n🔍 测试图片: {self.test_image_path}")
        print(f"   图片大小: {self.test_image_path.stat().st_size} bytes")

        # 1. 上传测试图片，获取 image_key
        print(f"\n🔍 上传测试图片")
        image_key = await upload_image(
            settings.FEISHU_APP_SECRET,
            self.test_image_path
        )

        assert image_key is not None, "上传图片失败"
        print(f"   上传成功, image_key: {image_key}")

        # 2. 发送图片消息，获取 message_id
        print(f"\n🔍 发送图片消息")

        import lark_oapi as lark
        client = lark.Client.builder() \
            .app_id(settings.FEISHU_APP_ID) \
            .app_secret(settings.FEISHU_APP_SECRET) \
            .domain(getattr(lark, settings.FEISHU_MESSAGE_DOMAIN)) \
            .log_level(lark.LogLevel.WARNING) \
            .build()

        # 构建图片消息内容
        content = json.dumps({"image_key": image_key})
        request = lark.api.im.v1.CreateMessageRequest.builder() \
            .receive_id_type(settings.FEISHU_MESSAGE_RECEIVE_ID_TYPE) \
            .request_body(
                lark.api.im.v1.CreateMessageRequestBody.builder()
                .msg_type("image")
                .receive_id(settings.FEISHU_HOOK_NOTIFICATION_USER_ID)
                .content(content)
                .build()
            ) \
            .build()

        response = client.im.v1.message.create(request)

        assert response.success(), f"发送图片消息失败: {response.code} - {response.msg}"
        message_id = response.data.message_id
        print(f"   发送成功, message_id: {message_id}")

        # 3. 下载图片
        print(f"\n🔍 下载图片")
        result = await download_file(
            settings.FEISHU_APP_SECRET,
            message_id,
            image_key,
            self.save_dir
        )

        assert result is not None, "下载图片失败"
        assert result.exists(), f"下载的图片文件不存在: {result}"
        print(f"   保存路径: {result}")
        print(f"   文件大小: {result.stat().st_size} bytes")

        # 验证文件不为空
        file_size = result.stat().st_size
        assert file_size > 0, f"图片文件为空: {file_size}"
        print(f"\n✅ 金黄色五角星图片上传下载测试成功!")
