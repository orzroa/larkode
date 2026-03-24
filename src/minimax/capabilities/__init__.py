"""
MiniMax 能力模块

提供：图片生成、视频生成、语音合成、音乐生成
"""
from src.minimax.capabilities.image_gen import ImageGenCapability
from src.minimax.capabilities.video_gen import VideoGenCapability
from src.minimax.capabilities.voice_tts import VoiceTTSCapability
from src.minimax.capabilities.music_gen import MusicGenCapability

__all__ = [
    "ImageGenCapability",
    "VideoGenCapability",
    "VoiceTTSCapability",
    "MusicGenCapability",
]