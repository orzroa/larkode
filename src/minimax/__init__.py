"""
MiniMax 多媒体能力集成

提供：图片生成、视频生成、语音合成、音乐生成
"""
from src.minimax.client import MiniMaxClient, get_minimax_client
from src.minimax.feishu_delivery import MiniMaxFeishuDelivery
from src.minimax.commands import MiniMaxCommands, HELP_TEXT

# 用户最近上传的图片缓存 {user_id: {"path": str, "url": str}}
_user_last_image: dict = {}


def set_user_image(user_id: str, image_path: str, image_url: str = ""):
    """设置用户最近上传的图片路径和 URL"""
    _user_last_image[user_id] = {"path": image_path, "url": image_url}


def get_user_image_path(user_id: str) -> str:
    """获取用户最近上传的图片本地路径"""
    return _user_last_image.get(user_id, {}).get("path", "")


def get_user_image_url(user_id: str) -> str:
    """获取用户最近上传的图片 URL"""
    return _user_last_image.get(user_id, {}).get("url", "")


__all__ = [
    "MiniMaxClient",
    "get_minimax_client",
    "MiniMaxFeishuDelivery",
    "MiniMaxCommands",
    "HELP_TEXT",
    "set_user_image",
    "get_user_image_path",
    "get_user_image_url",
]