"""
文件处理工具函数
"""
import os
from datetime import datetime
from pathlib import Path
from typing import Optional


def save_temp_file(
    content: str,
    prefix: str,
    directory: Optional[Path] = None,
    extension: str = "txt"
) -> Path:
    """保存内容到临时文件

    Args:
        content: 文件内容
        prefix: 文件名前缀
        directory: 保存目录，默认使用 get_settings().UPLOAD_DIR
        extension: 文件扩展名，默认 "txt"

    Returns:
        Path: 保存的文件路径
    """
    from src.config.settings import Config, get_settings

    dir_path = directory or get_settings().UPLOAD_DIR
    dir_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{prefix}_{timestamp}.{extension}"
    file_path = dir_path / file_name

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)

    return file_path
