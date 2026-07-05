"""
队列监控器

监控 ~/.larkode/queue/pending/ 目录，发现文件后上传到飞书并发送给用户
"""
import asyncio
import logging
import shutil
from datetime import datetime
from pathlib import Path

from src.config.settings import get_settings
from src.feishu.file_ops import upload_file, send_file_message

logger = logging.getLogger(__name__)

# 队列目录
QUEUE_DIR = Path.home() / ".larkode" / "queue"
PENDING_DIR = QUEUE_DIR / "pending"
SENT_DIR = QUEUE_DIR / "sent"
FAILED_DIR = QUEUE_DIR / "failed"


class QueueMonitor:
    """队列监控器"""

    def __init__(self, feishu_api):
        """
        初始化队列监控器

        Args:
            feishu_api: FeishuAPI 实例（用于获取 app_secret）
        """
        self._feishu_api = feishu_api
        self._app_secret = feishu_api.app_secret
        self._user_id_warned = False

    async def monitor_queue(self):
        """监控队列目录"""
        # 确保目录存在
        PENDING_DIR.mkdir(parents=True, exist_ok=True)
        SENT_DIR.mkdir(parents=True, exist_ok=True)
        FAILED_DIR.mkdir(parents=True, exist_ok=True)

        logger.info(f"队列监控已启动: {PENDING_DIR}")

        while True:
            try:
                # 扫描 pending 目录
                pending_files = list(PENDING_DIR.iterdir())

                for file_path in pending_files:
                    if file_path.is_file():
                        logger.info(f"发现待发送文件: {file_path.name}")
                        await self._send_file(file_path)

                # 每 30 秒检查一次
                await asyncio.sleep(30)

            except Exception as e:
                logger.error(f"监控队列时出错: {e}", exc_info=True)
                await asyncio.sleep(60)

    async def _send_file(self, file_path: Path):
        """
        发送文件到飞书

        Args:
            file_path: 文件路径
        """
        try:
            # 获取目标用户 ID
            target_user = get_settings().FEISHU_HOOK_NOTIFICATION_USER_ID
            if not target_user:
                if not self._user_id_warned:
                    logger.warning("未配置目标用户 ID (FEISHU_HOOK_NOTIFICATION_USER_ID)，跳过发送")
                    self._user_id_warned = True
                return

            # 如果配置是 union_id 类型，但传入的是 open_id，自动转换
            receive_id = target_user
            receive_id_type = get_settings().FEISHU_MESSAGE_RECEIVE_ID_TYPE
            if receive_id_type == "union_id" and target_user.startswith("ou_"):
                logger.info(f"open_id → union_id 转换中: {target_user}")
                union_id = await self._feishu_api.open_id_to_union_id(target_user)
                if union_id:
                    receive_id = union_id
                    logger.info(f"转换为 union_id: {receive_id}")
                else:
                    logger.warning(f"open_id 转 union_id 失败，将使用原 ID")

            # 上传文件（失败会抛出异常）
            logger.info(f"上传文件: {file_path.name}")
            file_key = await upload_file(self._app_secret, file_path)

            # 发送文件消息
            logger.info(f"发送文件消息给用户: {receive_id} (类型: {receive_id_type})")
            success = await send_file_message(self._app_secret, receive_id, file_key, receive_id_type)

            if success:
                # 移动到 sent 目录（带时间戳）
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                sent_name = f"{timestamp}_{file_path.name}"
                sent_path = SENT_DIR / sent_name
                shutil.move(str(file_path), str(sent_path))
                logger.info(f"文件已发送并归档: {sent_path}")
            else:
                # 发送失败，移动到 failed 目录避免重复尝试
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                failed_name = f"{timestamp}_{file_path.name}"
                failed_path = FAILED_DIR / failed_name
                shutil.move(str(file_path), str(failed_path))
                logger.error(f"文件消息发送失败，已移至失败目录: {failed_path}")

        except Exception as e:
            logger.error(f"发送文件时出错: {file_path.name}, 错误: {e}", exc_info=True)