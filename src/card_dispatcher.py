"""
卡片发送器 - 统一所有卡片发送入口

职责：
- 统一的卡片发送接口
- 协调卡片构建、编号管理、文件上传、数据库存储
- 根据内容长度自动判断是否上传文件
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from src.config.settings import get_settings
from src.models import Message, MessageType, MessageDirection, MessageSource
from src.storage import db
from src.utils.card_id import get_card_id_manager
from src.utils.file_utils import save_temp_file

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class CardDispatcher:
    """
    卡片发送器 - 统一所有卡片发送入口
    """

    # 需要文件上传的卡片类型
    FILE_UPLOAD_CARD_TYPES = {"stop", "prompt", "permission", "tmux"}

    def __init__(
        self,
        platform=None,
        feishu_api=None,
        notification_sender=None,
    ):
        """
        初始化卡片发送器

        Args:
            platform: IM 平台实例
            feishu_api: 飞书 API 实例
            notification_sender: 通知发送器（可选）
        """
        self.platform = platform
        self.feishu = feishu_api
        self._notification_sender = notification_sender
        self._card_id_manager = get_card_id_manager()

    def set_notification_sender(self, sender):
        """设置通知发送器"""
        self._notification_sender = sender

    def set_platform(self, platform):
        """设置平台实例"""
        self.platform = platform

    def set_feishu_api(self, feishu_api):
        """设置飞书 API 实例"""
        self.feishu = feishu_api

    def get_default_max_length(self) -> int:
        """获取默认的最大卡片长度"""
        return int(os.getenv("CARD_MAX_LENGTH", str(get_settings().CARD_MAX_LENGTH)))

    def should_use_file(self, card_type: str) -> bool:
        """判断是否应该使用文件上传"""
        use_file_env = os.getenv("USE_FILE_FOR_LONG_CONTENT", "true").lower() == "true"
        return use_file_env and card_type in self.FILE_UPLOAD_CARD_TYPES

    def _get_card_id(self) -> int:
        """获取下一个卡片编号"""
        return int(self._card_id_manager.get_next_id())

    def _format_timestamp(self, iso_timestamp: str) -> str:
        """格式化时间戳"""
        try:
            dt = datetime.fromisoformat(iso_timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return iso_timestamp

    def _build_display_content(
        self,
        pure_content: str,
        card_id: int,
        timestamp: str
    ) -> str:
        """构建展示内容（添加编号和时间戳）

        Args:
            pure_content: 纯内容
            card_id: 卡片编号
            timestamp: 时间戳（ISO 格式）

        Returns:
            str: 包含元数据的展示内容
        """
        formatted_time = self._format_timestamp(timestamp)
        return f"📨 **卡片编号**: {card_id}\n🕒 `{formatted_time}`\n{pure_content}"

    async def _upload_file_and_send(
        self,
        user_id: str,
        file_content: str,
        card_type: str,
        title: str,
        template_color: str,
        card_id: int,
        timestamp: str,
    ) -> Tuple[Optional[str], str]:
        """上传文件并发送说明卡片

        Args:
            user_id: 用户 ID
            file_content: 文件内容
            card_type: 卡片类型
            title: 卡片标题
            template_color: 卡片颜色
            card_id: 卡片编号
            timestamp: 时间戳

        Returns:
            Tuple[Optional[str], str]: (file_key, display_content)
        """
        file_key = None
        display_content = ""

        try:
            # 保存临时文件
            file_prefix = f"{card_type}_{card_id}"
            file_path = save_temp_file(file_content, file_prefix, extension="txt")
            file_name = file_path.name

            # 上传文件
            if self.feishu:
                file_key = await self.feishu.upload_file(file_path, get_settings().FILE_UPLOAD_TYPE)
                if file_key:
                    # 发送文件消息
                    await self.feishu.send_file_message(user_id, file_key)

                    # 构建说明卡片内容（包含编号和时间）
                    display_content = f"完整内容已保存为文件: `{file_name}`"
                else:
                    display_content = f"文件上传失败，但内容已保存为: `{file_name}`"
            else:
                display_content = f"文件上传不可用，内容已保存为: `{file_name}`"

        except Exception as e:
            logger.error(f"上传文件失败: {e}", exc_info=True)
            display_content = f"文件上传失败: {str(e)}"

        return file_key, display_content

    async def _send_normal_card(
        self,
        user_id: str,
        card_type: str,
        title: str,
        content: str,
        template_color: str,
        card_id: Optional[int] = None,
        timestamp: Optional[str] = None,
    ) -> Optional[str]:
        """发送普通卡片

        Args:
            user_id: 用户 ID
            card_type: 卡片类型
            title: 卡片标题
            content: 内容（纯内容）
            template_color: 卡片颜色
            card_id: 卡片编号（可选）
            timestamp: 时间戳（可选）

        Returns:
            Optional[str]: 飞书消息 ID
        """
        # 构建 NormalizedCard（包含元数据）
        from src.interfaces.im_platform import NormalizedCard

        # 创建 NormalizedCard（传入 card_id 和 timestamp，避免重复生成）
        card = NormalizedCard(
            card_type=card_type,
            title=title,
            content=content,
            template_color=template_color,
            card_id=card_id,
            timestamp=timestamp,
        )

        # 发送卡片
        if self._notification_sender:
            success = await self._notification_sender.send_card(user_id, card)
            if success:
                # 尝试获取 message_id
                if hasattr(self._notification_sender, 'last_message_id'):
                    return self._notification_sender.last_message_id
        elif self.platform:
            return await self.platform.send_card(user_id, card)

        return ""

    async def _store_message(
        self,
        user_id: str,
        pure_content: str,
        card_id: int,
        message_type: str = "response",
        feishu_message_id: str = "",
        message_source: MessageSource = MessageSource.FEISHU,
    ) -> None:
        """存储消息到数据库（只存储纯内容）

        Args:
            user_id: 用户 ID
            pure_content: 纯内容（不包含元数据）
            card_id: 卡片编号
            message_type: 消息类型
            feishu_message_id: 飞书消息 ID
            message_source: 消息来源
        """
        msg = Message(
            user_id=user_id,
            message_type=MessageType(message_type),
            content=pure_content,
            direction=MessageDirection.DOWNSTREAM,
            is_test=None,  # 使用全局测试模式
            message_source=message_source,
            feishu_message_id=feishu_message_id,
            card_id=card_id
        )
        db.save_message(msg)

    async def send_card(
        self,
        user_id: str,
        card_type: str,
        title: str,
        content: str,
        message_type: str = "response",
        template_color: str = "grey",
        max_length: Optional[int] = None,
        message_source: MessageSource = MessageSource.FEISHU,
    ) -> Tuple[str, Optional[str]]:
        """
        统一的卡片发送接口

        Args:
            user_id: 用户 ID
            card_type: 卡片类型
            title: 卡片标题
            content: 卡片内容（纯内容）
            message_type: 消息类型（response, status, error）
            template_color: 卡片颜色
            max_length: 最大长度限制，None 则使用默认配置
            message_source: 消息来源（FEISHU, HOOK, API_TEST）

        Returns:
            Tuple[str, Optional[str]]: (feishu_message_id, file_key or None)
        """
        # 1. 生成卡片编号和时间戳
        card_id = self._get_card_id()
        timestamp = datetime.now().isoformat()

        # 2. 检查内容长度
        max_length = max_length or self.get_default_max_length()
        need_file = len(content) > max_length and self.should_use_file(card_type)

        file_key = None
        feishu_message_id = ""
        display_content = ""
        pure_content = content  # 纯内容用于存储

        if need_file:
            # 上传文件并发送说明卡片
            file_key, display_content = await self._upload_file_and_send(
                user_id, content, card_type, title, template_color, card_id, timestamp
            )

            # 发送说明卡片（包含编号和时间）
            feishu_message_id = await self._send_normal_card(
                user_id, card_type, title, display_content, template_color, card_id, timestamp
            )
        else:
            # 直接发送卡片（包含完整内容和元数据）
            feishu_message_id = await self._send_normal_card(
                user_id, card_type, title, content, template_color, card_id, timestamp
            )

        # 3. 存储纯内容到数据库
        await self._store_message(
            user_id, pure_content, card_id, message_type, feishu_message_id, message_source
        )

        return feishu_message_id, file_key


# 全局实例（需要在运行时初始化）
_card_dispatcher: Optional[CardDispatcher] = None


def get_card_dispatcher() -> Optional[CardDispatcher]:
    """获取全局卡片发送器实例"""
    return _card_dispatcher


def set_card_dispatcher(dispatcher: CardDispatcher) -> None:
    """设置全局卡片发送器实例"""
    global _card_dispatcher
    _card_dispatcher = dispatcher