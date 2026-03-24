"""
MiniMax 命令解析与分发

解析 #mm <cmd> <args> 并分发到对应的 capability handler
"""
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


HELP_TEXT = """
**MiniMax 多媒体能力**

🎨 **图片生成**
• `#mm img <提示词>` — 文生图

🎬 **视频生成**
• `#mm t2v <提示词>` — 文生视频

🔊 **语音合成**
• `#mm tts <文字>` — 文字转语音

🎵 **音乐生成**
• `#mm music <风格> <歌词>` — 文生音乐（必须提供歌词）
• 示例：`#mm music 古典 明月几时有，把酒问青天`

📖 `#mm help` — 显示此帮助
"""


class MiniMaxCommands:
    """MiniMax 命令处理器"""

    def __init__(
        self,
        client: "MiniMaxClient",
        delivery: "MiniMaxFeishuDelivery",
        streaming_manager: Optional["StreamingOutputManager"] = None,
    ):
        from src.minimax.capabilities import (
            ImageGenCapability,
            VideoGenCapability,
            VoiceTTSCapability,
            MusicGenCapability,
        )

        self.delivery = delivery
        self.image_cap = ImageGenCapability(client, delivery)
        self.video_cap = VideoGenCapability(client, delivery, streaming_manager)
        self.voice_cap = VoiceTTSCapability(client, delivery)
        self.music_cap = MusicGenCapability(client, delivery)

    async def handle_command(self, user_id: str, command: str):
        """
        处理 MiniMax 命令

        Args:
            user_id: 用户 ID
            command: 完整命令（不包含 #mm 前缀）
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        args = parts[1] if len(parts) > 1 else ""

        logger.info(f"MiniMax 命令: user={user_id}, cmd={cmd}, args={args[:50]}...")

        if cmd == "help":
            await self._cmd_help(user_id)
        elif cmd == "img":
            await self.image_cap.text_to_image(user_id, args)
        elif cmd == "t2v":
            await self.video_cap.text_to_video(user_id, args)
        elif cmd == "tts":
            await self.voice_cap.text_to_speech(user_id, args)
        elif cmd == "music":
            await self.music_cap.text_to_music(user_id, args)
        else:
            await self._cmd_unknown(user_id, cmd)

    async def _cmd_help(self, user_id: str):
        """显示帮助"""
        await self.delivery.send_text(user_id, HELP_TEXT)

    async def _cmd_unknown(self, user_id: str, cmd: str):
        """未知命令"""
        await self.delivery.send_error(
            user_id,
            f"未知子命令: {cmd}\n\n请输入 #mm help 查看所有可用命令",
        )
