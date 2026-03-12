"""
Slack 平台实现（Stub）

这是一个 Slack 平台的存根实现，用于测试多平台架构。
实际使用时，需要集成 Slack Bolt SDK 来处理真实的 Slack API 交互。

TODO:
1. 安装 slack-bolt SDK
2. 实现 Slack API 集成
3. 实现 WebSocket 客户端（Slack 使用 Socket Mode 或 RTM API）
4. 实现卡片格式转换
5. 实现文件上传/下载
"""
from typing import Dict, Any, Optional, List
from pathlib import Path

from src.interfaces.im_platform import (
    IIMPlatform,
    IIMCardBuilder,
    NormalizedMessage,
    NormalizedUser,
    NormalizedCard,
    MessageType,
    PlatformConfig,
)

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class SlackPlatform(IIMPlatform):
    """
    Slack 平台实现

    当前是一个存根实现，实际使用时需要：
    1. 集成 slack-bolt SDK
    2. 实现 Slack App 的 OAuth 鉴权
    3. 实现事件监听和消息发送
    """

    def __init__(self, app_id: str, app_secret: str, bot_token: str = "", **kwargs):
        """
        初始化 Slack 平台

        Args:
            app_id: Slack App ID
            app_secret: Slack Client Secret (Signing Secret)
            bot_token: Slack Bot Token (xoxb-...)
            **kwargs: 其他配置
        """
        self._app_id = app_id
        self._app_secret = app_secret
        self._bot_token = bot_token
        self._extra_config = kwargs

        # TODO: 初始化 Slack Bolt App
        # from slack_bolt import App
        # self._app = App(
        #     token=bot_token,
        #     signing_secret=app_secret,
        # )

        logger.info("Slack 平台已初始化（存根模式）")

    async def send_message(
        self,
        user_id: str,
        content: str,
        message_type: MessageType = MessageType.TEXT,
    ) -> bool:
        """
        发送消息给用户

        Args:
            user_id: 用户 ID（在 Slack 中通常是用户 ID）
            content: 消息内容
            message_type: 消息类型

        Returns:
            发送成功返回 True，否则返回 False
        """
        # TODO: 实现 Slack 消息发送
        # await self._app.client.chat_postMessage(
        #     channel=user_id,
        #     text=content,
        # )
        logger.info(f"[Slack 存根] 发送消息到 {user_id}: {content[:50]}...")
        return True

    async def send_card(
        self,
        user_id: str,
        card: NormalizedCard,
    ) -> bool:
        """
        发送富卡片消息

        Args:
            user_id: 用户 ID
            card: 标准化卡片

        Returns:
            发送成功返回 True，否则返回 False
        """
        # TODO: 转换 NormalizedCard 为 Slack Block Kit 格式并发送
        # blocks = SlackCardBuilder.normalized_to_blocks(card)
        # await self._app.client.chat_postMessage(
        #     channel=user_id,
        #     blocks=blocks,
        # )
        logger.info(f"[Slack 存根] 发送卡片到 {user_id}: {card.title}")
        return True

    async def send_file(
        self,
        user_id: str,
        file_key: str,
    ) -> bool:
        """
        发送文件消息

        Args:
            user_id: 用户 ID
            file_key: 文件标识符

        Returns:
            发送成功返回 True，否则返回 False
        """
        # TODO: 实现 Slack 文件发送
        logger.info(f"[Slack 存根] 发送文件到 {user_id}: {file_key}")
        return True

    async def download_file(
        self,
        message_id: str,
        file_key: str,
        save_dir: Optional[Path] = None,
    ) -> Optional[Path]:
        """
        从平台下载文件

        Args:
            message_id: 消息 ID
            file_key: 文件标识符
            save_dir: 保存目录

        Returns:
            下载的文件路径，失败返回 None
        """
        # TODO: 实现 Slack 文件下载
        logger.info(f"[Slack 存根] 下载文件: {file_key}")
        return None

    async def get_user_info(self, user_id: str) -> Optional[NormalizedUser]:
        """
        获取用户信息

        Args:
            user_id: 用户 ID

        Returns:
            用户信息，失败返回 None
        """
        # TODO: 实现 Slack 用户信息获取
        # result = await self._app.client.users_info(user=user_id)
        # return NormalizedUser(
        #     user_id=user_id,
        #     name=result["user"]["name"],
        #     avatar=result["user"]["profile"]["image_72"],
        # )
        logger.info(f"[Slack 存根] 获取用户信息: {user_id}")
        return NormalizedUser(user_id=user_id)

    async def upload_file(
        self,
        file_path: Path,
        file_type: str = "stream",
    ) -> Optional[str]:
        """
        上传文件到平台

        Args:
            file_path: 文件路径
            file_type: 文件类型

        Returns:
            file_key（在 Slack 中是 file ID），失败返回 None
        """
        # TODO: 实现 Slack 文件上传
        # result = await self._app.client.files_upload_v2(
        #     file=str(file_path),
        # )
        # return result["file"]["id"]
        logger.info(f"[Slack 存根] 上传文件: {file_path}")
        return None

    def parse_event(self, event_data: Dict[str, Any]) -> Optional[NormalizedMessage]:
        """
        解析平台特定事件为标准化消息

        Args:
            event_data: Slack 事件数据

        Returns:
            标准化消息，无法解析返回 None
        """
        # TODO: 实现 Slack 事件解析
        # 示例事件格式：
        # {
        #     "type": "message",
        #     "user": "U1234567890",
        #     "text": "hello world",
        #     "ts": "1234567890.123456",
        # }
        return None

    def is_platform_command(self, content: str) -> bool:
        """
        检查内容是否为平台特定命令

        Slack 使用斜杠命令（如 /status）或特殊前缀

        Args:
            content: 消息内容

        Returns:
            如果是平台命令返回 True，否则返回 False
        """
        return content.startswith("/")

    def get_websocket_client(self) -> Optional[Any]:
        """
        获取 WebSocket 客户端（如果平台支持）

        Slack 支持 Socket Mode WebSocket 连接

        Returns:
            WebSocket 客户端实例，不支持返回 None
        """
        # TODO: 实现 Slack Socket Mode WebSocket 客户端
        # Socket Mode 使用 wss://wss-primary.slack.com/socket-mode/...
        return None


