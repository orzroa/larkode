"""
CardKit 客户端 - 卡片流式更新

职责：
- 创建卡片实体
- 流式更新卡片内容（带节流）
- 维护 card_id -> sequence 映射
"""
import asyncio
import time
from typing import Optional, Callable, Awaitable

from src.feishu.api import FeishuAPI

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class StreamingCallback:
    """流式回调处理器 - 带节流功能"""

    def __init__(
        self,
        card_id: str,
        feishu_api: FeishuAPI,
        card_json_template: str,
        sequence: int = 0,
        throttle: float = 0.5,
    ):
        """
        初始化流式回调

        Args:
            card_id: 卡片 ID
            feishu_api: FeishuAPI 实例
            card_json_template: 卡片 JSON 模板
            sequence: 初始序列号
            throttle: 节流间隔（秒）
        """
        self.card_id = card_id
        self.feishu_api = feishu_api
        self.card_json_template = card_json_template
        self.sequence = sequence
        self.throttle = throttle
        self.last_update = 0.0
        self._closed = False

    async def on_chunk(self, content: str, is_last: bool = False) -> bool:
        """
        处理流式内容块

        Args:
            content: 新内容
            is_last: 是否是最后一块

        Returns:
            bool: 是否更新成功
        """
        if self._closed:
            return False

        now = time.time()
        self.sequence += 1

        # 节流控制：非最后一块时，只有超过节流间隔才更新
        if not is_last and (now - self.last_update) < self.throttle:
            return True  # 跳过本次更新

        # 构建更新后的卡片 JSON
        updated_card_json = self._build_card_json(content)

        # 调用 API 更新卡片
        success = await self.feishu_api.update_cardkit_card(
            self.card_id, updated_card_json, self.sequence
        )

        if success:
            self.last_update = now

        return success

    def _build_card_json(self, content: str) -> str:
        """构建卡片 JSON"""
        import json

        # 从模板复制并更新 content
        try:
            card_data = json.loads(self.card_json_template)
            # 找到 content 元素并更新
            if "elements" in card_data:
                for element in card_data["elements"]:
                    if element.get("tag") == "markdown" and "content" in element:
                        element["content"] = content
                        break
            return json.dumps(card_data, ensure_ascii=False)
        except Exception as e:
            logger.error(f"构建卡片 JSON 失败: {e}")
            return self.card_json_template

    async def close(self) -> None:
        """关闭回调"""
        self._closed = True


class CardKitClient:
    """CardKit 客户端 - 管理卡片实体的创建和更新"""

    def __init__(self, feishu_api: FeishuAPI, default_throttle: float = 0.5):
        """
        初始化 CardKitClient

        Args:
            feishu_api: FeishuAPI 实例
            default_throttle: 默认节流间隔（秒）
        """
        self.feishu_api = feishu_api
        self.default_throttle = default_throttle
        self._active_callbacks: dict[str, StreamingCallback] = {}

    async def create_card_entity(
        self,
        card_json: str,
        user_id: str,
        title: str = "消息",
        template_color: str = "blue",
    ) -> Optional[tuple[str, str]]:
        """
        创建卡片实体并发送初始消息

        Args:
            card_json: 卡片 JSON 字符串
            user_id: 用户 ID
            title: 卡片标题
            template_color: 卡片颜色

        Returns:
            tuple[str, str]: (card_id, message_id) 或 None
        """
        try:
            # 创建卡片实体
            card_id = await self.feishu_api.create_cardkit_card(card_json)

            if not card_id:
                logger.error("创建卡片实体失败")
                return None

            # 发送卡片消息（使用完整 card_json）
            message_id = await self.feishu_api.send_cardkit_message(user_id, None, card_json)

            if not message_id:
                logger.error("发送卡片消息失败")
                return None

            logger.info(f"创建卡片实体成功: card_id={card_id}, message_id={message_id}")
            return card_id, message_id

        except Exception as e:
            logger.error(f"创建卡片实体失败: {e}")
            return None

    async def create_streaming_callback(
        self,
        card_id: str,
        card_json_template: str,
        throttle: Optional[float] = None,
    ) -> StreamingCallback:
        """
        创建流式回调处理器

        Args:
            card_id: 卡片 ID
            card_json_template: 卡片 JSON 模板
            throttle: 节流间隔（可选）

        Returns:
            StreamingCallback: 流式回调处理器
        """
        callback = StreamingCallback(
            card_id=card_id,
            feishu_api=self.feishu_api,
            card_json_template=card_json_template,
            sequence=0,
            throttle=throttle or self.default_throttle,
        )
        self._active_callbacks[card_id] = callback
        return callback

    async def remove_callback(self, card_id: str) -> None:
        """移除回调处理器"""
        if card_id in self._active_callbacks:
            await self._active_callbacks[card_id].close()
            del self._active_callbacks[card_id]

    async def close_all(self) -> None:
        """关闭所有回调"""
        for callback in self._active_callbacks.values():
            await callback.close()
        self._active_callbacks.clear()


# 全局实例
_card_kit_client: Optional[CardKitClient] = None


def get_card_kit_client() -> Optional[CardKitClient]:
    """获取全局 CardKitClient 实例"""
    return _card_kit_client


def set_card_kit_client(client: CardKitClient) -> None:
    """设置全局 CardKitClient 实例"""
    global _card_kit_client
    _card_kit_client = client
