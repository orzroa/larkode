"""
MiniMax 多媒体能力集成

提供：图片生成、视频生成、语音合成、音乐生成
"""
from src.minimax.client import MiniMaxClient, get_minimax_client
from src.minimax.feishu_delivery import MiniMaxFeishuDelivery
from src.minimax.commands import MiniMaxCommands, HELP_TEXT

__all__ = [
    "MiniMaxClient",
    "get_minimax_client",
    "MiniMaxFeishuDelivery",
    "MiniMaxCommands",
    "HELP_TEXT",
]