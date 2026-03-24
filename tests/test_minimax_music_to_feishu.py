"""
MiniMax 音乐生成端到端测试

此测试完成完整流程：
1. 调用 MiniMax 音乐生成 API
2. 下载生成的音乐文件
3. 上传到飞书
4. 发送给指定用户

前置条件：
1. 环境变量 MINIMAX_API_KEY 已设置
2. .env 文件中 FEISHU_APP_ID 和 FEISHU_APP_SECRET 已配置
3. FEISHU_HOOK_NOTIFICATION_USER_ID 已设置（目标用户）

运行方式：
    # 默认跳过，需要显式指定 -m e2e 才运行
    uv run pytest tests/test_minimax_music_to_feishu.py -v -m e2e
"""
import os
import time
import pytest
import tempfile
from pathlib import Path

from src.config.settings import get_settings


# 标记为 e2e 测试，默认跳过
pytestmark = pytest.mark.e2e


def _get_config():
    """获取配置（延迟加载）"""
    settings = get_settings()
    return {
        "minimax_api_key": os.environ.get("MINIMAX_API_KEY", "") or settings.minimax_api_key,
        "minimax_group_id": os.environ.get("MINIMAX_GROUP_ID", "") or settings.minimax_group_id,
        "feishu_app_id": settings.feishu_app_id,
        "feishu_app_secret": settings.feishu_app_secret,
        "feishu_user_id": settings.feishu_hook_notification_user_id,
    }


def require_api_keys(f):
    """装饰器：需要有效的 API Keys"""
    @pytest.mark.asyncio
    async def wrapper(*args, **kwargs):
        config = _get_config()
        missing = []
        if not config["minimax_api_key"]:
            missing.append("MINIMAX_API_KEY")
        if not config["feishu_app_id"]:
            missing.append("FEISHU_APP_ID")
        if not config["feishu_app_secret"]:
            missing.append("FEISHU_APP_SECRET")
        if not config["feishu_user_id"]:
            missing.append("FEISHU_HOOK_NOTIFICATION_USER_ID")

        if missing:
            pytest.skip(f"缺少配置: {', '.join(missing)}")
            return
        return await f(*args, **kwargs)
    return wrapper


