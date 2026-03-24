"""
MiniMax 视频生成能力

支持：#mm t2v (文生视频)
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

    async def text_to_video(self, user_id: str, prompt: str):
        """
        文生视频：#mm t2v <提示词>
        """
        if not prompt.strip():
            await self.delivery.send_error(user_id, "请提供提示词，例如：#mm t2v 日出时分海面波光粼粼")
            return

        await self.delivery.send_progress(user_id, f"🎬 正在生成视频...\n\n提示词：{prompt}\n\n预计需要 1-2 分钟")

        try:
            task_id = await self.client.text_to_video(prompt=prompt)
            logger.info(f"文生视频任务已提交，task_id={task_id}")

            if not task_id:
                await self.delivery.send_error(user_id, "视频生成任务提交失败，请检查 API Key")
                return

            asyncio.create_task(self._poll_video_task(user_id, task_id))

        except Exception as e:
            logger.error(f"文生视频提交失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"视频生成失败: {e}")

    async def _poll_video_task(self, user_id: str, task_id: str):
        """后台轮询视频任务进度"""
        from src.minimax.exceptions import MiniMaxTimeoutError

        last_status = None
        poll_count = 0

        try:
            while True:
                await asyncio.sleep(5.0)
                poll_count += 1

                result = await self.client.get_video_task_result(task_id)
                status = result.get("status", result.get("base_resp", {}).get("status_msg", ""))

                if poll_count % 2 == 0 and status != last_status:
                    last_status = status
                    progress_msg = self._format_progress_message(status, poll_count)
                    await self.delivery.send_progress(user_id, progress_msg)

                if status in ("SUCCESS", "success", "Completed", "Success"):
                    video_url = result.get("video_url") or result.get("data", {}).get("video_url", "")
                    if video_url:
                        video_path = await self._download_video(user_id, video_url)
                        if video_path:
                            await self.delivery.send_video(user_id, video_path)
                        else:
                            await self.delivery.send_error(user_id, "视频下载失败")
                    else:
                        await self.delivery.send_error(user_id, "未获取到视频链接")
                    return

                if status in ("FAIL", "fail", "Failed", "Error"):
                    msg = result.get("message", result.get("msg", "视频生成失败"))
                    await self.delivery.send_error(user_id, f"视频生成失败: {msg}")
                    return

                if poll_count > 60:
                    await self.delivery.send_error(user_id, "视频生成超时，请稍后重试")
                    return

        except MiniMaxTimeoutError:
            await self.delivery.send_error(user_id, "视频生成超时")
        except Exception as e:
            logger.error(f"轮询视频任务出错: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"视频生成出错: {e}")

    def _format_progress_message(self, status: str, poll_count: int) -> str:
        """格式化进度消息"""
        elapsed = poll_count * 5
        status_text = {
            "PROCESSING": "正在渲染中",
            "processing": "正在渲染中",
            "QUEUED": "排队中",
            "queued": "排队中",
            "RUNNING": "正在生成",
            "running": "正在生成",
            "PENDING": "等待中",
            "pending": "等待中",
        }.get(status, status)

        dots = "." * (poll_count % 4 + 1)
        return f"🎬 视频生成中 {dots}\n\n状态：{status_text}\n\n已用时：约 {elapsed} 秒"

    async def _download_video(self, user_id: str, url: str) -> Optional[Path]:
        """下载视频文件"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
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