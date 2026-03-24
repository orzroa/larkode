"""
MiniMax 视频生成端到端测试

此测试完成完整流程：
1. 调用 MiniMax 视频生成 API
2. 轮询等待视频生成完成
3. 下载生成的视频文件
4. 上传到飞书
5. 发送视频消息给指定用户

模型策略：
- 首选：MiniMax-Hailuo-2.3-Fast（快速生成）
- 备选：MiniMax-Hailuo-2.3（限流时使用）
- 放弃：两次都限流则跳过

前置条件：
1. 环境变量 MINIMAX_API_KEY 已设置
2. .env 文件中 FEISHU_APP_ID 和 FEISHU_APP_SECRET 已配置
3. FEISHU_HOOK_NOTIFICATION_USER_ID 已设置（目标用户）

运行方式：
    # 默认跳过，需要显式指定 -m e2e 才运行
    uv run pytest tests/test_minimax_video_to_feishu.py -v -m e2e -s
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


class TestMiniMaxVideoToFeishuE2E:
    """MiniMax 视频生成并发送到飞书的端到端测试"""

    @require_api_keys
    async def test_video_to_feishu_full_flow(self):
        """
        完整流程测试：视频生成 -> 下载 -> 上传飞书 -> 发送

        测试案例：《水调歌头·明月几时有》
        """
        from src.minimax.client import MiniMaxClient
        from src.minimax.exceptions import MiniMaxRateLimitError, MiniMaxAPIError
        from src.feishu.file_ops import upload_video, send_file_message
        from src.feishu.api import FeishuAPI
        import httpx
        import asyncio

        config = _get_config()

        # 测试参数：《水调歌头·明月几时有》
        # Step 1: 先生成一张图片作为视频首帧（模拟用户上传图片）
        prompt_for_image = "中国古典诗词意境，明月高悬夜空，诗人举杯邀月，月光如水洒落人间，唯美优雅，水墨画风格"

        # Step 2: 视频生成提示词
        prompt_for_video = """明月几时有？把酒问青天。
