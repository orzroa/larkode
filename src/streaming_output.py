"""
流式输出管理器

管理 AI 助手流式输出时的卡片创建和实时更新
"""
import asyncio
import os
import time
from typing import Optional, Dict
from pathlib import Path

from src.config.settings import get_settings
from src.feishu.cardkit_client import CardKitClient

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)


class StreamingOutputManager:
    """
    流式输出管理器

    负责：
    1. 创建可更新的卡片实体
    2. 管理流式输出生命周期
    3. 协调卡片更新（带节流）
    4. 处理错误和降级策略

    全局只保持一张流式卡片，新卡片会结束旧卡片
    """

    # 节流间隔（秒）
    UPDATE_THROTTLE_INTERVAL = 0.5

    # 单例实例
    _instance: Optional['StreamingOutputManager'] = None

    def __new__(cls, cardkit_client: CardKitClient):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.cardkit = cardkit_client
            cls._instance._update_states = {}
            cls._instance._active_card_id = None
            cls._instance._cancelled_cards = set()  # 跟踪已被取消的卡片
            cls._instance._active_monitor_task = None  # 当前活跃的监控任务
            # 从配置读取更新间隔
            cls._instance._update_interval = get_settings().STREAMING_UPDATE_INTERVAL
        return cls._instance

    def __init__(self, cardkit_client: CardKitClient):
        """
        初始化流式输出管理器

        Args:
            cardkit_client: CardKit 客户端实例
        """
        # 单例模式下，__init__ 会被多次调用，但实例只创建一次
        # 所以这里不需要重复初始化
        pass

    async def start_streaming(
        self,
        user_id: str,
        initial_message: str = "正在处理...",
        title: str = "AI 助手",
        template_color: str = "blue"
    ) -> Optional[str]:
        """
        开始流式输出，创建卡片实体

        Args:
            user_id: 用户 ID
            initial_message: 初始消息内容
            title: 卡片标题
            template_color: 卡片颜色

        Returns:
            card_id，失败返回 None
        """
        try:
            # 如果有旧的流式卡片，先结束它
            logger.debug(f"检查旧卡片: _active_card_id={self._active_card_id}, _update_states keys={list(self._update_states.keys())}")

            # 1. 取消旧的监控任务
            if self._active_monitor_task and not self._active_monitor_task.done():
                logger.info(f"取消旧的监控任务")
                self._active_monitor_task.cancel()
                try:
                    await self._active_monitor_task
                except asyncio.CancelledError:
                    logger.info(f"旧监控任务已取消")

            # 2. 结束旧的流式卡片
            if self._active_card_id and self._active_card_id in self._update_states:
                old_card_id = self._active_card_id
                old_content = self._update_states[old_card_id].get("last_content", "")

                # 在旧卡片最后添加提示
                final_old_content = old_content + "\n\n---\n\n📢 **新的流式卡片已创建**"

                logger.info(f"结束旧的流式卡片: {old_card_id}, 内容长度: {len(old_content)}")

                # 结束旧卡片（等待更新完成）
                try:
                    success = await self.cardkit.update_card_content(
                        old_card_id,
                        final_old_content,
                        cancelled_cards=None  # 允许更新提示消息
                    )
                    if success:
                        logger.info(f"✅ 旧卡片已标记为新卡片替代: {old_card_id}")
                except Exception as e:
                    logger.error(f"更新旧卡片失败: {e}")

                # 清理旧卡片状态
                self.cleanup(old_card_id)
            else:
                logger.debug(f"没有需要结束的旧卡片")

            # 创建卡片实体
            card_id = await self.cardkit.create_card_entity(
                content=initial_message,
                title=title,
                template_color=template_color
            )

            if card_id:
                # 发送卡片消息给用户
                send_success = await self.cardkit.send_card_to_user(
                    card_id=card_id,
                    user_id=user_id
                )

                if send_success:
                    # 初始化更新状态
                    self._update_states[card_id] = {
                        "last_update_time": 0.0,
                        "last_content": initial_message,
                        "user_id": user_id,
                        "start_time": time.time(),  # 记录开始时间
                        "title": title,  # 保存标题
                    }

                    # 设置为当前活跃卡片
                    self._active_card_id = card_id

                    logger.info(f"开始流式输出: card_id={card_id}, user_id={user_id}")
                    return card_id
                else:
                    logger.error(f"发送卡片消息失败，card_id={card_id}")
                    return None
            else:
                logger.warning("创建卡片实体失败，将降级到传统模式")
                return None

        except Exception as e:
            logger.error(f"启动流式输出失败: {e}", exc_info=True)
            return None

    async def update_content(self, card_id: str, content: str) -> bool:
        """
        更新卡片内容（带节流）

        Args:
            card_id: 卡片 ID
            content: 新内容

        Returns:
            更新成功返回 True
        """
        # 检查卡片是否已被取消
        if card_id in self._cancelled_cards:
            logger.info(f"卡片 {card_id} 已被取消，跳过更新")
            return False

        if card_id not in self._update_states:
            # 旧卡片的监控任务仍在运行，已被新卡片替代，静默失败
            logger.info(f"卡片 {card_id} 已被替代，跳过更新")
            return False

        try:
            state = self._update_states[card_id]
            state["last_content"] = content

            now = time.time()

            # 节流逻辑：距离上次更新时间足够
            if (now - state["last_update_time"]) >= self._update_interval:
                # 计算已用时间
                elapsed = now - state.get("start_time", now)
                title = f"命令处理({int(elapsed)})"

                success = await self.cardkit.update_card_content(
                    card_id,
                    content,
                    cancelled_cards=self._cancelled_cards,
                    title=title  # 传入动态标题
                )
                if success:
                    state["last_update_time"] = now
                    logger.debug(f"卡片内容已更新: {card_id}")
                return success
            else:
                # 节流中，跳过更新
                logger.debug(f"节流中，跳过更新: {card_id}")
                return True

        except Exception as e:
            logger.error(f"更新卡片内容失败: {e}", exc_info=True)
            return False

    async def finish_streaming(self, card_id: str, final_content: str) -> bool:
        """
        完成流式输出，发送最终内容

        Args:
            card_id: 卡片 ID
            final_content: 最终内容

        Returns:
            成功返回 True
        """
        # 检查卡片是否已被取消
        if card_id in self._cancelled_cards:
            logger.info(f"卡片 {card_id} 已被取消，跳过完成")
            return False

        if card_id not in self._update_states:
            # 旧卡片的监控任务仍在运行，已被新卡片替代，静默失败
            logger.info(f"卡片 {card_id} 已被替代，跳过完成")
            return False

        try:
            # 计算总耗时
            state = self._update_states.get(card_id, {})
            elapsed = time.time() - state.get("start_time", time.time())
            title = f"命令处理(完成，耗时{int(elapsed)}秒)"

            # 强制更新最终内容（不节流）
            success = await self.cardkit.update_card_content(
                card_id,
                final_content,
                cancelled_cards=self._cancelled_cards,
                title=title  # 传入完成标题
            )

            # 清理状态
            if success:
                logger.info(f"流式输出完成: {card_id}")
                self.cleanup(card_id)
            else:
                logger.warning(f"更新最终内容失败: {card_id}")

            return success

        except Exception as e:
            logger.error(f"完成流式输出失败: {e}", exc_info=True)
            return False

    async def handle_error(self, card_id: str, error_message: str) -> bool:
        """
        处理错误，更新卡片显示错误信息

        Args:
            card_id: 卡片 ID
            error_message: 错误消息

        Returns:
            成功返回 True
        """
        if card_id not in self._update_states:
            # 旧卡片的监控任务仍在运行，已被新卡片替代，静默失败
            logger.debug(f"卡片 {card_id} 已被替代，跳过错误处理")
            return False

        try:
            error_content = f"❌ **错误**\n\n{error_message}"
            success = await self.cardkit.update_card_content(card_id, error_content)

            if success:
                logger.info(f"错误信息已更新到卡片: {card_id}")
                self.cleanup(card_id)

            return success

        except Exception as e:
            logger.error(f"更新错误信息失败: {e}", exc_info=True)
            return False

    def cleanup(self, card_id: str):
        """
        清理卡片相关资源

        Args:
            card_id: 卡片 ID
        """
        # 将卡片标记为已取消（防止后续更新）
        self._cancelled_cards.add(card_id)

        if card_id in self._update_states:
            del self._update_states[card_id]
            logger.debug(f"清理卡片状态: {card_id}")

        # 清理 CardKitClient 中的 sequence
        if card_id in self.cardkit._card_sequence:
            del self.cardkit._card_sequence[card_id]

        # 清理 CardKitClient 中的元数据
        if card_id in self.cardkit._card_metadata:
            del self.cardkit._card_metadata[card_id]

        # 如果是当前活跃卡片，重置活跃卡片 ID
        if self._active_card_id == card_id:
            self._active_card_id = None

        # 延迟清理 cancelled_cards（给监控任务时间停止）
        # 5秒后自动移除（避免内存泄漏）
        asyncio.create_task(self._delayed_cancel_cleanup(card_id, delay=5.0))

    async def _delayed_cancel_cleanup(self, card_id: str, delay: float = 5.0):
        """延迟清理取消标记，给监控任务时间停止"""
        await asyncio.sleep(delay)
        if card_id in self._cancelled_cards:
            self._cancelled_cards.discard(card_id)
            logger.debug(f"延迟清理取消标记: {card_id}")

    def register_monitor_task(self, task: asyncio.Task):
        """
        注册当前活跃的监控任务

        Args:
            task: 监控任务
        """
        self._active_monitor_task = task
        logger.debug(f"注册监控任务: {task}")

    @classmethod
    def reset_instance(cls):
        """
        重置单例实例（仅用于测试）
        """
        if cls._instance is not None:
            cls._instance._update_states.clear()
            cls._instance._cancelled_cards.clear()
            cls._instance._active_card_id = None
            cls._instance._active_monitor_task = None
            cls._instance = None

    def is_active(self, card_id: str) -> bool:
        """
        检查卡片是否处于活跃状态

        Args:
            card_id: 卡片 ID

        Returns:
            活跃返回 True
        """
        return card_id in self._update_states


def create_streaming_manager() -> Optional[StreamingOutputManager]:
    """
    创建流式输出管理器实例（单例模式）

    Returns:
        StreamingOutputManager 实例，配置不完整返回 None
    """
    try:
        settings = get_settings()

        # 检查是否启用流式输出
        if not settings.STREAMING_OUTPUT_ENABLED:
            logger.info("流式输出未启用")
            return None

        # 检查飞书配置
        if not settings.FEISHU_APP_ID or not settings.FEISHU_APP_SECRET:
            logger.warning("飞书配置不完整，无法创建流式输出管理器")
            return None

        # 如果已有单例实例，直接返回
        if StreamingOutputManager._instance is not None:
            return StreamingOutputManager._instance

        # 创建 CardKitClient
        cardkit = CardKitClient(
            app_id=settings.FEISHU_APP_ID,
            app_secret=settings.FEISHU_APP_SECRET
        )

        # 创建 StreamingOutputManager（单例）
        manager = StreamingOutputManager(cardkit)

        logger.info("流式输出管理器已创建（单例）")
        return manager

    except Exception as e:
        logger.error(f"创建流式输出管理器失败: {e}", exc_info=True)
        return None