"""
MiniMax 端到端测试

此测试模块用于真实调用 MiniMax API。

前置条件：
1. 环境变量 MINIMAX_API_KEY 已设置

测试范围：
- ✅ 图片生成 (#mm img) - model=image-01, base_url=api.minimaxi.com
- ✅ TTS (#mm tts) - model=speech-2.8-hd, voice=male-qn-qingse (默认)
- ⚠️  音乐生成 (#mm music) - 需要开通 music 权限（可能不支持）
- ❌ 视频生成 - 不在本测试范围内

注意：
- base URL: https://api.minimaxi.com（不是 api.minimax.io）
- TTS 可用 voice: male-qn-qingse, English_expressive_narrator 等

运行方式：
    # 默认跳过，需要显式指定 -m e2e 才运行
    uv run pytest tests/test_minimax_e2e_image.py -v -m e2e -s
"""
import os
import time
import pytest
import tempfile
from pathlib import Path

# 标记为 e2e 测试，默认跳过
pytestmark = pytest.mark.e2e

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_GROUP_ID = os.environ.get("MINIMAX_GROUP_ID", "")


def require_api_key(f):
    """装饰器：需要有效的 API Key"""
    return pytest.mark.skipif(
        not MINIMAX_API_KEY,
        reason="MINIMAX_API_KEY 未设置",
    )(f)


class TestMiniMaxImageGenerationE2E:
    """MiniMax 图片生成端到端测试"""

    @require_api_key
    @pytest.mark.asyncio
    async def test_img_generation_url(self):
        """真实调用 MiniMax 图片生成 API（URL 格式）"""
        from src.minimax.client import MiniMaxClient

        client = MiniMaxClient(
            api_key=MINIMAX_API_KEY,
            group_id=MINIMAX_GROUP_ID or None,
        )
        try:
            result = await client.image_generation(
                prompt="一只可爱的橘色狸花猫，写实风格，高清",
                response_format="url",
            )

            # 打印原始响应（调试用）
            print(f"\nAPI 原始响应: {result}")

            # 验证返回格式
            assert "image_urls" in result, f"返回格式错误，缺少 image_urls: {result}"
            assert len(result["image_urls"]) > 0, "未返回任何图片 URL"

            image_url = result["image_urls"][0]
            print(f"✅ 图片 URL: {image_url[:80]}...")

            # 下载图片并验证
            import httpx
            with tempfile.TemporaryDirectory() as tmpdir:
                async with httpx.AsyncClient(timeout=30.0) as http:
                    resp = await http.get(image_url)
                    resp.raise_for_status()

                img_path = Path(tmpdir) / "cat.png"
                with open(img_path, "wb") as f:
                    f.write(resp.content)

                size = img_path.stat().st_size
                assert size > 1000, f"图片太小: {size} bytes"

                # 验证 PNG/JPEG 格式
                with open(img_path, "rb") as f:
                    header = f.read(8)
                is_png = header[:8] == b'\x89PNG\r\n\x1a\n'
                is_jpeg = header[:2] == b'\xff\xd8'
                assert is_png or is_jpeg, f"无效图片格式: {header[:4].hex()}"
                fmt = "PNG" if is_png else "JPEG"
                print(f"✅ 图片下载成功: {fmt}, {size} bytes, 保存至: {img_path}")

        finally:
            await client.close()

    @require_api_key
    @pytest.mark.asyncio
    async def test_img_generation_base64(self):
        """真实调用 MiniMax 图片生成 API（Base64 格式）"""
        from src.minimax.client import MiniMaxClient

        client = MiniMaxClient(
            api_key=MINIMAX_API_KEY,
            group_id=MINIMAX_GROUP_ID or None,
        )
        try:
            result = await client.image_generation(
                prompt="a cute orange tabby cat, realistic style",
                response_format="base64",
            )
            print(f"\nAPI 原始响应 keys: {result.keys()}")

            assert "image_base64" in result, f"返回格式错误，缺少 image_base64: {result}"
            assert len(result["image_base64"]) > 0, "未返回任何图片数据"

            with tempfile.TemporaryDirectory() as tmpdir:
                img_path = Path(tmpdir) / "cat_base64.png"
                import base64
                with open(img_path, "wb") as f:
                    f.write(base64.b64decode(result["image_base64"][0]))

                size = img_path.stat().st_size
                assert size > 1000, f"图片太小: {size} bytes"
                print(f"✅ Base64 图片生成成功: {size} bytes")

        finally:
            await client.close()


class TestMiniMaxTTSE2E:
    """MiniMax TTS 端到端测试"""

    @require_api_key
    @pytest.mark.asyncio
    async def test_tts_generation(self):
        """真实调用 MiniMax TTS API"""
        from src.minimax.client import MiniMaxClient

        client = MiniMaxClient(
            api_key=MINIMAX_API_KEY,
            group_id=MINIMAX_GROUP_ID or None,
        )
        try:
            # 使用 male-qn-qingse（中文音色）
            audio_bytes = await client.text_to_speech(
                text="今天天气真好，适合出去散步。",
                voice_id="male-qn-qingse",
                model="speech-2.8-hd",
            )

            assert audio_bytes, "TTS 未返回音频数据"
            assert len(audio_bytes) > 100, f"音频太小: {len(audio_bytes)} bytes"

            # 保存到临时文件
            with tempfile.TemporaryDirectory() as tmpdir:
                audio_path = Path(tmpdir) / "tts_output.mp3"
                with open(audio_path, "wb") as f:
                    f.write(audio_bytes)

                size = audio_path.stat().st_size
                print(f"✅ TTS 生成成功: {size} bytes, 保存至: {audio_path}")

        finally:
            await client.close()

    @require_api_key
    @pytest.mark.asyncio
    async def test_tts_english(self):
        """真实调用 MiniMax TTS API（英文音色）"""
        from src.minimax.client import MiniMaxClient

        client = MiniMaxClient(api_key=MINIMAX_API_KEY)
        try:
            audio_bytes = await client.text_to_speech(
                text="Hello, how are you today?",
                voice_id="English_expressive_narrator",
                model="speech-2.8-hd",
            )

            assert audio_bytes and len(audio_bytes) > 100
            print(f"✅ TTS 英文音色成功: {len(audio_bytes)} bytes")

        finally:
            await client.close()