class TestMiniMaxMusicToFeishuE2E:
    """MiniMax 音乐生成并发送到飞书的端到端测试"""

    @require_api_keys
    async def test_music_to_feishu_full_flow(self):
        """
        完整流程测试：音乐生成 -> 下载 -> 上传飞书 -> 发送

        测试案例：《水调歌头·明月几时有》
        风格：中国古典婉约怀念带一点点忧伤最后有有点放达
        """
        from src.minimax.client import MiniMaxClient
        from src.feishu.file_ops import upload_file, send_file_message
        import httpx

        config = _get_config()

        # 测试参数
        style = "中国古典婉约怀念带一点点忧伤最后有有点放达，音乐优雅动听"
        lyrics = """明月几时有？把酒问青天。
不知天上宫阙，今夕是何年。
我欲乘风归去，又恐琼楼玉宇，高处不胜寒。
起舞弄清影，何似在人间。
转朱阁，低绮户，照无眠。
不应有恨，何事长向别时圆？
人有悲欢离合，月有阴晴圆缺，此事古难全。
但愿人长久，千里共婵娟。"""

        print(f"\n{'='*60}")
        print(f"🎵 音乐生成测试")
        print(f"风格: {style}")
        print(f"歌词: {lyrics[:30]}...")
        print(f"目标用户: {config['feishu_user_id']}")
        print(f"{'='*60}\n")

        # Step 1: 调用 MiniMax 音乐生成 API
        print("Step 1: 调用 MiniMax 音乐生成 API...")
        client = MiniMaxClient(
            api_key=config["minimax_api_key"],
            group_id=config["minimax_group_id"] or None,
        )

        audio_url = None
        try:
            # 使用 music-2.5 模型（Max 套餐支持）
            result = await client.text_to_music(
                prompt=style,
                lyrics=lyrics,
                model="music-2.5",
                output_format="url",
            )

            print(f"API 原始响应 keys: {result.keys()}")

            # 提取音频 URL - 在 data.audio 字段中
            data = result.get("data", {})
            audio_url = data.get("audio", "")
            extra_info = result.get("extra_info", {})

            if not audio_url:
                base_resp = result.get("base_resp", {})
                error_msg = base_resp.get("status_msg", "未知错误")
                pytest.fail(f"音乐生成失败: {error_msg}\n原始响应: {result}")

            duration_sec = extra_info.get("music_duration", 0) / 1000
            print(f"✅ 音乐生成成功! 时长: {duration_sec:.1f} 秒")
            print(f"   URL: {audio_url[:60]}...")

        except Exception as e:
            pytest.fail(f"MiniMax API 调用失败: {e}")
        finally:
            await client.close()

        # Step 2: 下载音乐文件
        print("\nStep 2: 下载音乐文件...")
        music_path = None
        try:
            async with httpx.AsyncClient(timeout=120.0) as http:
                resp = await http.get(audio_url)
                resp.raise_for_status()

            # 保存到 uploads 目录
            uploads_dir = Path(__file__).parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            music_path = uploads_dir / f"shuidiaogetou_{timestamp}.mp3"

            with open(music_path, "wb") as f:
                f.write(resp.content)

            size = music_path.stat().st_size
            print(f"✅ 音乐下载成功: {music_path.name}, 大小: {size/1024:.1f} KB")

            # 验证文件格式（MP3 文件头）
            with open(music_path, "rb") as f:
                header = f.read(10)

            is_mp3 = (
                header[:3] == b'ID3' or  # ID3 标签
                header[:2] == b'\xff\xfb' or  # MPEG Audio Layer 3
                header[:2] == b'\xff\xf3'
            )
            if not is_mp3:
                print(f"⚠️ 警告: 文件可能不是 MP3 格式，文件头: {header[:4].hex()}")

        except Exception as e:
            pytest.fail(f"下载音乐文件失败: {e}")

        # Step 3: 上传到飞书
        print("\nStep 3: 上传音乐到飞书...")
        file_key = None
        try:
            file_key = await upload_file(config["feishu_app_secret"], music_path)
            if not file_key:
                pytest.fail("飞书文件上传失败，未获取到 file_key")

            print(f"✅ 飞书上传成功, file_key: {file_key}")

        except Exception as e:
            pytest.fail(f"飞书文件上传失败: {e}")

        # Step 4: 发送文件消息
        print("\nStep 4: 发送文件消息到飞书...")
        try:
            success = await send_file_message(
                config["feishu_app_secret"],
                config["feishu_user_id"],
                file_key,
            )

            if success:
                print(f"✅ 文件消息发送成功！")
                print(f"\n{'='*60}")
                print(f"🎉 完整流程测试成功！")
                print(f"请检查飞书是否收到文件: {music_path.name}")
                print(f"{'='*60}\n")
            else:
                pytest.fail("文件消息发送失败")

        except Exception as e:
            pytest.fail(f"发送文件消息失败: {e}")

        # 最终验证
        assert music_path is not None, "音乐文件未生成"
        assert music_path.exists(), f"音乐文件不存在: {music_path}"
        assert music_path.stat().st_size > 1000, "音乐文件太小"
        assert file_key is not None, "飞书 file_key 未获取"

    @require_api_keys
    async def test_music_simple(self):
        """
        简化测试：只验证音乐生成和下载

        不发送到飞书，用于快速验证 API 是否正常工作
        """
        from src.minimax.client import MiniMaxClient
        import httpx

        config = _get_config()

        style = "中国古典风格，优雅动听，思念怀念的情绪"
        lyrics = "明月几时有，把酒问青天。"

        client = MiniMaxClient(
            api_key=config["minimax_api_key"],
            group_id=config["minimax_group_id"] or None,
        )

        try:
            # Max 套餐支持 music-2.5 模型
            result = await client.text_to_music(
                prompt=style,
                lyrics=lyrics,
                model="music-2.5",
                output_format="url",
            )

            print(f"\nAPI 响应: {result}")

            # 提取音频 URL - 在 data.audio 字段中
            data = result.get("data", {})
            audio_url = data.get("audio", "")
            extra_info = result.get("extra_info", {})

            if not audio_url:
                base_resp = result.get("base_resp", {})
                pytest.fail(f"未获取到音频 URL: base_resp={base_resp}, result={result}")

            duration_sec = extra_info.get("music_duration", 0) / 1000
            size_kb = extra_info.get("music_size", 0) / 1024

            print(f"✅ 音乐生成成功!")
            print(f"   时长: {duration_sec:.1f} 秒")
            print(f"   大小: {size_kb:.1f} KB")
            print(f"   URL: {audio_url[:60]}...")

            # 下载验证
            async with httpx.AsyncClient(timeout=60.0) as http:
                resp = await http.head(audio_url)
                print(f"   音频 URL 状态: {resp.status_code}")
                assert resp.status_code == 200, f"音频 URL 不可访问: {resp.status_code}"

        finally:
            await client.close()