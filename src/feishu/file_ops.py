"""
飞书文件操作：下载、上传
"""
import imghdr
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from src.config.settings import get_settings
from src.feishu.exceptions import FeishuAPIUploadError

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


def _detect_audio_extension(file_path: Path) -> str:
    """
    检测音频文件扩展名

    Args:
        file_path: 文件路径

    Returns:
        str: 正确的扩展名（如 .amr, .mp3, .wav 等）
    """
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)

        # AMR 文件头识别
        if header.startswith(b'#AMR'):
            return '.amr'
        # MP3 文件头 (ID3 标签或 MPEG 同步字)
        if header[:3] == b'ID3' or header[:2] == b'\xff\xfb' or header[:2] == b'\xff\xf3':
            return '.mp3'
        # WAV 文件头
        if header[:4] == b'RIFF' and header[8:12] == b'WAVE':
            return '.wav'
        # OGG 文件头
        if header[:4] == b'OggS':
            return '.ogg'
        # M4A/AAC 文件头 (ftyp 标识)
        if header[4:8] == b'ftyp':
            return '.m4a'
        # FLAC 文件头
        if header[:4] == b'fLaC':
            return '.flac'
        # AAC/ADTS 文件头
        if header[:2] == b'\xff\xf1' or header[:2] == b'\xff\xf9':
            return '.aac'

        # 默认返回 .amr（飞书语音默认格式）
        logger.warning(f"无法识别音频类型，使用默认扩展名 .amr，文件头: {header[:8].hex()}")
        return '.amr'
    except Exception as e:
        logger.error(f"检测音频扩展名时出错: {e}")
        return '.amr'


def _create_client(app_secret: str):
    """创建飞书客户端"""
    import lark_oapi as lark
    return lark.Client.builder() \
        .app_id(get_settings().FEISHU_APP_ID) \
        .app_secret(app_secret) \
        .domain(getattr(lark, get_settings().FEISHU_MESSAGE_DOMAIN)) \
        .log_level(lark.LogLevel.WARNING) \
        .build()


def _get_save_path(file_key: str, save_dir: Optional[Path] = None) -> Path:
    """生成保存路径"""
    if save_dir is None:
        save_dir = Path(__file__).parent.parent.parent / "uploads"
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    file_path = save_dir / f"{timestamp}_{file_key}"
    return file_path


