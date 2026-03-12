"""
飞书 API 接口
"""
from pathlib import Path
from typing import Optional

# 导出异常类
from src.feishu.exceptions import (
    FeishuAPIError,
    FeishuAPISendError,
    FeishuAPIUploadError,
)

# 导出文件操作函数
from src.feishu.file_ops import (
    download_file,
    upload_file,
    send_file_message,
)

# 导出 WebSocket 客户端
from src.feishu.websocket import FeishuWebSocketClient

# 导出 API 类（含文件操作）
from src.feishu.api import FeishuAPI as _FeishuAPIBase


class FeishuAPI(_FeishuAPIBase):
    """飞书 API 客户端（含文件操作）"""

    async def download_file(self, message_id: str, file_key: str, save_dir: Optional[Path] = None):
        """下载飞书文件到本地"""
        return await download_file(self.app_secret, message_id, file_key, save_dir)

    async def upload_file(self, file_path: Path, file_type: str = None):
        """上传文件到飞书"""
        return await upload_file(self.app_secret, file_path, file_type)

    async def send_file_message(self, user_id: str, file_key: str, message_number: str = ""):
        """发送文件消息"""
        return await send_file_message(self.app_secret, user_id, file_key)