画面动态变化：明月缓缓升起，云雾飘动，诗人举杯，月光洒落，意境唯美。"""

        # 模型策略：
        # - MiniMax-Hailuo-2.3-Fast：首选（图生视频）
        # - MiniMax-Hailuo-2.3：备选（文生视频/图生视频）
        models_to_try = [
            "MiniMax-Hailuo-2.3-Fast",   # 首选：图生视频
            "MiniMax-Hailuo-2.3",         # 备选
        ]

        print(f"\n{'='*60}")
        print(f"🎬 视频生成测试（图生视频 p2v）")
        print(f"目标用户: {config['feishu_user_id']}")
        print(f"流程: 用户上传图片 → p2v 命令 → 生成视频")
        print(f"{'='*60}\n")

        client = MiniMaxClient(
            api_key=config["minimax_api_key"],
            group_id=config["minimax_group_id"] or None,
        )

        # Step 1: 模拟用户上传图片（生成图片并缓存）
        print("Step 1: 模拟用户上传图片...")
        image_url = None
        image_path = None
        try:
            result = await client.image_generation(
                prompt=prompt_for_image,
                response_format="url",
            )
            image_urls = result.get("image_urls", [])
            if image_urls:
                image_url = image_urls[0]
                print(f"  ✅ 图片生成成功!")
                print(f"     URL: {image_url[:60]}...")

                # 下载图片到本地
                uploads_dir = Path(__file__).parent.parent / "uploads"
                uploads_dir.mkdir(parents=True, exist_ok=True)
                timestamp = int(time.time() * 1000)
                image_path = uploads_dir / f"video_frame_{timestamp}.jpg"

                async with httpx.AsyncClient(timeout=60.0) as http:
                    resp = await http.get(image_url)
                    resp.raise_for_status()
                    with open(image_path, "wb") as f:
                        f.write(resp.content)

                print(f"  ✅ 图片下载成功: {image_path.name}")

                # 缓存用户图片（模拟用户上传图片的流程）
                from src.minimax import set_user_image
                set_user_image(config['feishu_user_id'], str(image_path), image_url)
                print(f"  ✅ 已缓存用户图片，可使用 p2v 命令")
            else:
                pytest.fail("图片生成失败：未获取到图片 URL")
        except Exception as e:
            pytest.fail(f"图片生成失败: {e}")

        # Step 2: 调用图生视频 API（使用缓存的图片）
        print("\nStep 2: 调用图生视频 API...")

        # 从缓存获取用户图片
        from src.minimax import get_user_image_path, get_user_image_url
        cached_image_path = get_user_image_path(config['feishu_user_id'])
        cached_image_url = get_user_image_url(config['feishu_user_id'])
        print(f"  从缓存获取图片: {cached_image_path}")

        if not cached_image_path:
            pytest.fail("用户未上传图片，请先上传图片")

        task_id = None
        used_model = None

        for model in models_to_try:
            try:
                print(f"\n  尝试模型: {model}")
                # 优先使用 URL，否则使用本地文件路径（会转为 Base64）
                image_to_use = cached_image_url if cached_image_url else cached_image_path
                task_id = await client.image_to_video(
                    prompt=prompt_for_video,
                    image_path=image_to_use,
                    model=model,
                )
                used_model = model
                print(f"  ✅ 任务提交成功! task_id: {task_id}")
                break

            except MiniMaxRateLimitError:
                print(f"  ⚠️ 模型 {model} 限流，尝试下一个...")
                continue

            except MiniMaxAPIError as e:
                error_msg = str(e)
                error_code = e.details.get("response", {}).get("base_resp", {}).get("status_code", 0)

                # 限流错误：尝试下一个模型
                if "rate" in error_msg.lower() or "limit" in error_msg.lower() or "usage limit" in error_msg.lower() or error_code in (429, 2056):
                    print(f"  ⚠️ 模型 {model} 限流，尝试下一个...")
                    continue
                # 套餐不支持：尝试下一个模型
                elif "not support" in error_msg.lower() or "token plan" in error_msg.lower() or error_code == 2061:
                    print(f"  ⚠️ 当前套餐不支持模型 {model}，尝试下一个...")
                    continue
                else:
                    raise

        if not task_id:
            pytest.skip("所有模型都不可用（限流/套餐不支持）")

        await client.close()

        # Step 2: 轮询等待视频生成完成
        print(f"\nStep 2: 轮询等待视频生成完成...")
        print(f"  使用模型: {used_model}")
        print(f"  task_id: {task_id}")

        file_id = None
        client = MiniMaxClient(api_key=config["minimax_api_key"])

        try:
            poll_count = 0
            max_polls = 72  # 最多等待 6 分钟（每 5 秒轮询一次）

            while poll_count < max_polls:
                await asyncio.sleep(5.0)
                poll_count += 1

                result = await client.get_video_task_result(task_id)
                status = result.get("status", "")

                elapsed = poll_count * 5
                print(f"  [{elapsed}s] 状态: {status}")

                if status == "Success":
                    file_id = result.get("file_id")
                    if file_id:
                        print(f"  ✅ 视频生成成功! file_id: {file_id}")
                        break
                    else:
                        pytest.fail(f"视频生成成功但未获取到 file_id: {result}")

                if status == "Fail":
                    msg = result.get("error_message", "视频生成失败")
                    pytest.fail(f"视频生成失败: {msg}")

            if not file_id:
                pytest.fail(f"视频生成超时（等待 {max_polls * 5} 秒）")

        finally:
            await client.close()

        # Step 3: 获取视频下载 URL
        print("\nStep 3: 获取视频下载 URL...")
        client = MiniMaxClient(api_key=config["minimax_api_key"])
        try:
            file_info = await client.retrieve_file(file_id)
            video_url = file_info.get("download_url")
            if not video_url:
                pytest.fail(f"未获取到视频下载 URL: {file_info}")
            print(f"  ✅ 下载 URL: {video_url[:60]}...")
        finally:
            await client.close()

        # Step 3: 下载视频文件
        print("\nStep 3: 下载视频文件...")
        video_path = None
        try:
            async with httpx.AsyncClient(timeout=180.0) as http:
                resp = await http.get(video_url)
                resp.raise_for_status()

            # 保存到 uploads 目录
            uploads_dir = Path(__file__).parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            timestamp = int(time.time() * 1000)
            video_path = uploads_dir / f"shuidiaogetou_video_{timestamp}.mp4"

            with open(video_path, "wb") as f:
                f.write(resp.content)

            size = video_path.stat().st_size
            print(f"✅ 视频下载成功: {video_path.name}, 大小: {size/1024/1024:.2f} MB")

            # 验证文件格式（MP4 文件头）
            with open(video_path, "rb") as f:
                header = f.read(12)

            # MP4 文件通常以 ftyp 开头（在第 4-8 字节）
            is_mp4 = (
                header[4:8] == b'ftyp' or  # MP4/MOV
                header[4:8] == b'moov' or
                header[:3] == b'ID3' or     # ID3 标签（不太可能）
                len(header) > 8
            )
            if not is_mp4:
                print(f"⚠️ 警告: 文件可能不是 MP4 格式，文件头: {header[:8].hex()}")

        except Exception as e:
            pytest.fail(f"下载视频文件失败: {e}")

        # Step 4: 上传到飞书
        print("\nStep 4: 上传视频到飞书...")
        file_key = None
        try:
            file_key = await upload_video(config["feishu_app_secret"], video_path)
            if not file_key:
                pytest.fail("飞书视频上传失败，未获取到 file_key")

            print(f"✅ 飞书上传成功, file_key: {file_key}")

        except Exception as e:
            pytest.fail(f"飞书视频上传失败: {e}")

        # Step 5: 发送视频消息
        print("\nStep 5: 发送视频消息到飞书...")
        try:
            # 使用 FeishuAPI 发送视频消息
            feishu = FeishuAPI(
                app_id=config["feishu_app_id"],
                app_secret=config["feishu_app_secret"]
            )

            # 先发文本通知
            await feishu.send_message(
                config["feishu_user_id"],
                f"🎬 视频生成完成！\n模型: {used_model}"
            )

            # 飞书不支持 video 消息类型，直接发送文件消息
            success = await send_file_message(
                config["feishu_app_secret"],
                config["feishu_user_id"],
                file_key,
            )

            if success:
                print(f"✅ 文件消息发送成功！")
                print(f"\n{'='*60}")
                print(f"🎉 完整流程测试成功！")
                print(f"模型: {used_model}")
                print(f"请检查飞书是否收到视频: {video_path.name}")
                print(f"{'='*60}\n")
            else:
                pytest.fail("文件消息发送失败")

        except Exception as e:
            pytest.fail(f"发送视频消息失败: {e}")

        # 最终验证
        assert video_path is not None, "视频文件未生成"
        assert video_path.exists(), f"视频文件不存在: {video_path}"
        assert video_path.stat().st_size > 10000, "视频文件太小"
        assert file_key is not None, "飞书 file_key 未获取"

    @require_api_keys
    async def test_video_generation_quick(self):
        """
        快速测试：只验证视频生成 API 是否正常工作

        不发送到飞书，用于快速验证 API 连通性
        """
        from src.minimax.client import MiniMaxClient
        from src.minimax.exceptions import MiniMaxRateLimitError, MiniMaxAPIError

        config = _get_config()

        prompt = "一轮明月高悬夜空，月光如水洒落人间"

        client = MiniMaxClient(
            api_key=config["minimax_api_key"],
            group_id=config["minimax_group_id"] or None,
        )

        task_id = None
        used_model = None

        try:
            # 尝试两个模型（注意：Fast 模型不支持文生视频）
            models = ["MiniMax-Hailuo-2.3", "MiniMax-Hailuo-02"]

            for model in models:
                try:
                    print(f"\n尝试模型: {model}")
                    task_id = await client.text_to_video(prompt=prompt, model=model)
                    used_model = model
                    print(f"✅ 任务提交成功! task_id: {task_id}")
                    break
                except (MiniMaxRateLimitError, MiniMaxAPIError) as e:
                    error_msg = str(e)
                    # 检查是否是限流错误
                    if "rate" in error_msg.lower() or "limit" in error_msg.lower() or "429" in error_msg:
                        print(f"⚠️ 模型 {model} 限流: {e}")
                        continue
                    else:
                        # 其他错误直接抛出
                        raise

            if not task_id:
                pytest.skip("所有模型都限流")

            print(f"\n使用模型: {used_model}")
            print(f"task_id: {task_id}")

        finally:
            await client.close()