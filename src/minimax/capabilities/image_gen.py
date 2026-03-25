"""
MiniMax 图片生成能力

支持：#mm img
"""
import base64
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


class ImageGenCapability:
    """MiniMax 图片生成能力"""

    def __init__(
        self,
        client: "MiniMaxClient",
        delivery: "MiniMaxFeishuDelivery",
    ):
        self.client = client
        self.delivery = delivery

    async def text_to_image(self, user_id: str, prompt: str):
        """
        文生图：#mm img <提示词>
        """
        if not prompt.strip():
            await self.delivery.send_error(user_id, "请提供提示词，例如：#mm img 画一只可爱的猫")
            return

        await self.delivery.send_progress(user_id, f"🎨 正在生成图片...\n\n提示词：{prompt}")

        try:
            result = await self.client.image_generation(prompt=prompt, response_format="url")
            logger.info(f"图片生成结果: {result}")

            image_urls = result.get("image_urls", [])
            base64_images = result.get("image_base64", [])

            if image_urls:
                image_path = await self._download_image(user_id, image_urls[0])
                if image_path:
                    await self.delivery.send_image(user_id, image_path)
                else:
                    await self.delivery.send_error(user_id, "图片下载失败")
            elif base64_images:
                image_path = await self._save_base64_image(user_id, base64_images[0])
                if image_path:
                    await self.delivery.send_image(user_id, image_path)
                else:
                    await self.delivery.send_error(user_id, "图片保存失败")
            else:
                await self.delivery.send_error(
                    user_id,
                    f"未获取到图片数据，请检查 API Key 是否正确\n\n原始响应: {result}",
                )

        except Exception as e:
            logger.error(f"图片生成失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"图片生成失败: {e}")

    async def image_to_image(self, user_id: str, prompt: str, image_path: str = None):
        """
        图生图：#mm p2p <提示词>

        需要用户先上传一张图片，然后用此命令生成新图片

        Args:
            user_id: 用户 ID
            prompt: 图片生成提示词
            image_path: 图片路径（如果为 None，从缓存中获取用户最近上传的图片）
        """
        if not prompt.strip():
            await self.delivery.send_error(user_id, "请提供提示词，例如：#mm p2p 把这只猫变成一只狗")
            return

        # 如果没有提供图片路径，从缓存中获取用户最近上传的图片
        if not image_path:
            from src.minimax import get_user_image_path
            image_path = get_user_image_path(user_id)

        if not image_path:
            await self.delivery.send_error(
                user_id,
                "请先上传一张图片，然后使用 #mm p2p <提示词> 生成新图片\n\n"
                "示例：\n"
                "1. 先发送一张图片\n"
                "2. 发送 #mm p2p 把这张图片变成油画风格"
            )
            return

        # 检查图片文件是否存在
        if image_path.startswith("http://") or image_path.startswith("https://"):
            # URL 格式，直接使用
            image_name = "URL"
        elif not Path(image_path).exists():
            await self.delivery.send_error(user_id, f"图片文件不存在，请重新上传图片")
            return
        else:
            image_name = Path(image_path).name

        await self.delivery.send_progress(
            user_id,
            f"🎨 正在根据图片生成新图片...\n\n"
            f"原图: {image_name}\n"
            f"提示词：{prompt}"
        )

        try:
            result = await self.client.image_to_image(prompt=prompt, image_path=image_path, response_format="url")
            logger.info(f"图生图结果: {result}")

            image_urls = result.get("image_urls", [])
            base64_images = result.get("image_base64", [])

            if image_urls:
                image_path = await self._download_image(user_id, image_urls[0])
                if image_path:
                    await self.delivery.send_image(user_id, image_path)
                else:
                    await self.delivery.send_error(user_id, "图片下载失败")
            elif base64_images:
                image_path = await self._save_base64_image(user_id, base64_images[0])
                if image_path:
                    await self.delivery.send_image(user_id, image_path)
                else:
                    await self.delivery.send_error(user_id, "图片保存失败")
            else:
                await self.delivery.send_error(
                    user_id,
                    f"未获取到图片数据\n\n原始响应: {result}",
                )

        except Exception as e:
            logger.error(f"图生图失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"图生图失败: {e}")

    # ==================== 辅助方法 ====================

    async def _download_image(self, user_id: str, url: str) -> Optional[Path]:
        """从 URL 下载图片"""
        import httpx

        try:
            # 处理 file:// 协议
            if url.startswith("file://"):
                local_path = Path(url[7:])
                if local_path.exists():
                    return local_path
                return None

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            import time
            file_path = uploads_dir / f"mm_img_{int(time.time() * 1000)}.png"

            with open(file_path, "wb") as f:
                f.write(response.content)

            return file_path

        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            return None

    async def _save_base64_image(self, user_id: str, base64_data: str) -> Optional[Path]:
        """保存 base64 图片数据"""
        try:
            image_bytes = base64.b64decode(base64_data)

            uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            import time
            file_path = uploads_dir / f"mm_img_{int(time.time() * 1000)}.png"

            with open(file_path, "wb") as f:
                f.write(image_bytes)

            return file_path

        except Exception as e:
            logger.error(f"保存 base64 图片失败: {e}")
            return None