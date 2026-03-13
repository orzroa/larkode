"""
流式输出管理器

负责：
- 创建初始卡片
- 通过回调更新卡片内容（带节流）
- 发送最终内容
"""
import asyncio
import time
import os
from typing import Optional

from src.config.settings import get_settings
from src.feishu import FeishuAPI, CardKitClient
from src.card_dispatcher import CardDispatcher

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
except ImportError:
    import logging

try:
    logger = get_logger(__name__)
except NameError:
    logger = logging.getLogger(__name__)


class StreamingOutputManager:
    """流式输出管理器"""

    def __init__(
        self,
        user_id: str,
        feishu_api: FeishuAPI,
        card_dispatcher: Optional[CardDispatcher] = None,
    ):
        """
        初始化流式输出管理器

        Args:
            user_id: 用户 ID
            feishu_api: FeishuAPI 实例
            card_dispatcher: CardDispatcher 实例
        """
        self.user_id = user_id
        self.feishu_api = feishu_api
        self.card_dispatcher = card_dispatcher

        # 配置
        settings = get_settings()
        self.throttle = float(os.getenv(
            "STREAMING_THROTTLE_INTERVAL",
            str(settings.STREAMING_THROTTLE_INTERVAL)
        ))

        # 状态
        self._card_id: Optional[str] = None
        self._message_id: Optional[str] = None
        self._card_json_template: str = ""
        self._sequence: int = 0
        self._last_update: float = 0
        self._content_buffer: str = ""
        self._is_started: bool = False
        self._is_closed: bool = False
        self._is_stopped: bool = False  # 是否已停止更新

    async def start(self, title: str = "AI 响应中...", template_color: str = "blue") -> bool:
        """
        创建初始卡片

        Args:
            title: 卡片标题
            template_color: 卡片颜色

        Returns:
            bool: 是否创建成功
        """
        try:
            # 检查是否启用流式输出
            settings = get_settings()
            streaming_enabled = os.getenv("STREAMING_ENABLED", str(settings.STREAMING_ENABLED)).lower() == "true"

            if not streaming_enabled:
                logger.info("流式输出未启用")
                return False

            # 构建初始卡片 JSON
            self._card_json_template = _build_cardkit_card_json(title, "⌨️ AI 正在输入...", template_color)

            # 尝试创建 CardKit 卡片
            try:
                card_kit_client = CardKitClient(
                    feishu_api=self.feishu_api,
                    default_throttle=self.throttle
                )

                result = await card_kit_client.create_card_entity(
                    card_json=self._card_json_template,
                    user_id=self.user_id,
                    title=title,
                    template_color=template_color
                )

                if result:
                    self._card_id, self._message_id = result
                    self._is_started = True
                    logger.info(f"流式卡片已创建")
                    return True
                else:
                    logger.warning("CardKit 创建失败，将使用普通模式")
                    return False

            except Exception as cardkit_err:
                logger.warning(f"CardKit API 不可用: {cardkit_err}，将使用普通模式")
                return False

        except Exception as e:
            logger.error(f"创建流式卡片失败: {e}")
            return False

    async def on_chunk(self, content: str, is_last: bool = False) -> bool:
        """
        处理内容块

        更新流式卡片内容。

        Args:
            content: 新内容
            is_last: 是否是最后一块

        Returns:
            bool: 是否更新成功
        """
        if self._is_closed or self._is_stopped:
            return False

        # 如果没有创建卡片，跳过
        if not self._card_id:
            return False

        try:
            # 跳过空内容，避免将空白推送到卡片
            if not content or not content.strip():
                return True

            # 抓全量模式：直接使用传入的内容，不累积
            if is_last:
                self._content_buffer = content
            else:
                # 每次都用最新的全量内容
                self._content_buffer = content

            self._sequence += 1

            now = time.time()

            # 节流控制 - 跳过太频繁的更新
            if not is_last and (now - self._last_update) < self.throttle:
                return True

            # 构建卡片（使用累积内容）
            title = "AI 响应" if is_last else f"AI 响应 ({self._sequence})"
            card_json = _build_cardkit_card_json(title, self._content_buffer, "blue")

            # 先更新卡片实体
            success = await self.feishu_api.update_cardkit_card(
                self._card_id, card_json, self._sequence
            )

            if success:
                # 关键：更新后需要 patch 已有消息，用户才能看到更新
                if self._message_id:
                    patch_success = await self.feishu_api.patch_card_message(
                        self._message_id, card_json
                    )
                    logger.info(f"seq {self._sequence} ok")
                    if not patch_success:
                        logger.warning(f"seq {self._sequence} patch fail")
                else:
                    logger.warning(f"流式卡片更新成功但没有 message_id: sequence={self._sequence}")
            else:
                logger.warning(f"流式卡片更新失败: sequence={self._sequence}")

            self._last_update = now
            return True

        except Exception as e:
            logger.error(f"更新流式卡片失败: {e}")
            return True  # 返回 True 避免中断处理

    def _build_card_json(self, content: str) -> str:
        """构建卡片 JSON"""
        import json

        try:
            card_data = json.loads(self._card_json_template)

            # 更新内容 - 支持 body.elements 或直接 elements
            if "body" in card_data and "elements" in card_data["body"]:
                for element in card_data["body"]["elements"]:
                    if element.get("tag") == "markdown" and "content" in element:
                        element["content"] = content
                        break
            elif "elements" in card_data:
                for element in card_data["elements"]:
                    if element.get("tag") == "markdown" and "content" in element:
                        element["content"] = content
                        break

            return json.dumps(card_data, ensure_ascii=False)
        except Exception as e:
            logger.error(f"构建卡片 JSON 失败: {e}")
            return self._card_json_template

    async def close(self) -> None:
        """关闭管理器"""
        self._is_closed = True

    async def stop_with_message(self, message: str) -> None:
        """停止更新并追加提示消息

        Args:
            message: 要追加的提示消息（支持 Markdown 粗体）
        """
        if self._is_closed or self._is_stopped:
            return

        self._is_stopped = True

        try:
            # 在当前内容末尾追加提示
            if self._content_buffer:
                new_content = self._content_buffer + "\n\n" + message
            else:
                new_content = message

            self._sequence += 1
            card_json = _build_cardkit_card_json("AI 响应", new_content, "blue")

            # 更新卡片实体
            success = await self.feishu_api.update_cardkit_card(
                self._card_id, card_json, self._sequence
            )

            if success and self._message_id:
                await self.feishu_api.patch_card_message(self._message_id, card_json)
                logger.info(f"已停止更新，追加提示: seq={self._sequence}")

        except Exception as e:
            logger.error(f"停止更新失败: {e}")

        self._is_closed = True


def _build_cardkit_card_json(title: str, content: str, template_color: str = "blue") -> str:
    """
    构建 CardKit 卡片 JSON

    Args:
        title: 卡片标题
        content: 卡片内容
        template_color: 卡片颜色

    Returns:
        str: 卡片 JSON 字符串
    """
    import json

    # 颜色映射
    color_map = {
        "green": "#00A86B",
        "blue": "#1989FA",
        "orange": "#FF7D00",
        "grey": "#909399",
        "red": "#F56C6C"
    }
    color = color_map.get(template_color, "#1989FA")

    # 飞书 interactive 消息卡片格式（需要 schema: "2.0"）
    card = {
        "schema": "2.0",
        "config": {
            "wide_screen_mode": True
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": title
            },
            "template": template_color
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

    return json.dumps(card, ensure_ascii=False)
