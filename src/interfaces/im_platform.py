"""
IM 平台抽象层

定义接口以解耦特定 IM 平台（飞书、Slack、钉钉等）
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from enum import Enum


class MessageType(str, Enum):
    """跨平台消息类型"""
    TEXT = "text"
    IMAGE = "image"
    FILE = "file"
    CARD = "card"
    INTERACTION = "interaction"
    VOICE = "voice"


class NormalizedMessage:
    """跨平台标准化消息格式"""
    def __init__(
        self,
        message_id: str,
        user_id: str,
        chat_id: Optional[str],
        message_type: MessageType,
        content: str,
        raw_data: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None,
        timestamp: Optional[str] = None,
    ):
        self.message_id = message_id
        self.user_id = user_id
        self.chat_id = chat_id
        self.message_type = message_type
        self.content = content
        self.raw_data = raw_data
        self.attachments = attachments or []
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "message_id": self.message_id,
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "message_type": self.message_type.value,
            "content": self.content,
            "attachments": self.attachments,
            "timestamp": self.timestamp,
            "raw_data": self.raw_data,
        }


class NormalizedUser:
    """标准化用户信息"""
    def __init__(
        self,
        user_id: str,
        name: Optional[str] = None,
        avatar: Optional[str] = None,
    ):
        self.user_id = user_id
        self.name = name
        self.avatar = avatar

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "user_id": self.user_id,
            "name": self.name,
            "avatar": self.avatar,
        }


class NormalizedCard:
    """
    标准化卡片格式（用于富消息）

    重构说明：
    - content 现在存储纯内容，不包含元数据
    - 卡片编号 (card_id) 和时间戳 (timestamp) 作为单独属性
    - 展示时使用 get_display_content() 方法添加元数据
    - 数据库存储时使用 get_pure_content() 获取纯内容
    """
    def __init__(
        self,
        card_type: str,
        title: str,
        content: str,
        template_color: str = "grey",
        card_id: Optional[int] = None,
        timestamp: Optional[str] = None,
    ):
        import os
        from datetime import datetime
        from src.utils.card_id import get_card_id_manager
        from src.config.settings import get_settings

        self.card_type = card_type
        self.title = title
        self.template_color = template_color

        # 纯内容（不包含元数据）
        self._pure_content = content

        # 卡片编号（如果未提供则自动生成）
        if card_id is None:
            manager = get_card_id_manager()
            self.card_id = int(manager.get_next_id())
        else:
            self.card_id = card_id

        # 时间戳（如果未提供则自动生成）
        if timestamp is None:
            self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        else:
            self.timestamp = timestamp

        # 为了向后兼容，保留 content 属性为展示内容（包含元数据）
        self.content = self.get_display_content()

    @property
    def pure_content(self) -> str:
        """获取纯内容（只读属性）"""
        return self._pure_content

    def get_pure_content(self) -> str:
        """获取纯内容（用于存储到数据库）

        Returns:
            str: 纯内容，不包含元数据
        """
        return self._pure_content

    def get_display_content(self) -> str:
        """获取展示内容（包含编号和时间戳）

        Returns:
            str: 包含元数据的展示内容
        """
        return f"📨 **卡片编号**: {self.card_id}\n🕒 `{self.timestamp}`\n{self._pure_content}"

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "card_type": self.card_type,
            "title": self.title,
            "content": self.content,  # 展示内容（包含元数据）
            "template_color": self.template_color,
            "card_id": self.card_id,
            "timestamp": self.timestamp,
        }


class PlatformConfig:
    """平台特定配置"""
    def __init__(
        self,
        app_id: str,
        app_secret: str,
        domain: Optional[str] = None,
        receive_id_type: str = "user_id",
        **kwargs
    ):
        self.app_id = app_id
        self.app_secret = app_secret
        self.domain = domain
        self.receive_id_type = receive_id_type
        self.extra = kwargs

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "app_id": self.app_id,
            "app_secret": self.app_secret,
            "domain": self.domain,
            "receive_id_type": self.receive_id_type,
            "extra": self.extra,
        }


class IIMPlatform(ABC):
    """IM 平台接口"""

    @abstractmethod
    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT
    ) -> bool:
        """发送消息给用户"""
        pass

    @abstractmethod
    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard
    ) -> bool:
        """发送富卡片消息"""
        pass

    @abstractmethod
    async def send_file(
        self,
        user_id: str,
        file_key: str,
    ) -> bool:
        """发送文件消息"""
        pass

    @abstractmethod
    async def download_file(
        self,
        message_id: str,
        file_key: str,
        save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """从平台下载文件"""
        pass

    @abstractmethod
    async def get_user_info(self, user_id: str) -> Optional[NormalizedUser]:
        """获取用户信息"""
        pass

    @abstractmethod
    async def upload_file(
        self,
        file_path: Path,
        file_type: str = "stream"
    ) -> Optional[str]:
        """上传文件到平台，返回 file_key"""
        pass

    @abstractmethod
    def parse_event(self, event_data: Dict[str, Any]) -> Optional[NormalizedMessage]:
        """解析平台特定事件为标准化消息"""
        pass

    @abstractmethod
    def is_platform_command(self, content: str) -> bool:
        """检查内容是否为平台特定命令（如 #help, #cancel）"""
        pass


class IIMCardBuilder(ABC):
    """卡片构建器接口"""

    @abstractmethod
    def create_command_card(
        self,
        command: str
    ) -> NormalizedCard:
        """创建命令确认卡片"""
        pass

    @abstractmethod
    def create_output_card(
        self,
        output: str,
        title: str = "Output",
        message_number: str = ""
    ) -> NormalizedCard:
        """创建输出显示卡片"""
        pass

    @abstractmethod
    def create_error_card(
        self,
        error: str,
        message_number: str = ""
    ) -> NormalizedCard:
        """创建错误卡片"""
        pass