class SlackCardBuilder(IIMCardBuilder):
    """
    Slack 卡片构建器

    将 NormalizedCard 转换为 Slack Block Kit 格式
    """

    def create_command_card(
        self,
        command: str
    ) -> NormalizedCard:
        """创建命令确认卡片"""
        content = f"正在执行命令: {command}"
        return NormalizedCard(
            card_type="command",
            title="执行命令",
            content=content,
            template_color="grey",
        )

    def create_output_card(
        self,
        output: str,
        title: str = "Output",
        message_number: str = "",
    ) -> NormalizedCard:
        """创建输出显示卡片"""
        content = output
        if message_number:
            content = f"📨 消息编号: {message_number}\n\n{content}"
        return NormalizedCard(
            card_type="output",
            title=title,
            content=content,
            template_color="grey",
        )

    def create_error_card(
        self,
        error: str,
        message_number: str = "",
    ) -> NormalizedCard:
        """创建错误卡片"""
        content = f"❌ 错误: {error}"
        if message_number:
            content = f"📨 消息编号: {message_number}\n\n{content}"
        return NormalizedCard(
            card_type="error",
            title="错误",
            content=content,
            template_color="red",
        )

    @staticmethod
    def normalized_to_blocks(card: NormalizedCard) -> List[Dict[str, Any]]:
        """
        将 NormalizedCard 转换为 Slack Block Kit 格式

        Args:
            card: 标准化卡片

        Returns:
            Slack Block Kit blocks 列表
        """
        # TODO: 实现完整的 Block Kit 格式转换
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": card.title,
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": card.content,
                },
            },
        ]
        return blocks


def register_slack_platform():
    """
    注册 Slack 平台到工厂

    在模块导入时调用，注册 Slack 平台和卡片构建器
    """
    from src.factories.platform_factory import IMPlatformFactory

    IMPlatformFactory.register_platform(
        "slack",
        SlackPlatform,
        SlackCardBuilder,
    )

    logger.info("Slack 平台已注册到工厂")
