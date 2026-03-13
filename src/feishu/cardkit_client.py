"""
飞书 CardKit 客户端

提供卡片实体创建、更新功能，支持流式输出场景
"""
import asyncio
import json
import time
from typing import Optional, Callable, Dict
from pathlib import Path

from src.config.settings import get_settings

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class CardKitClient:
    """飞书 CardKit 客户端 - 支持流式卡片更新"""

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret
        self._client = None
        # 卡片序号管理：card_id -> sequence
        self._card_sequence: Dict[str, int] = {}
        # 卡片元数据：card_id -> {title, template_color}
        self._card_metadata: Dict[str, Dict] = {}
        # 并发锁：确保 sequence 的原子递增
        self._lock = asyncio.Lock()

    def _get_client(self):
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

    def _get_next_sequence(self, card_id: str) -> int:
        """获取并递增卡片操作序号（必须严格递增）"""
        seq = self._card_sequence.get(card_id, 0) + 1
        self._card_sequence[card_id] = seq
        return seq

    async def create_card_entity(
        self,
        content: str,
        title: str = "AI 助手",
        template_color: str = "grey"
    ) -> Optional[str]:
        """
        创建卡片实体，返回 card_id

        Args:
            content: 卡片内容
            title: 卡片标题
            template_color: 模板颜色

        Returns:
            card_id，创建失败返回 None
        """
        try:
            import lark_oapi as lark

            client = self._get_client()

            card_data = {
                "schema": "2.0",
                "config": {"update_multi": True},  # 共享卡片，所有人可见更新
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": template_color
                },
                "body": {
                    "elements": [{"tag": "markdown", "content": content}]
                }
            }

            request = lark.api.cardkit.v1.CreateCardRequest.builder() \
                .request_body(
                    lark.api.cardkit.v1.CreateCardRequestBody.builder()
                    .type("card_json")
                    .data(json.dumps(card_data))
                    .build()
                ).build()

            # 在异步环境中执行同步调用（使用 asyncio.to_thread 更安全）
            response = await asyncio.to_thread(client.cardkit.v1.card.create, request)

            if response.success() and response.data:
                card_id = response.data.card_id

                # 保存卡片元数据（标题和颜色）
                self._card_metadata[card_id] = {
                    "title": title,
                    "template_color": template_color
                }

                # 获取初始 sequence（如果响应中包含）
                initial_seq = getattr(response.data, 'sequence', None)
                if initial_seq is not None:
                    self._card_sequence[card_id] = initial_seq
                    logger.info(f"成功创建卡片实体: {card_id}, 初始 sequence: {initial_seq}")
                else:
                    # 如果没有返回，初始化为 0
                    self._card_sequence[card_id] = 0
                    logger.info(f"成功创建卡片实体: {card_id}")

                # 获取 share_id（用于发送消息）
                share_id = getattr(response.data, 'share_id', None)
                if share_id:
                    logger.info(f"卡片 share_id: {share_id}")

                # 打印完整响应以便调试
                logger.info(f"创建卡片响应: code={response.code}, msg={response.msg}, card_id={card_id}")
                logger.debug(f"完整响应对象: {dir(response.data)}")

                return card_id

            logger.error(f"创建卡片失败: {response.code} - {response.msg}")
            return None

        except Exception as e:
            logger.error(f"创建卡片实体时出错: {e}", exc_info=True)
            return None

    async def send_card_to_user(
        self,
        card_id: str,
        user_id: str,
        receive_id_type: str = "open_id"
    ) -> bool:
        """
        发送卡片消息给用户

        CardKit创建的卡片实体，通过消息API发送卡片ID引用

        Args:
            card_id: 卡片ID
            user_id: 用户ID
            receive_id_type: 接收者ID类型

        Returns:
            发送成功返回 True
        """
        try:
            import lark_oapi as lark

            client = self._get_client()

            # 正确的发送方式：消息content引用card_id
            # 根据飞书文档：https://open.feishu.cn/document/cardkit-v1/streaming-updates-openapi-overview
            content = json.dumps({
                "type": "card",
                "data": {
                    "card_id": card_id
                }
            })

            request = lark.api.im.v1.CreateMessageRequest.builder() \
                .receive_id_type(receive_id_type) \
                .request_body(
                    lark.api.im.v1.CreateMessageRequestBody.builder()
                    .receive_id(user_id)
                    .msg_type("interactive")
                    .content(content)
                    .build()
                ).build()

            # 在异步环境中执行同步调用（使用 asyncio.to_thread 更安全）
            response = await asyncio.to_thread(client.im.v1.message.create, request)

            if response.success():
                logger.info(f"✅ 成功发送卡片消息给用户 {user_id}, card_id={card_id}")
                return True

            logger.error(f"❌ 发送卡片消息失败: {response.code} - {response.msg}")
            return False

        except Exception as e:
            logger.error(f"发送卡片消息时出错: {e}", exc_info=True)
            return False

    async def update_card_content(
        self,
        card_id: str,
        content: str,
        cancelled_cards: Optional[set] = None,
        title: Optional[str] = None
    ) -> bool:
        """
        更新卡片内容

        Args:
            card_id: 卡片ID
            content: 新内容
            cancelled_cards: 已取消的卡片集合（可选）
            title: 动态标题（可选），如不提供则使用元数据中的标题

        Returns:
            更新成功返回 True，失败返回 False
        """
        # 检查卡片是否已被取消
        if cancelled_cards and card_id in cancelled_cards:
            logger.info(f"卡片 {card_id} 已被取消，跳过更新")
            return False

        try:
            import lark_oapi as lark

            client = self._get_client()

            # 获取卡片元数据（标题和颜色）
            metadata = self._card_metadata.get(card_id, {})
            # 如果传入了标题则使用，否则使用元数据中的标题
            card_title = title if title is not None else metadata.get("title", "AI 助手")
            template_color = metadata.get("template_color", "grey")

            card_data = {
                "schema": "2.0",
                "config": {"update_multi": True},
                "header": {
                    "title": {"tag": "plain_text", "content": card_title},
                    "template": template_color
                },
                "body": {
                    "elements": [{"tag": "markdown", "content": content}]
                }
            }

            # 使用锁确保 sequence 的原子递增和请求发送
            async with self._lock:
                # 获取并立即递增 sequence（原子操作）
                next_seq = self._card_sequence.get(card_id, 0) + 1
                self._card_sequence[card_id] = next_seq

                # 注意：card 参数需要 Card 对象，不是字符串
                card_obj = lark.api.cardkit.v1.Card.builder() \
                    .type("card_json") \
                    .data(json.dumps(card_data)) \
                    .build()

                request = lark.api.cardkit.v1.UpdateCardRequest.builder() \
                    .card_id(card_id) \
                    .request_body(
                        lark.api.cardkit.v1.UpdateCardRequestBody.builder()
                        .card(card_obj)
                        .sequence(next_seq)  # 必须严格递增
                        .build()
                    ).build()

                # 在异步环境中执行同步调用（使用 asyncio.to_thread 更安全）
                # 锁保护整个更新过程，避免并发竞争
                response = await asyncio.to_thread(client.cardkit.v1.card.update, request)

                if response.success():
                    logger.info(f"✅ 成功更新卡片 {card_id} (seq={next_seq})")
                    return True

                # 失败时回滚 sequence（保持一致性）
                # 只有当前 sequence 还是我们设置的值时才回滚
                if self._card_sequence.get(card_id) == next_seq:
                    self._card_sequence[card_id] = next_seq - 1

                logger.warning(f"❌ 更新卡片失败: {response.code} - {response.msg}; card_id={card_id}, seq={next_seq}")
                return False

        except Exception as e:
            logger.error(f"更新卡片内容时出错: {e}", exc_info=True)
            return False


