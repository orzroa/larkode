"""
MiniMax 视频生成能力

支持：#mm t2v (文生视频)、#mm p2v (图生视频)
"""
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Optional

# 优先使用新的日志工具
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from src.minimax.client import MiniMaxClient
    from src.minimax.feishu_delivery import MiniMaxFeishuDelivery
    from src.streaming_output import StreamingOutputManager


class VideoGenCapability:
    """MiniMax 视频生成能力"""

    def __init__(
        self,
        client: "MiniMaxClient",
        delivery: "MiniMaxFeishuDelivery",
        streaming_manager: Optional["StreamingOutputManager"] = None,
    ):
        self.client = client
        self.delivery = delivery
        self.streaming_manager = streaming_manager

    async def text_to_video(self, user_id: str, prompt: str, model: str = "MiniMax-Hailuo-2.3"):
        """
        文生视频：#mm t2v <提示词>
        """
        if not prompt.strip():
            await self.delivery.send_error(user_id, "请提供提示词，例如：#mm t2v 日出时分海面波光粼粼")
            return

        await self.delivery.send_progress(user_id, f"🎬 正在生成视频...\n\n提示词：{prompt}\n\n预计需要 1-2 分钟")

        try:
            task_id = await self.client.text_to_video(prompt=prompt, model=model)
            logger.info(f"文生视频任务已提交，task_id={task_id}")

            if not task_id:
                await self.delivery.send_error(user_id, "视频生成任务提交失败，请检查 API Key")
                return

            asyncio.create_task(self._poll_video_task(user_id, task_id, "文生视频"))

        except Exception as e:
            logger.error(f"文生视频提交失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"视频生成失败: {e}")

    async def image_to_video(self, user_id: str, prompt: str, image_path: str = None, model: str = "MiniMax-Hailuo-2.3-Fast"):
        """
        图生视频：#mm p2v <提示词>

        需要用户先上传一张图片，然后用此命令生成视频

        Args:
            user_id: 用户 ID
            prompt: 视频生成提示词（描述图片如何动起来）
            image_path: 图片路径（如果为 None，从缓存中获取用户最近上传的图片）
            model: 模型名称
        """
        if not prompt.strip():
            await self.delivery.send_error(user_id, "请提供提示词，例如：#mm p2v 画面中的场景开始动起来，人物开始行走")
            return

        # 如果没有提供图片路径，从缓存中获取用户最近上传的图片
        if not image_path:
            from src.minimax import get_user_image_path
            image_path = get_user_image_path(user_id)

        if not image_path:
            await self.delivery.send_error(
                user_id,
                "请先上传一张图片，然后使用 #mm p2v <提示词> 生成视频\n\n"
                "示例：\n"
                "1. 先发送一张图片\n"
                "2. 发送 #mm p2v 画面中的人物开始跳舞"
            )
            return

        # 检查图片文件是否存在
        from pathlib import Path
        if image_path.startswith("http://") or image_path.startswith("https://"):
            # URL 格式，直接使用
            pass
        elif not Path(image_path).exists():
            await self.delivery.send_error(user_id, f"图片文件不存在，请重新上传图片")
            return

        await self.delivery.send_progress(
            user_id,
            f"🎬 正在生成视频...\n\n"
            f"图片: {Path(image_path).name if not image_path.startswith('http') else 'URL'}\n"
            f"提示词：{prompt}\n\n"
            f"预计需要 1-2 分钟"
        )

        try:
            task_id = await self.client.image_to_video(
                prompt=prompt,
                image_path=image_path,
                model=model,
            )
            logger.info(f"图生视频任务已提交，task_id={task_id}, image_path={image_path}")

            if not task_id:
                await self.delivery.send_error(user_id, "视频生成任务提交失败")
                return

            asyncio.create_task(self._poll_video_task(user_id, task_id, "图生视频"))

        except Exception as e:
            logger.error(f"图生视频提交失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"视频生成失败: {e}")

    async def _poll_video_task(self, user_id: str, task_id: str, task_type: str = "视频生成"):
        """后台轮询视频任务进度"""
        from src.minimax.exceptions import MiniMaxTimeoutError

        poll_count = 0
        max_polls = 72  # 最多等待 6 分钟

        try:
            while poll_count < max_polls:
                await asyncio.sleep(5.0)
                poll_count += 1

                result = await self.client.get_video_task_result(task_id)
                status = result.get("status", "")

                if poll_count % 4 == 0:
                    elapsed = poll_count * 5
                    await self.delivery.send_progress(
                        user_id,
                        f"🎬 {task_type}中...\n\n状态：{status}\n\n已用时：约 {elapsed} 秒"
                    )

                if status == "Success":
                    file_id = result.get("file_id")
                    if file_id:
                        await self._handle_video_success(user_id, file_id)
                    else:
                        await self.delivery.send_error(user_id, "视频生成成功但未获取到文件ID")
                    return

                if status == "Fail":
                    msg = result.get("error_message", "视频生成失败")
                    await self.delivery.send_error(user_id, f"视频生成失败: {msg}")
                    return

            await self.delivery.send_error(user_id, "视频生成超时，请稍后重试")

        except MiniMaxTimeoutError:
            await self.delivery.send_error(user_id, "视频生成超时")
        except Exception as e:
            logger.error(f"轮询视频任务出错: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"视频生成出错: {e}")

    async def _handle_video_success(self, user_id: str, file_id: str):
        """处理视频生成成功"""
        try:
            # 获取下载 URL
            file_info = await self.client.retrieve_file(file_id)
            download_url = file_info.get("download_url")

            if not download_url:
                await self.delivery.send_error(user_id, "未获取到视频下载链接")
                return

            # 下载视频
            video_path = await self._download_video(user_id, download_url)
            if video_path:
                # 发送文件消息（飞书不支持 video 消息类型）
                await self.delivery.send_file(user_id, video_path)
            else:
                await self.delivery.send_error(user_id, "视频下载失败")

        except Exception as e:
            logger.error(f"处理视频成功结果失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"视频处理失败: {e}")

    async def _download_video(self, user_id: str, url: str) -> Optional[Path]:
        """下载视频文件"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            import time
            file_path = uploads_dir / f"mm_video_{int(time.time() * 1000)}.mp4"

            with open(file_path, "wb") as f:
                f.write(response.content)

            logger.info(f"视频下载成功: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"下载视频失败: {e}")
            return None