class TestMiniMaxMusicE2E:
    """MiniMax 音乐生成端到端测试"""

    @require_api_key
    @pytest.mark.asyncio
    async def test_music_generation(self):
        """真实调用 MiniMax 音乐生成 API"""
        from src.minimax.client import MiniMaxClient
        from src.minimax.exceptions import MiniMaxAPIError
        import httpx

        client = MiniMaxClient(
            api_key=MINIMAX_API_KEY,
            group_id=MINIMAX_GROUP_ID or None,
        )
        try:
            try:
                result = await client.text_to_music(
                    prompt="欢快的电子音乐",
                    lyrics="[Intro]\nla la la\n\n[Chorus]\n欢快的节拍",
                    output_format="url",
                )
            except httpx.ReadTimeout:
                pytest.skip("音乐生成 API 超时（可能不支持或服务不可用）")

            audio_url = (
                result.get("audio_url")
                or result.get("data", {}).get("audio_url", "")
            )
            if not audio_url:
                br = result.get("base_resp", {})
                msg = br.get("status_msg", "")
                if "not support" in msg or "invalid" in msg:
                    pytest.skip(f"API Key 不支持音乐生成: {msg}")
                pytest.fail(f"音乐生成失败: {result}")

            print(f"✅ Music URL: {audio_url[:60]}...")

            with tempfile.TemporaryDirectory() as tmpdir:
                async with httpx.AsyncClient(timeout=60.0) as http:
                    resp = await http.get(audio_url)
                    resp.raise_for_status()

                music_path = Path(tmpdir) / "music.mp3"
                with open(music_path, "wb") as f:
                    f.write(resp.content)

                size = music_path.stat().st_size
                print(f"✅ 音乐下载成功: {size} bytes")

        except MiniMaxAPIError as e:
            if "not support" in e.message or "invalid" in e.message:
                pytest.skip(f"API Key 不支持音乐生成: {e.message}")
            raise

        finally:
            await client.close()

class TestMiniMaxP2PE2E:
    """MiniMax 图生图端到端测试"""

    @require_api_key
    @pytest.mark.asyncio
    async def test_p2p_generation_url(self):
        """真实调用 MiniMax 图生图 API（使用 URL 格式的图片）"""
        from src.minimax.client import MiniMaxClient
        import httpx

        # 首先生成一张源图片
        client = MiniMaxClient(
            api_key=MINIMAX_API_KEY,
            group_id=MINIMAX_GROUP_ID or None,
        )
        try:
            source_result = await client.image_generation(
                prompt="a simple red apple on white background",
                response_format="url",
            )
            assert "image_urls" in source_result
            source_url = source_result["image_urls"][0]
            print(f"✅ 源图片 URL: {source_url[:80]}...")

            # 下载源图片
            async with httpx.AsyncClient(timeout=30.0) as http:
                resp = await http.get(source_url)
                resp.raise_for_status()
                source_data = resp.content

            print(f"✅ 源图片大小: {len(source_data)} bytes")

            # 使用源图片 URL 进行图生图
            result = await client.image_to_image(
                prompt="make the apple green",
                image_path=source_url,
                response_format="url",
            )

            print(f"\n图生图 API 响应: {result}")

            assert "image_urls" in result, f"返回格式错误，缺少 image_urls: {result}"
            assert len(result["image_urls"]) > 0, "未返回任何图片 URL"

            image_url = result["image_urls"][0]
            print(f"✅ 图生图 URL: {image_url[:80]}...")

        finally:
            await client.close()

    @require_api_key
    @pytest.mark.asyncio
    async def test_p2p_generation_base64(self):
        """真实调用 MiniMax 图生图 API（使用 Base64 格式）"""
        from src.minimax.client import MiniMaxClient

        client = MiniMaxClient(
            api_key=MINIMAX_API_KEY,
            group_id=MINIMAX_GROUP_ID or None,
        )
        try:
            # 生成源图片（Base64 格式）
            source_result = await client.image_generation(
                prompt="a yellow banana on blue background",
                response_format="base64",
            )
            assert "image_base64" in source_result
            source_b64 = source_result["image_base64"][0]
            print(f"✅ 源图片 Base64 大小: {len(source_b64)} chars")

            # 使用源图片 Base64 进行图生图
            result = await client.image_to_image(
                prompt="add some spots to the banana",
                image_path=f"data:image/png;base64,{source_b64}",
                response_format="url",
            )

            assert "image_urls" in result, f"返回格式错误: {result}"
            assert len(result["image_urls"]) > 0

            image_url = result["image_urls"][0]
            print(f"✅ 图生图 URL: {image_url[:80]}...")

        finally:
            await client.close()
