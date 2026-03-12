"""
飞书 API 客户端：消息、用户操作
"""
from typing import Optional, Dict, Any

from src.config.settings import get_settings
from src.feishu.exceptions import FeishuAPISendError

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class FeishuAPI:
    """飞书 API 客户端"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self.access_token: Optional[str] = None
        self._client: Optional[Any] = None

    def _get_client(self) -> Any:
        """获取飞书客户端实例（复用）"""
        if self._client is not None:
            return self._client

        import lark_oapi as lark
        self._client = lark.Client.builder() \
            .app_id(get_settings().FEISHU_APP_ID) \
            .app_secret(self.app_secret) \
            .domain(getattr(lark, get_settings().FEISHU_MESSAGE_DOMAIN)) \
            .log_level(lark.LogLevel.DEBUG) \
            .build()
        return self._client

    async def send_message(self, user_id: str, message: str):
        """发送消息给用户

        Returns:
            str: 发送成功返回消息ID，失败返回空字符串
        """
        logger.info(f"FeishuAPI.send_message 被调用: user_id={user_id}")
        try:
            import lark_oapi as lark
            client = self._get_client()

            logger.info("lark.Client 获取完成")

            # 构建消息请求
            # message 可以是 dict、JSON 字符串、或普通文本
            import json
            if isinstance(message, dict):
                # dict 序列化为 JSON 字符串
                message = json.dumps(message, ensure_ascii=False)
            elif isinstance(message, str):
                # 尝试解析为 dict 再序列化，确保格式一致
                try:
                    parsed = json.loads(message)
                    message = json.dumps(parsed, ensure_ascii=False)
                except json.JSONDecodeError:
                    # 不是 JSON，保持为字符串（用于 text 类型）
                    pass
            request = lark.api.im.v1.CreateMessageRequest.builder() \
                .receive_id_type(get_settings().FEISHU_MESSAGE_RECEIVE_ID_TYPE) \
                .request_body(
                    lark.api.im.v1.CreateMessageRequestBody.builder()
                    .msg_type("interactive")
                    .receive_id(user_id)
                    .content(message)
                    .build()
                ) \
                .build()

            logger.info(f"构建消息请求完成，准备发送")

            # 发送消息（同步方法，需要在异步环境中包装）
            import asyncio
            loop = asyncio.get_running_loop()
            logger.info(f"获取 event loop: {loop}")

            logger.info("准备调用 loop.run_in_executor")
            response = await loop.run_in_executor(None, client.im.v1.message.create, request)

            logger.info(f"收到飞书 API 响应: success={response.success()}")

            if response.success():
                # 获取消息ID
                message_id = response.data.message_id if response.data else ""
                logger.info(f"成功发送消息给用户 {user_id}, message_id={message_id}")
                return message_id
            else:
                logger.error(f"发送消息失败: {response.code} - {response.msg}, log_id: {response.get_log_id()}")
                raise FeishuAPISendError("feishu", f"发送消息失败: {response.code} - {response.msg}")

        except FeishuAPISendError:
            raise
        except Exception as e:
            logger.error(f"发送消息时出错: {e}", exc_info=True)
            raise FeishuAPISendError("feishu", f"发送消息时出错: {e}")

    async def send_interactive_message(self, user_id: str, card_json: str, message_number: str = "") -> str:
        """
        发送交互式卡片消息

        Args:
            user_id: 用户 ID
            card_json: 卡片 JSON 字符串
            message_number: 消息编号

        Returns:
            str: 发送成功返回消息ID，失败返回空字符串
        """
        return await self.send_message(user_id, card_json)

    async def get_user_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        获取用户信息

        Args:
            user_id: 用户 ID (open_id)

        Returns:
            用户信息字典，失败返回 None
        """
        try:
            import lark_oapi as lark

            client = lark.Client.builder() \
                .app_id(get_settings().FEISHU_APP_ID) \
                .app_secret(self.app_secret) \
                .domain(getattr(lark, get_settings().FEISHU_MESSAGE_DOMAIN)) \
                .log_level(lark.LogLevel.WARNING) \
                .build()

            request = lark.api.contact.v3.GetUserRequest.builder() \
                .user_id(user_id) \
                .user_id_type("open_id") \
                .build()

            response = client.contact.v3.user.get(request)

            if response.success() and response.data:
                return {
                    "user_id": user_id,
                    "name": response.data.name or "",
                    "avatar": response.data.avatar_72x72 or ""
                }

            return None

        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            return None

    async def get_message(self, msg_id: str) -> Optional[Dict[str, Any]]:
        """
        根据消息 ID 获取消息详情

        Args:
            msg_id: 消息 ID

        Returns:
            消息详情字典，失败返回 None
        """
        try:
            import lark_oapi as lark

            client = self._get_client()

            request = lark.api.im.v1.GetMessageRequest.builder() \
                .message_id(msg_id) \
                .build()

            response = await asyncio.get_event_loop().run_in_executor(
                None, client.im.v1.message.get, request
            )

            if response.success() and response.data:
                return {
                    "message_id": msg_id,
                    "msg_type": response.data.msg_type,
                    "content": response.data.body,
                }

            logger.warning(f"获取消息失败: {response.code} - {response.msg}")
            return None

        except Exception as e:
            logger.error(f"获取消息详情失败: {e}")
            return None