async def download_file(
    app_secret: str,
    message_id: str,
    file_key: str,
    save_dir: Optional[Path] = None
) -> Optional[Path]:
    """
    下载飞书文件到本地

    Args:
        app_secret: 飞书应用密钥
        message_id: 消息 ID
        file_key: 文件的 file_key
        save_dir: 保存目录

    Returns:
        Path: 保存后的文件路径，失败返回 None
    """
    try:
        import lark_oapi as lark

        client = _create_client(app_secret)

        # 构造请求对象
        request = lark.api.im.v1.GetMessageResourceRequest.builder() \
            .message_id(message_id) \
            .file_key(file_key) \
            .type("file") \
            .build()

        # 发起请求
        response = client.im.v1.message_resource.get(request)

        if not response.success():
            logger.error(
                f"获取文件资源失败: code: {response.code}, msg: {response.msg}, "
                f"log_id: {response.get_log_id()}"
            )
            return None

        # 确定文件名
        file_name = getattr(response, 'file_name', None)
        if not file_name:
            file_name = f"feishu_{file_key}.txt"

        # 生成保存路径
        file_path = _get_save_path(file_key, save_dir)
        file_path = file_path.parent / f"{file_path.stem}_{file_name}"

        # 保存文件
        file_obj = response.file
        with open(file_path, "wb") as f:
            f.write(file_obj.read())

        # 文件类型识别：图片和音频是两个独立分支，互斥处理
        valid_image_exts = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
        valid_audio_exts = {'.amr', '.mp3', '.wav', '.ogg', '.m4a', '.flac', '.aac'}

        if file_path.exists():
            current_ext = file_path.suffix.lower()
            detected_type = imghdr.what(str(file_path))

            if detected_type:
                # 分支1：识别为图片
                correct_ext = f".{detected_type}"
                if current_ext != correct_ext:
                    new_path = file_path.with_suffix(correct_ext)
                    file_path.rename(new_path)
                    file_path = new_path
                    logger.info(f"图片类型识别为 {detected_type}，已重命名为: {file_path}")
                else:
                    logger.info(f"图片类型确认: {detected_type}")
            elif current_ext not in valid_audio_exts:
                # 分支2：不是图片，且当前不是已知音频扩展名，尝试识别音频
                detected_ext = _detect_audio_extension(file_path)
                if detected_ext != current_ext:
                    new_path = file_path.with_suffix(detected_ext)
                    file_path.rename(new_path)
                    file_path = new_path
                    logger.info(f"语音类型识别为 {detected_ext}，已重命名为: {file_path}")
                else:
                    logger.info(f"语音类型确认: {detected_ext}")
            else:
                # 分支3：既不是图片也不是音频，或已经是正确扩展名
                logger.info(f"文件保持原样: {file_path}")

        logger.info(f"文件已保存到: {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"下载文件时出错: {e}", exc_info=True)
        return None


async def upload_image(
    app_secret: str,
    image_path: Path
) -> Optional[str]:
    """
    上传图片到飞书

    Args:
        app_secret: 飞书应用密钥
        image_path: 图片文件路径

    Returns:
        image_key: 上传成功返回 image_key，失败返回 None
    """
    try:
        import lark_oapi as lark

        client = _create_client(app_secret)

        # 打开图片文件
        with open(image_path, "rb") as file:
            # 构建图片上传请求
            request = lark.api.im.v1.CreateImageRequest.builder() \
                .request_body(
                    lark.api.im.v1.CreateImageRequestBody.builder()
                    .image_type("message")
                    .image(file)
                    .build()
                ) \
                .build()

            # 上传图片
            response = client.im.v1.image.create(request)

            if response.success() and response.data:
                image_key = response.data.image_key
                logger.info(f"图片上传成功: {image_path.name}, image_key: {image_key}")
                return image_key
            else:
                logger.error(f"图片上传失败: code: {response.code}, msg: {response.msg}")
                return None

    except Exception as e:
        logger.error(f"上传图片时出错: {e}", exc_info=True)
        return None


async def upload_file(
    app_secret: str,
    file_path: Path,
    file_type: str = None
) -> Optional[str]:
    """
    上传文件到飞书

    Args:
        app_secret: 飞书应用密钥
        file_path: 文件路径
        file_type: 文件类型 (stream, docx, pdf 等)

    Returns:
        file_key: 上传成功返回 file_key，失败返回 None
    """
    if file_type is None:
        file_type = get_settings().FILE_UPLOAD_TYPE

    try:
        import lark_oapi as lark

        client = _create_client(app_secret)

        # 打开文件
        with open(file_path, "rb") as file:
            # 构建文件上传请求
            request = lark.api.im.v1.CreateFileRequest.builder() \
                .request_body(
                    lark.api.im.v1.CreateFileRequestBody.builder()
                    .file_type(file_type)
                    .file_name(file_path.name)
                    .file(file)
                    .build()
                ) \
                .build()

            # 上传文件
            response = client.im.v1.file.create(request)

            if response.success() and response.data:
                file_key = response.data.file_key
                logger.info(f"文件上传成功: {file_path.name}, file_key: {file_key}")
                return file_key
            else:
                logger.error(f"文件上传失败: code: {response.code}, msg: {response.msg}")
                raise FeishuAPIUploadError(f"文件上传失败: {response.code} - {response.msg}")

    except FeishuAPIUploadError:
        raise
    except Exception as e:
        logger.error(f"上传文件时出错: {e}", exc_info=True)
        raise FeishuAPIUploadError(f"上传文件时出错: {e}")


async def send_file_message(
    app_secret: str,
    user_id: str,
    file_key: str
) -> bool:
    """
    发送文件消息

    Args:
        app_secret: 飞书应用密钥
        user_id: 用户 ID
        file_key: 文件的 file_key

    Returns:
        bool: 发送成功返回 True，失败返回 False
    """
    try:
        import lark_oapi as lark

        client = _create_client(app_secret)

        # 构建消息请求
        content = json.dumps({"file_key": file_key})
        request = lark.api.im.v1.CreateMessageRequest.builder() \
            .receive_id_type(get_settings().FEISHU_MESSAGE_RECEIVE_ID_TYPE) \
            .request_body(
                lark.api.im.v1.CreateMessageRequestBody.builder()
                .msg_type("file")
                .receive_id(user_id)
                .content(content)
                .build()
            ) \
            .build()

        # 发送消息
        response = client.im.v1.message.create(request)

        if response.success():
            logger.info(f"文件消息发送成功: {file_key}")
            return True
        else:
            logger.error(f"文件消息发送失败: {response.code} - {response.msg}")
            return False

    except Exception as e:
        logger.error(f"发送文件消息时出错: {e}", exc_info=True)
        return False
