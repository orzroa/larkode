"""
MiniMax API 客户端

支持：image_generation、video_generation、t2a（语音合成）、speech_to_text、music_generation

API Base URL: https://api.minimax.io
"""
import asyncio
import base64
import binascii
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from src.config.settings import get_settings
from src.minimax.exceptions import (
    MiniMaxAPIError,
    MiniMaxAuthError,
    MiniMaxRateLimitError,
    MiniMaxTimeoutError,
    MiniMaxUploadError,
)

# 优先使用新的日志工具
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)

BASE_URL = "https://api.minimaxi.com"


class MiniMaxClient:
    """MiniMax API 客户端"""

    def __init__(self, api_key: Optional[str] = None, group_id: Optional[str] = None):
        settings = get_settings()
        self.api_key = api_key or settings.minimax_api_key
        self.group_id = group_id or settings.minimax_group_id
        self._client: Optional[httpx.AsyncClient] = None

        if not self.api_key:
            logger.warning("MINIMAX_API_KEY 未配置，MiniMax 功能将不可用")

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _handle_response(self, response: httpx.Response) -> Dict[str, Any]:
        """处理 API 响应"""
        status = response.status_code
        try:
            data = response.json()
        except Exception:
            data = {}

        if status == 401:
            raise MiniMaxAuthError()
        if status == 429:
            raise MiniMaxRateLimitError()

        if status >= 400:
            msg = data.get("msg", data.get("message", "Unknown error"))
            raise MiniMaxAPIError(f"MiniMax API 错误: {msg}", status_code=status, response_data=data)

        # 检查 base_resp
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code") and base_resp["status_code"] != 0:
            code = base_resp.get("status_code", 0)
            msg = base_resp.get("status_msg", "Unknown error")
            raise MiniMaxAPIError(f"MiniMax API 错误: {msg} (code={code})", status_code=status, response_data=data)

        return data

    # ==================== Image Generation ====================

    async def image_generation(
        self,
        prompt: str,
        model: str = "image-01",
        response_format: str = "url",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        图片生成（同步，返回 URL 或 base64）

        Args:
            prompt: 提示词
            model: 模型名称（image-01）
            response_format: url 或 base64

        Returns:
            {"image_urls": [...]} 或 {"image_base64": [...]}
        """
        client = self._get_client()
        payload = {
            "model": model,
            "prompt": prompt,
            "response_format": response_format,
            **kwargs,
        }
        response = await client.post("/v1/image_generation", json=payload)
        data = self._handle_response(response)

        # 提取图片数据（统一格式）
        result = {}
        if "data" in data:
            if "image_urls" in data["data"]:
                result["image_urls"] = data["data"]["image_urls"]
            elif "image_base64" in data["data"]:
                result["image_base64"] = data["data"]["image_base64"]
        elif "image_urls" in data:
            result["image_urls"] = data["image_urls"]
        elif "image_base64" in data:
            result["image_base64"] = data["image_base64"]

        return result

    # ==================== Video Generation ====================

    async def text_to_video(
        self,
        prompt: str,
        model: str = "MiniMax-Hailuo-2.3",
        **kwargs,
    ) -> str:
        """
        文生视频

        Args:
            prompt: 提示词
            model: 模型名称

        Returns:
            task_id
        """
        client = self._get_client()
        payload = {
            "model": model,
            "prompt": prompt,
            **kwargs,
        }
        response = await client.post("/v1/video_generation", json=payload)
        data = self._handle_response(response)
        return data.get("task_id", "")

    async def image_to_video(
        self,
        prompt: str,
        image_path: str,
        model: str = "MiniMax-Hailuo-2.3-Fast",
        **kwargs,
    ) -> str:
        """
        图生视频

        Args:
            prompt: 提示词
            image_path: 图片路径（本地路径、URL 或 Base64）
            model: 模型名称

        Returns:
            task_id
        """
        client = self._get_client()

        # 判断输入类型并转换为合适的格式
        if image_path.startswith("http://") or image_path.startswith("https://"):
            # URL 格式，直接使用
            first_frame_image = image_path
        elif image_path.startswith("data:image"):
            # 已经是 Base64 格式
            first_frame_image = image_path
        else:
            # 本地文件，转换为 Base64
            import base64
            with open(image_path, "rb") as f:
                image_data = f.read()

            # 检测图片类型
            if image_path.lower().endswith(".png"):
                mime_type = "image/png"
            elif image_path.lower().endswith(".webp"):
                mime_type = "image/webp"
            else:
                mime_type = "image/jpeg"

            b64_data = base64.b64encode(image_data).decode("utf-8")
            first_frame_image = f"data:{mime_type};base64,{b64_data}"

        # 使用 first_frame_image 参数（Hailuo 系列模型）
        payload = {
            "model": model,
            "prompt": prompt,
            "first_frame_image": first_frame_image,
            **kwargs,
        }
        response = await client.post("/v1/video_generation", json=payload)
        data = self._handle_response(response)
        return data.get("task_id", "")

    async def get_video_task_result(self, task_id: str) -> Dict[str, Any]:
        """查询视频生成任务结果"""
        client = self._get_client()
        # 正确的查询端点是 /v1/query/video_generation?task_id=xxx
        response = await client.get(f"/v1/query/video_generation?task_id={task_id}")
        return self._handle_response(response)

    async def retrieve_file(self, file_id: str) -> Dict[str, Any]:
        """
        获取文件下载 URL

        Args:
            file_id: 文件 ID（从视频生成任务结果中获取）

        Returns:
            {"download_url": "...", "filename": "...", "bytes": ...}
        """
        client = self._get_client()
        response = await client.get(f"/v1/files/retrieve?file_id={file_id}")
        data = self._handle_response(response)
        file_info = data.get("file", {})
        return {
            "download_url": file_info.get("download_url", ""),
            "filename": file_info.get("filename", ""),
            "bytes": file_info.get("bytes", 0),
            "file_id": file_info.get("file_id"),
        }

    # ==================== TTS ====================

    async def text_to_speech(
        self,
        text: str,
        voice_id: str = "male-qn-qingse",
        model: str = "speech-2.8-hd",
        speed: float = 1.0,
        output_format: str = "mp3",
        **kwargs,
    ) -> bytes:
        """
        文字转语音

        Args:
            text: 要转换的文字
            voice_id: 音色 ID（默认 male-qn-qingse）
            model: 模型名称（默认 speech-2.8-hd）
            speed: 语速
            output_format: 音频格式

        Returns:
            音频二进制数据
        """
        client = self._get_client()
        payload = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": speed,
            },
            "audio_setting": {
                "format": output_format,
            },
            **kwargs,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=60.0) as c:
            response = await c.post("/v1/t2a_v2", json=payload)

        if response.status_code == 401:
            raise MiniMaxAuthError()
        if response.status_code == 429:
            raise MiniMaxRateLimitError()
        if response.status_code >= 400:
            try:
                data = response.json()
                msg = data.get("base_resp", {}).get("status_msg", "Unknown error")
            except Exception:
                msg = f"HTTP {response.status_code}"
            raise MiniMaxAPIError(f"TTS 错误: {msg}", status_code=response.status_code)

        # TTS V2 返回 hex 编码的音频
        try:
            data = response.json()
            if data.get("data", {}).get("audio"):
                hex_audio = data["data"]["audio"]
                return bytes.fromhex(hex_audio)
        except Exception:
            pass

        # Fallback: 直接返回二进制
        return response.content

    async def text_to_speech_streaming(self, text: str, voice_id: str = "female_tianmei", **kwargs):
        """
        文字转语音（流式）
        """
        client = self._get_client()
        payload = {
            "model": "speech-02-hd",
            "text": text,
            "stream": True,
            "voice_setting": {"voice_id": voice_id},
            **kwargs,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=60.0) as c:
            async with c.stream("POST", "/v1/t2a_v2", json=payload) as response:
                if response.status_code == 401:
                    raise MiniMaxAuthError()
                if response.status_code >= 400:
                    raise MiniMaxAPIError(f"TTS 流式错误: HTTP {response.status_code}", status_code=response.status_code)

                async for chunk in response.aiter_bytes():
                    if chunk:
                        yield chunk

    # ==================== Speech to Text ====================

    async def speech_to_text(
        self,
        audio_path: str,
        model: str = "speech-01",
        language_boost: str = "zh",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        语音转文字

        Args:
            audio_path: 音频文件路径
            model: 模型名称

        Returns:
            {"text": "..."}
        """
        client = self._get_client()

        with open(audio_path, "rb") as f:
            audio_data = f.read()

        files = {"file": (Path(audio_path).name, audio_data, "audio/mpeg")}
        data = {
            "model": model,
            "language_boost": language_boost,
            **kwargs,
        }

        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(base_url=BASE_URL, headers=headers, timeout=60.0) as c:
            response = await c.post("/v1/speech_recognition", data=data, files=files)
        return self._handle_response(response)

    # ==================== Music Generation ====================

    async def text_to_music(
        self,
        prompt: str,
        lyrics: str = "",
        model: str = "music-2.5",
        output_format: str = "url",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        文生音乐

        Args:
            prompt: 提示词（描述音乐风格/情绪）
            lyrics: 歌词（可选，但建议提供）
            model: 模型名称
            output_format: url 或 base64

        Returns:
            {"audio_url": "...", ...}
        """
        client = self._get_client()
        payload = {
            "model": model,
            "prompt": prompt,
            "output_format": output_format,
            **kwargs,
        }
        if lyrics:
            payload["lyrics"] = lyrics
        response = await client.post("/v1/music_generation", json=payload, timeout=180.0)
        data = self._handle_response(response)
        return data

    async def text_to_music_v2(
        self,
        prompt: str,
        model: str = "dfspphonk",
        duration: int = 60,
        output_format: str = "mp3",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        文生音乐 V2（使用 /v1/music/generation 端点）

        Args:
            prompt: 提示词（描述音乐风格/情绪）
            model: 模型名称（dfspphonk 等）
            duration: 音乐时长（秒）
            output_format: 输出格式（hex, wav, mp3）

        Returns:
            {"audio": "hex...", "extra_info": {...}}
        """
        client = self._get_client()
        payload = {
            "model": model,
            "prompt": prompt,
            "duration": duration,
            "output_format": output_format,
            "audio_setting": {
                "sample_rate": 44100,
                "bitrate": 256000,
                "format": output_format,
            },
            **kwargs,
        }
        response = await client.post("/v1/music/generation", json=payload, timeout=180.0)
        data = self._handle_response(response)
        return data

    async def get_music_task_result(self, task_id: str) -> Dict[str, Any]:
        """查询音乐生成任务结果"""
        client = self._get_client()
        response = await client.get(f"/v1/music_generation/{task_id}")
        return self._handle_response(response)

    # ==================== Async Task Polling ====================

    async def wait_for_task(
        self,
        task_id: str,
        get_result_fn,
        poll_interval: float = 3.0,
        timeout: int = 300,
    ) -> Dict[str, Any]:
        """
        轮询等待异步任务完成
        """
        import time as time_module

        start_time = time_module.time()
        while True:
            if time_module.time() - start_time > timeout:
                raise MiniMaxTimeoutError(task_id, timeout)

            result = await get_result_fn(task_id)

            status = result.get("status", result.get("base_resp", {}).get("status_msg", ""))
            if status in ("SUCCESS", "success", "Completed", "Success"):
                return result
            if status in ("FAIL", "fail", "Failed", "Error"):
                msg = result.get("message", result.get("msg", "任务失败"))
                raise MiniMaxAPIError(f"MiniMax 任务失败: {msg}", response_data=result)

            await asyncio.sleep(poll_interval)


# 全局客户端实例
_client: Optional[MiniMaxClient] = None


def get_minimax_client() -> MiniMaxClient:
    """获取全局 MiniMax 客户端实例"""
    global _client
    if _client is None:
        _client = MiniMaxClient()
    return _client
