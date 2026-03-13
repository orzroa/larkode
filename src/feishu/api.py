"""
飞书 API 客户端：消息、用户操作
"""
import asyncio
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
            .log_level(lark.LogLevel.WARNING) \
            .build()
        return self._client

    async def send_message(self, user_id: str, message: str):
        """发送消息给用户

        Returns:
            str: 发送成功返回消息ID，失败返回空字符串
        """
        logger.info(f"FeishuAPI.send_message 被调用: user_id={user_id}, message_type=interactive")
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

            logger.info(f"发送的消息内容: {message[:200]}...")

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

    # ==================== CardKit API ====================

    async def create_cardkit_card(self, card_json: str) -> Optional[str]:
        """
        创建 CardKit 卡片实体

        Args:
            card_json: 卡片 JSON 字符串

        Returns:
            str: 卡片 ID，失败返回 None
        """
        try:
            import lark_oapi as lark
            import json

            client = self._get_client()

            # 解析卡片 JSON
            card_data = json.loads(card_json)

            # 使用 card_json 类型，data 需要是 JSON 字符串
            request_body = lark.api.cardkit.v1.CreateCardRequestBodyBuilder() \
                .type("card_json") \
                .data(json.dumps(card_data)) \
                .build()

            request = lark.api.cardkit.v1.CreateCardRequest.builder() \
                .request_body(request_body) \
                .build()

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, client.cardkit.v1.card.create, request)

            # 调试：打印响应
            logger.info(f"CardKit create response: {response}")
            if hasattr(response, 'data'):
                logger.info(f"Response data: {response.data}")
                if response.data:
                    logger.info(f"Response data card_id: {response.data.card_id}")

            # 检查响应
            if hasattr(response, 'data') and response.data and response.data.card_id:
                card_id = response.data.card_id
                logger.info(f"成功创建 CardKit 卡片: {card_id}")
                return card_id
            else:
                # 尝试其他属性访问方式
                if hasattr(response, 'msg'):
                    logger.error(f"创建 CardKit 卡片失败: {response.msg}")
                else:
                    logger.error(f"创建 CardKit 卡片失败: {response}")
                return None

        except Exception as e:
            logger.error(f"创建 CardKit 卡片失败: {e}")
            return None

    async def update_cardkit_card(self, card_id: str, card_json: str, sequence: int) -> bool:
        """
        更新 CardKit 卡片实体

        Args:
            card_id: 卡片 ID
            card_json: 卡片 JSON 字符串
            sequence: 序列号（必须递增）

        Returns:
            bool: 是否成功
        """
        try:
            import lark_oapi as lark
            import json

            client = self._get_client()

            # 解析卡片 JSON
            card_data = json.loads(card_json)

            # 移除 schema 字段（更新 API 可能不需要）
            card_data.pop("schema", None)

            # 构建 card 对象 - 需要 type 和 data 字段
            card_obj = {
                "type": "card_json",
                "data": json.dumps(card_data, ensure_ascii=False)
            }

            # 构建更新请求
            request_body = lark.api.cardkit.v1.UpdateCardRequestBodyBuilder() \
                .card(card_obj) \
                .sequence(sequence) \
                .build()

            request = lark.api.cardkit.v1.UpdateCardRequest.builder() \
                .card_id(card_id) \
                .request_body(request_body) \
                .build()

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, client.cardkit.v1.card.update, request)

            # 检查响应 - 飞书 API 返回 code=0 表示成功
            if hasattr(response, 'code') and response.code == 0:
                return True
            elif hasattr(response, 'success') and response.success():
                return True
            else:
                logger.error(f"更新 CardKit 失败: {response.code if hasattr(response, 'code') else 'N/A'}")
                return False

        except Exception as e:
            logger.error(f"更新 CardKit 失败: {e}")
            return False

    async def patch_card_message(self, message_id: str, card_json: str) -> bool:
        """
        更新已发送的卡片消息

        Args:
            message_id: 消息 ID
            card_json: 新的卡片 JSON

        Returns:
            bool: 是否成功
        """
        try:
            import json
            import lark_oapi as lark
            client = self._get_client()

            request = lark.api.im.v1.PatchMessageRequest.builder() \
                .message_id(message_id) \
                .request_body(
                    lark.api.im.v1.PatchMessageRequestBody.builder()
                    .content(card_json)
                    .build()
                ) \
                .build()

            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, client.im.v1.message.patch, request)

            if hasattr(response, 'code') and response.code == 0:
                return True
            else:
                logger.error(f"patch 消息失败: {response.code if hasattr(response, 'code') else 'N/A'}")
                return False

        except Exception as e:
            logger.error(f"patch 消息失败: {e}")
            return False

    async def send_cardkit_message(self, user_id: str, card_id: str = None, card_json: str = None) -> Optional[str]:
        """
        发送 CardKit 卡片消息

        Args:
            user_id: 用户 ID
            card_id: 卡片 ID（可选，已废弃）
            card_json: 完整的卡片 JSON（可选）

        Returns:
            str: 消息 ID，失败返回 None
        """
        try:
            import json

            # 直接发送完整的卡片 JSON
            if not card_json:
                logger.error("需要提供 card_json")
                return None

            # 发送完整的卡片 JSON（用于 interactive 消息类型）
            # SDK 会自动处理 JSON 序列化
            result = await self.send_message(user_id, card_json)
            return result

        except Exception as e:
            logger.error(f"发送 CardKit 消息失败: {e}")
            return None