class StreamingCardUpdater:
    """
    流式卡片更新器 - 带节流功能

    管理 AI Agent 流式输出时的卡片更新
    """

    # 节流间隔（秒）- 控制更新频率
    UPDATE_THROTTLE_INTERVAL = 0.5

    def __init__(self, cardkit_client: CardKitClient):
        self.cardkit = cardkit_client
        self._state: Dict[str, Dict] = {}

    def make_throttled_callback(
        self,
        card_id: str,
        do_update: Callable[[str], None],
        interval: float = UPDATE_THROTTLE_INTERVAL
    ) -> Callable[[str, bool], None]:
        """
        创建带节流的回调函数

        Args:
            card_id: 卡片ID
            do_update: 执行更新的函数
            interval: 节流间隔（秒）

        Returns:
            节流回调函数
        """
        state_key = card_id
        self._state[state_key] = {
            "last_update_time": 0.0,
            "last_content": ""
        }

        def on_chunk(accumulated: str, is_last: bool) -> None:
            state = self._state[state_key]
            state["last_content"] = accumulated or "正在处理..."
            now = time.time()

            # 节流逻辑：间隔足够 或 最后一次
            if is_last or (now - state["last_update_time"]) >= interval:
                do_update(state["last_content"])
                state["last_update_time"] = now

        return on_chunk

    def cleanup(self, card_id: str):
        """清理卡片相关状态"""
        if card_id in self._state:
            del self._state[card_id]
        if card_id in self.cardkit._card_sequence:
            del self.cardkit._card_sequence[card_id]
        if card_id in self.cardkit._card_metadata:
            del self.cardkit._card_metadata[card_id]