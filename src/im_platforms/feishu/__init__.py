"""
飞书平台实现

实现 IIMPlatform 接口，提供飞书特定的消息发送和事件处理功能
"""# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

import asyncio# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

import json# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

import re
from pathlib import Path
from typing import Dict, Any, Optional, List

from src.interfaces.im_platform import (
    IIMPlatform,
    IIMCardBuilder,
    NormalizedMessage,
    NormalizedUser,
    NormalizedCard,
    PlatformConfig,
    MessageType,
)
from src.feishu import FeishuAPI, FeishuWebSocketClient
from src.interfaces.websocket_client import IWebSocketClient, WebSocketEvent, EventType
from src.config.settings import Config

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class FeishuPlatform(IIMPlatform):
    """飞书平台实现"""

    def __init__(self, config: PlatformConfig):
        self.config = config
        self.api = FeishuAPI(config.app_id, config.app_secret)
        self._domain = config.domain
        self._receive_id_type = config.receive_id_type
        # WebSocket 客户端在需要时创建
        self._ws_client: Optional[FeishuWebSocketClient] = None

    @property
    def verification_token(self) -> Optional[str]:
        """获取验证令牌（从额外配置中）"""
        return self.config.extra.get("verification_token")

    def get_websocket_client(self) -> Optional[IWebSocketClient]:
        """
        获取 WebSocket 客户端

        Returns:
            WebSocket 客户端实例
        """
        if self._ws_client is None:
            # verification_token 实际上未被 WebSocket 连接使用，因此即使没有也创建客户端
            token = self.verification_token or ""
            self._ws_client = FeishuWebSocketClient(
                self.config.app_id,
                self.config.app_secret,
                token
            )
        return self._ws_client

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT
    ) -> bool:
        """发送消息给用户"""
        try:
            return await self.api.send_message(user_id, content)
        except Exception as e:
            logger.error(f"发送消息失败: {e}", exc_info=True)
            return False

    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard
    ) -> bool:
        """
        发送富卡片消息

        将 NormalizedCard 转换为飞书卡片格式并发送
        """
        try:
            logger.info(f"FeishuPlatform.send_card 开始: user_id={user_id}, card={card.title}")
            logger.info(f"self.api: {self.api}")

            # 将 NormalizedCard 转换为飞书卡片 JSON
            feishu_card = self._convert_normalized_card_to_feishu(card)
            logger.info(f"转换后的飞书卡片: {feishu_card[:200]}...")
            logger.info(f"准备调用 self.api.send_message")

            result = await self.api.send_message(user_id, feishu_card)
            logger.info(f"api.send_message 返回: {result}")
            return result
        except Exception as e:
            logger.error(f"发送卡片失败: {e}", exc_info=True)
            return False

    async def send_file(
        self,
        user_id: str,
        file_key: str,
    ) -> bool:
        """发送文件消息"""
        try:
            return await self.api.send_file_message(user_id, file_key)
        except Exception as e:
            logger.error(f"发送文件失败: {e}", exc_info=True)
            return False

    async def download_file(
        self,
        message_id: str,
        file_key: str,
        save_dir: Optional[Path] = None
    ) -> Optional[Path]:
        """从飞书下载文件"""
        try:
            return await self.api.download_file(message_id, file_key, save_dir)
        except Exception as e:
            logger.error(f"下载文件失败: {e}", exc_info=True)
            return None

    async def get_user_info(self, user_id: str) -> Optional[NormalizedUser]:
        """获取用户信息"""
        try:
            user_info = await self.api.get_user_info(user_id)
            if user_info:
                return NormalizedUser(
                    user_id=user_info["user_id"],
                    name=user_info.get("name"),
                    avatar=user_info.get("avatar")
                )
            return None
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}", exc_info=True)
            return None

    async def upload_file(
        self,
        file_path: Path,
        file_type: str = "stream"
    ) -> Optional[str]:
        """上传文件到飞书，返回 file_key"""
        try:
            return await self.api.upload_file(file_path, file_type)
        except Exception as e:
            logger.error(f"上传文件失败: {e}", exc_info=True)
            return None

    def parse_event(self, event_data: Dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        解析飞书事件为标准化消息

        Args:
            event_data: 飞书事件数据

        Returns:
            标准化消息对象
        """
        try:
            event_type = event_data.get("type")

            # 处理消息接收事件
            if event_type == "im.message.receive_v1":
                event = event_data.get("event", {})
                sender = event.get("sender", {})
                message = event.get("message", {})

                user_id = sender.get("sender_id", {}).get("open_id")
                message_id = message.get("message_id")
                content = message.get("content")
                msg_type = message.get("msg_type")

                if not user_id or not content:
                    logger.warning("消息数据不完整")
                    return None

                # 解析消息内容
                content_data = json.loads(content)

                # 确定消息类型
                if msg_type == "image":
                    message_type = MessageType.IMAGE
                    text_content = ""
                    attachments = [{"image_key": content_data.get("image_key")}]
                elif msg_type == "file":
                    message_type = MessageType.FILE
                    text_content = ""
                    attachments = [{"file_key": content_data.get("file_key")}]
                elif msg_type == "audio":
                    message_type = MessageType.VOICE
                    text_content = ""
                    attachments = [{"file_key": content_data.get("file_key")}]
                elif msg_type == "interactive":
                    message_type = MessageType.INTERACTION
                    text_content = content_data.get("text", "")
                    attachments = []
                else:  # text 或其他类型
                    message_type = MessageType.TEXT
                    text_content = content_data.get("text", "")
                    attachments = []

                return NormalizedMessage(
                    message_id=message_id,
                    user_id=user_id,
                    chat_id=None,  # 飞书单聊没有 chat_id
                    message_type=message_type,
                    content=text_content,
                    raw_data=event_data,
                    attachments=attachments,
                    timestamp=message.get("create_time")
                )

            # 处理卡片交互事件
            elif event_type == "im.message.message_read_v1":
                # 消息已读事件
                return None

            elif event_type == "card.action.trigger":
                # 卡片按钮点击事件
                return None

            else:
                logger.debug(f"未处理的事件类型: {event_type}")
                return None

        except Exception as e:
            logger.error(f"解析飞书事件失败: {e}", exc_info=True)
            return None

    def is_platform_command(self, content: str) -> bool:
        """
        检查内容是否为飞书平台特定命令

        飞书平台使用 # 开头的命令作为平台命令
        """
        return content.strip().startswith("#")

    def _convert_normalized_card_to_feishu(self, card: NormalizedCard) -> str:
        """
        将 NormalizedCard 转换为飞书卡片 JSON 格式

        Args:
            card: 标准化卡片

        Returns:
            飞书卡片 JSON 字符串

        Note:
            card.content 现在包含展示内容（包含编号和时间戳）
            由 NormalizedCard 的 get_display_content() 方法自动生成
        """
        # 使用展示内容（包含元数据）
        content = card.content

        feishu_card = {
            "schema": "2.0",
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {"tag": "plain_text", "content": card.title},
                "template": card.template_color
            },
            "body": {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": content
                    }
                ]
            }
        }
        return json.dumps(feishu_card, ensure_ascii=False)


class FeishuCardBuilder(IIMCardBuilder):
    """飞书卡片构建器实现"""

    @staticmethod
    def create_command_card(
        command: str
    ) -> NormalizedCard:
        """创建命令确认卡片（直接使用 NormalizedCard）"""
        content = f"命令: `{command}`\n状态: 开始处理..."
        return NormalizedCard(
            card_type="command",
            title="命令确认",
            content=content,
            template_color="grey"
        )

    @staticmethod
    def create_output_card(
        output: str,
        title: str = "Output"
    ) -> NormalizedCard:
        """创建输出显示卡片（直接使用 NormalizedCard）"""
        content = f"屏幕内容:\n\n```\n{output}\n```"
        return NormalizedCard(
            card_type="output",
            title=title,
            content=content,
            template_color="grey"
        )

    @staticmethod
    def create_error_card(
        error: str
    ) -> NormalizedCard:
        """创建错误卡片（直接使用 NormalizedCard）"""
        content = f"错误: {error}"
        return NormalizedCard(
            card_type="error",
            title="错误",
            content=content,
            template_color="red"
        )

    @staticmethod
    def _extract_content(card_data: Dict[str, Any]) -> str:
        """从飞书卡片数据中提取内容文本（去除消息编号和时间头部）"""
        body = card_data.get("body", {})
        elements = body.get("elements", [])

        contents = []
        for element in elements:
            if element.get("tag") == "markdown":
                content = element.get("content", "")
                # 去除消息编号和时间头部（格式：📨 **消息编号**: xxx\n🕒 `xxx`\n\n）
                # 匹配以 📨 **消息编号**: 开头到空行之前的内容
                content = re.sub(r'^📨 \*\*消息编号\*\*:.*?\n🕒 `.*?`\n\n', '', content, flags=re.DOTALL)
                contents.append(content)
            elif element.get("tag") == "div":
                # 处理 div 元素中的文本
                text = element.get("text", {})
                if isinstance(text, str):
                    contents.append(text)
                elif isinstance(text, dict):
                    contents.append(text.get("content", ""))

        return "\n".join(contents) if contents else ""

    @staticmethod
    def create_help_card(help_text: str) -> NormalizedCard:
        """创建帮助卡片"""
        return NormalizedCard(
            card_type="help",
            title="帮助",
            content=help_text,
            template_color="grey"
        )

    @staticmethod
    def create_history_card(history_text: str) -> NormalizedCard:
        """创建历史记录卡片"""
        return NormalizedCard(
            card_type="history",
            title="历史记录",
            content=history_text,
            template_color="grey"
        )

    @staticmethod
    def create_cancel_card(message: str) -> NormalizedCard:
        """创建取消确认卡片"""
        return NormalizedCard(
            card_type="cancel",
            title="取消",
            content=message,
            template_color="grey"
        )

    @staticmethod
    def create_download_image_card(message: str) -> NormalizedCard:
        """创建下载图片确认卡片"""
        return NormalizedCard(
            card_type="download_image",
            title="下载图片",
            content=message,
            template_color="grey"
        )

    @staticmethod
    def create_download_voice_card(message: str) -> NormalizedCard:
        """创建下载语音确认卡片"""
        return NormalizedCard(
            card_type="download_voice",
            title="下载语音",
            content=message,
            template_color="grey"
        )


def register_feishu_platform():
    """注册飞书平台到工厂"""
    from src.factories.platform_factory import IMPlatformFactory
    IMPlatformFactory.register_platform("feishu", FeishuPlatform, FeishuCardBuilder)
