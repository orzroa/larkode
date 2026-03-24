"""
MiniMax 文字转语音能力

支持：#mm tts <文字>
"""
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

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


class VoiceTTSCapability:
    """MiniMax 文字转语音能力"""

    def __init__(
        self,
        client: "MiniMaxClient",
        delivery: "MiniMaxFeishuDelivery",
    ):
        self.client = client
        self.delivery = delivery

    async def text_to_speech(self, user_id: str, text: str):
        """
        文字转语音：#mm tts <文字>

        Args:
            user_id: 用户 ID
            text: 要转换的文字
        """
        if not text.strip():
            await self.delivery.send_error(
                user_id,
                "请提供要转换的文字，例如：#mm tts 今天天气真好",
            )
            return

        # 检查字数限制
        if len(text) > 1000:
            await self.delivery.send_error(user_id, "文字长度不能超过 1000 字，请分段转换")
            return

        await self.delivery.send_progress(user_id, f"🔊 正在生成语音...\n\n文字：{text[:100]}...")

        try:
            audio_bytes = await self.client.text_to_speech(text=text)
            if not audio_bytes:
                await self.delivery.send_error(user_id, "语音生成失败，未获取到音频数据")
                return
            logger.info(f"TTS 生成成功，音频大小: {len(audio_bytes)} bytes")

            # 保存到临时文件
            audio_path = await self._save_audio(user_id, audio_bytes)
            if audio_path:
                await self.delivery.send_audio(user_id, audio_path)
            else:
                await self.delivery.send_error(user_id, "音频保存失败")

        except Exception as e:
            logger.error(f"文字转语音失败: {e}", exc_info=True)
            await self.delivery.send_error(user_id, f"语音生成失败: {e}")

    async def _save_audio(self, user_id: str, audio_bytes: bytes) -> Optional[Path]:
        """保存音频数据到文件"""
        try:
            uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            import time
            file_path = uploads_dir / f"mm_tts_{int(time.time() * 1000)}.mp3"

            with open(file_path, "wb") as f:
                f.write(audio_bytes)

            return file_path

        except Exception as e:
            logger.error(f"保存音频失败: {e}")
            return None
