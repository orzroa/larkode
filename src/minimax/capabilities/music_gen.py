"""
MiniMax 音乐生成能力

支持：#mm music <提示词>
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


class MusicGenCapability:
    """MiniMax 音乐生成能力"""

    def __init__(
        self,
        client: "MiniMaxClient",
        delivery: "MiniMaxFeishuDelivery",
    ):
        self.client = client
        self.delivery = delivery

    async def text_to_music(self, user_id: str, prompt: str):
        """
        文生音乐：#mm music <风格> <歌词>

        格式：#mm music <风格> <歌词内容>
        - 第一个空格前是风格
        - 剩下的都是歌词

        注意：必须提供歌词，API 要求 lyrics 参数
        """
        if not prompt.strip():
            await self.delivery.send_error(
                user_id,
                "请提供音乐提示词，例如：#mm music 古典 明月几时有...",
            )
            return

        # 解析风格和歌词
        style, lyrics = self._parse_music_prompt(prompt)

        # 必须提供歌词
        if not lyrics:
            await self.delivery.send_error(
                user_id,
                "❌ 必须提供歌词\n\n"
                "正确格式：\n"
                "`#mm music <风格> <歌词内容>`\n\n"
                "示例：\n"
                "`#mm music 古典 明月几时有，把酒问青天`",
            )
            return

        # MiniMax API 要求 prompt 至少 10 个字符
        if len(style) < 10:
            style = f"{style}风格，音乐优雅动听"

        progress_msg = f"🎵 正在生成音乐...\n\n风格：{style}\n歌词：{lyrics[:50]}{'...' if len(lyrics) > 50 else ''}\n\n预计需要 1-3 分钟"
        await self.delivery.send_progress(user_id, progress_msg)

        try:
            result = await self.client.text_to_music(
                prompt=style,
                lyrics=lyrics,
                output_format="url"
            )
            logger.info(f"音乐生成结果: {result}")

            # 提取音乐 URL - 在 data.audio 字段中
            data = result.get("data", {})
            audio_url = data.get("audio", "")
            extra_info = result.get("extra_info", {})

            if audio_url:
                duration_sec = extra_info.get("music_duration", 0) / 1000
                logger.info(f"音乐生成成功: 时长 {duration_sec:.1f}秒, URL: {audio_url[:60]}...")
                music_path = await self._download_music(user_id, audio_url)
                if music_path:
                    await self.delivery.send_file(user_id, music_path)
                else:
                    await self.delivery.send_error(user_id, "音乐下载失败")
            else:
                # 检查是否有错误信息
                base_resp = result.get("base_resp", {})
                error_msg = base_resp.get("status_msg", "未知错误")
                await self.delivery.send_error(
                    user_id,
                    f"音乐生成失败: {error_msg}\n\n原始响应: {result}",
                )

        except Exception as e:
            # 获取错误消息，如果 str(e) 为空则使用异常类型名
            error_str = str(e).strip()
            if not error_str:
                error_str = f"{type(e).__name__}"
                # 如果是 MiniMax 错误，尝试获取更多信息
                if hasattr(e, 'message') and e.message:
                    error_str = e.message
                elif hasattr(e, 'code') and e.code:
                    error_str = f"{type(e).__name__} (code={e.code})"

            logger.error(f"音乐生成失败: {error_str}", exc_info=True)
            await self.delivery.send_error(user_id, f"音乐生成失败: {error_str}")

    def _parse_music_prompt(self, prompt: str) -> tuple:
        """
        解析音乐提示词，提取风格和歌词

        格式：#mm music <风格> <歌词内容>
        - 第一个空格后的第一部分是风格
        - 剩下的都是歌词

        示例：
        - #mm music 古典 明月几时有，把酒问青天
        - #mm music 流行 啦~啦~啦~

        Returns:
            tuple: (style, lyrics)
        """
        prompt = prompt.strip()

        # 按空格分割，第一部分是风格，剩下的都是歌词
        parts = prompt.split(None, 1)  # None 表示任何空白字符，1 表示只分割一次

        if len(parts) == 0:
            return "", ""

        if len(parts) == 1:
            # 只有风格，没有歌词
            return parts[0], ""

        # 第一部分是风格，第二部分是歌词
        style = parts[0]
        lyrics = parts[1]

        return style, lyrics

    async def _download_music(self, user_id: str, url: str) -> Optional[Path]:
        """下载音乐文件"""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.get(url)
                response.raise_for_status()

            uploads_dir = Path(__file__).parent.parent.parent.parent / "uploads"
            uploads_dir.mkdir(parents=True, exist_ok=True)

            import time
            file_path = uploads_dir / f"mm_music_{int(time.time() * 1000)}.mp3"

            with open(file_path, "wb") as f:
                f.write(response.content)

            logger.info(f"音乐下载成功: {file_path}")
            return file_path

        except Exception as e:
            logger.error(f"下载音乐失败: {e}")
            return None
