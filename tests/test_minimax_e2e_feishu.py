"""
MiniMax 真实飞书发送 E2E 测试

此测试真实调用 MiniMax API 生成图片/语音，下载后发送到飞书。
需要飞书 bot 已配置好，能真实收到消息。

运行方式（默认跳过，需显式指定 -m e2e）：
    FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx MINIMAX_API_KEY=xxx \
    uv run pytest tests/test_minimax_e2e_feishu.py -v -n0 -s -m e2e
"""
import asyncio
import base64
import os
import pytest
import tempfile
from pathlib import Path

# 标记为 e2e 测试，默认跳过
pytestmark = pytest.mark.e2e

# 前置条件检查
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")


def require_api_key(f):
    return pytest.mark.skipif(not MINIMAX_API_KEY, reason="MINIMAX_API_KEY 未设置")(f)


def require_feishu(f):
    return pytest.mark.skipif(
        not os.environ.get("FEISHU_APP_ID") or not os.environ.get("FEISHU_APP_SECRET"),
        reason="FEISHU_APP_ID 或 FEISHU_APP_SECRET 未设置",
    )(f)


class TestMiniMaxRealFeishuDelivery:
    """
    真实发送到飞书的 E2E 测试

    运行方式（需要真实的飞书 bot 配置）：
        FEISHU_APP_ID=xxx FEISHU_APP_SECRET=xxx MINIMAX_API_KEY=xxx \
        uv run pytest tests/test_minimax_e2e_feishu.py -v -n0 -s

    测试会将图片和语音真实发送到飞书，需要指定接收用户。
    可以通过 FEISHU_TARGET_USER_ID 环境变量指定目标用户 open_id，
    如果未指定则跳过（需要手动验证）。
    """

    @require_api_key
    @pytest.mark.asyncio
    async def test_real_image_to_feishu(self):
        """生成图片并真实发送到飞书"""
        from src.minimax.client import MiniMaxClient
        from src.feishu.api import FeishuAPI
        from src.config.settings import get_settings

        settings = get_settings()
        target_user = os.environ.get("FEISHU_TARGET_USER_ID", "")

        if not target_user:
            pytest.skip("FEISHU_TARGET_USER_ID 未设置，无法真实发送")

        # 1. 生成图片
        print(f"\n🎨 生成图片...")
        client = MiniMaxClient(api_key=MINIMAX_API_KEY)
        try:
            result = await client.image_generation(
                prompt="画一只可爱的橘色狸花猫，写实风格，高清",
                response_format="base64",
            )
            img_b64 = result["image_base64"][0]
            print(f"✅ 图片生成成功，base64 长度: {len(img_b64)}")
        finally:
            await client.close()

        # 2. 保存到临时文件
        with tempfile.TemporaryDirectory() as tmpdir:
            img_path = Path(tmpdir) / "cat.jpg"
            with open(img_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
            size = img_path.stat().st_size
            print(f"✅ 图片保存: {img_path} ({size // 1024} KB)")

            # 3. 发飞书
            print(f"📨 发送到飞书 user_id={target_user}...")
            feishu = FeishuAPI(app_id=settings.FEISHU_APP_ID, app_secret=settings.FEISHU_APP_SECRET)

            # 先发进度消息
            await feishu.send_message(target_user, "🎨 正在上传图片...")

            # 上传图片
            image_key = await feishu.upload_image(img_path)
            assert image_key, "图片上传失败"
            print(f"✅ 图片上传成功: {image_key}")

            # 发送图片消息
            success = await feishu.send_image_message(target_user, image_key)
            assert success, "图片消息发送失败"
            print(f"✅ 图片消息发送成功！")

    @require_api_key
    @pytest.mark.asyncio
    async def test_real_tts_to_feishu(self):
        """生成语音并真实发送到飞书"""
        from src.minimax.client import MiniMaxClient
        from src.feishu.api import FeishuAPI
        from src.config.settings import get_settings

        settings = get_settings()
        target_user = os.environ.get("FEISHU_TARGET_USER_ID", "")

        if not target_user:
            pytest.skip("FEISHU_TARGET_USER_ID 未设置，无法真实发送")

        # 1. 生成 TTS
        print(f"\n🔊 生成语音...")
        client = MiniMaxClient(api_key=MINIMAX_API_KEY)
        try:
            audio_bytes = await client.text_to_speech(
                text="你好，我是一只可爱的狸花猫，今天天气真好！",
                voice_id="male-qn-qingse",
                model="speech-2.8-hd",
            )
            print(f"✅ TTS 生成成功: {len(audio_bytes)} bytes")
        finally:
            await client.close()

        # 2. 保存
        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = Path(tmpdir) / "tts_output.mp3"
            with open(audio_path, "wb") as f:
                f.write(audio_bytes)
            print(f"✅ 语音保存: {audio_path} ({audio_path.stat().st_size // 1024} KB)")

            # 3. 发飞书
            print(f"📨 发送到飞书 user_id={target_user}...")
            feishu = FeishuAPI(app_id=settings.FEISHU_APP_ID, app_secret=settings.FEISHU_APP_SECRET)

            # 上传音频
            file_key = await feishu.upload_audio(audio_path)
            assert file_key, "音频上传失败"
            print(f"✅ 音频上传成功: {file_key}")

            # 发送音频消息
            success = await feishu.send_audio_message(target_user, file_key)
            assert success, "音频消息发送失败"
            print(f"✅ 音频消息发送成功！")
