"""
MiniMax 结果发回飞书

负责将 MiniMax 生成的图片/视频/音频/音乐/文字发回飞书
"""
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

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
    from src.card_dispatcher import CardDispatcher
    from src.feishu.api import FeishuAPI


class MiniMaxFeishuDelivery:
    """
    MiniMax 结果发回飞书

    支持：
    - 文字 → 卡片消息
    - 图片 → 图片消息
    - 视频 → 视频消息
    - 音频 → 音频消息
    - 音乐 → 文件消息
    """

    def __init__(
        self,
        feishu_api: "FeishuAPI",
        card_dispatcher: Optional["CardDispatcher"] = None,
    ):
        self.feishu_api = feishu_api
        self.card_dispatcher = card_dispatcher

    async def send_text(self, user_id: str, text: str):
        """发送文字（使用卡片）"""
        if self.card_dispatcher:
            from src.card_builder import UnifiedCardBuilder

            content = UnifiedCardBuilder.build_text_card(text)
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="minimax",
                title="MiniMax",
                content=content,
                message_type="response",
                template_color="blue",
            )
        else:
            # Fallback: 直接发文本消息
            card = {
                "msg_type": "text",
                "content": {"text": text},
            }
            await self.feishu_api.send_message(user_id, json.dumps(card))

    async def send_image(self, user_id: str, image_path: Path):
        """发送图片消息"""
        try:
            # 上传图片到飞书
            image_key = await self.feishu_api.upload_image(image_path)
            if not image_key:
                logger.error("MiniMax 图片上传飞书失败")
                await self.send_text(user_id, "❌ 图片上传失败")
                return

            # 发送图片消息
            success = await self.feishu_api.send_image_message(user_id, image_key)
            if success:
                logger.info(f"MiniMax 图片发送成功: {image_path.name}")
            else:
                logger.error(f"MiniMax 图片发送失败: {image_path.name}")
                await self.send_text(user_id, "❌ 图片发送失败")

        except Exception as e:
            logger.error(f"发送 MiniMax 图片时出错: {e}", exc_info=True)
            await self.send_text(user_id, f"❌ 发送图片失败: {e}")

    async def send_video(
        self,
        user_id: str,
        video_path: Path,
        thumbnail_path: Optional[Path] = None,
    ):
        """发送视频消息"""
        try:
            # 上传视频到飞书
            video_key = await self.feishu_api.upload_video(video_path)
            if not video_key:
                logger.error("MiniMax 视频上传飞书失败")
                await self.send_text(user_id, "❌ 视频上传失败")
                return

            # 上传视频封面（可选）
            thumbnail_key = None
            if thumbnail_path and thumbnail_path.exists():
                thumbnail_key = await self.feishu_api.upload_image(thumbnail_path)

            # 发送视频消息
            success = await self.feishu_api.send_video_message(user_id, video_key, thumbnail_key)
            if success:
                logger.info(f"MiniMax 视频发送成功: {video_path.name}")
            else:
                logger.error(f"MiniMax 视频发送失败: {video_path.name}")
                await self.send_text(user_id, "❌ 视频发送失败")

        except Exception as e:
            logger.error(f"发送 MiniMax 视频时出错: {e}", exc_info=True)
            await self.send_text(user_id, f"❌ 发送视频失败: {e}")

    async def send_audio(self, user_id: str, audio_path: Path):
        """发送音频消息"""
        try:
            # 上传音频到飞书
            audio_key = await self.feishu_api.upload_audio(audio_path)
            if not audio_key:
                logger.error("MiniMax 音频上传飞书失败")
                await self.send_text(user_id, "❌ 音频上传失败")
                return

            # 发送音频消息
            success = await self.feishu_api.send_audio_message(user_id, audio_key)
            if success:
                logger.info(f"MiniMax 音频发送成功: {audio_path.name}")
            else:
                logger.error(f"MiniMax 音频发送失败: {audio_path.name}")
                await self.send_text(user_id, "❌ 音频发送失败")

        except Exception as e:
            logger.error(f"发送 MiniMax 音频时出错: {e}", exc_info=True)
            await self.send_text(user_id, f"❌ 发送音频失败: {e}")

    async def send_file(self, user_id: str, file_path: Path):
        """发送文件消息（用于音乐等）"""
        try:
            # 上传文件到飞书
            file_key = await self.feishu_api.upload_file(file_path)
            if not file_key:
                logger.error("MiniMax 文件上传飞书失败")
                await self.send_text(user_id, "❌ 文件上传失败")
                return

            # 发送文件消息
            success = await self.feishu_api.send_file_message(user_id, file_key)
            if success:
                logger.info(f"MiniMax 文件发送成功: {file_path.name}")
            else:
                logger.error(f"MiniMax 文件发送失败: {file_path.name}")
                await self.send_text(user_id, "❌ 文件发送失败")

        except Exception as e:
            logger.error(f"发送 MiniMax 文件时出错: {e}", exc_info=True)
            await self.send_text(user_id, f"❌ 发送文件失败: {e}")

    async def send_error(self, user_id: str, error_message: str):
        """发送错误消息"""
        if self.card_dispatcher:
            from src.card_builder import UnifiedCardBuilder

            content = UnifiedCardBuilder.build_error_card(error_message)
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="error",
                title="MiniMax 错误",
                content=content,
                message_type="error",
                template_color="red",
            )
        else:
            await self.send_text(user_id, f"❌ {error_message}")

    async def send_progress(self, user_id: str, message: str):
        """发送进度消息"""
        if self.card_dispatcher:
            from src.card_builder import UnifiedCardBuilder

            content = UnifiedCardBuilder.build_text_card(message)
            await self.card_dispatcher.send_card(
                user_id=user_id,
                card_type="minimax_progress",
                title="MiniMax 处理中",
                content=content,
                message_type="response",
                template_color="grey",
            )
        else:
            await self.send_text(user_id, f"⏳ {message}")
