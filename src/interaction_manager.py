"""
交互管理器 - 处理卡片交互事件
"""
import asyncio
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# 优先使用新的日志工具，失败则回退到标准 logging
try:
    from src.logging_utils import get_logger
    logger = get_logger(__name__)
except ImportError:
    import logging
    logger = logging.getLogger(__name__)

# 交互文件路径（需要从 Config 导入）
INTERACTION_RESPONSE_FILE = None


def set_interaction_response_file_path(path: Path):
    """设置交互响应文件路径"""
    global INTERACTION_RESPONSE_FILE
    INTERACTION_RESPONSE_FILE = path


class InteractionManager:
    """交互管理器，处理用户与卡片的交互"""

    def __init__(self):
        # 存储等待交互的任务 {task_id: task_info}
        self._pending_interactions: Dict[str, Dict[str, Any]] = {}
        # 存储交互结果 {task_id: result}
        self._interaction_results: Dict[str, Any] = {}
        self._result_events: Dict[str, asyncio.Event] = {}
        self._lock = asyncio.Lock()

    async def handle_card_interaction(
        self,
        interaction_data: Dict[str, Any],
        feishu_api
    ) -> Optional[Dict[str, Any]]:
        """
        处理卡片交互事件

        Args:
            interaction_data: 交互数据
            feishu_api: 飞书 API 实例

        Returns:
            处理结果
        """
        try:
            action_value = interaction_data.get("action_value", {})
            form_value = interaction_data.get("form_value")
            operator = interaction_data.get("operator", {})
            context = interaction_data.get("context", {})

            # 提取 operator 的 open_id
            user_open_id = operator.get("open_id") or operator.get("user_id", "")
            if not user_open_id:
                logger.warning("无法获取用户 ID")
                return None

            # 获取 message_id 和 card_id
            message_id = context.get("open_message_id", "")
            chat_id = context.get("open_chat_id", "")

            logger.info(f"用户 {user_open_id} 交互: action={action_value}, form={form_value}, msg_id={message_id}")

            # 处理不同类型的交互
            if isinstance(action_value, dict):
                # Escape 按钮
                if action_value.get("action") == "escape":
                    return await self._handle_escape(user_open_id, message_id, feishu_api)

                # Yes/No 确认
                if action_value.get("action") == "confirm":
                    value = action_value.get("value")
                    return await self._handle_confirm(user_open_id, message_id, value, feishu_api)

            # 表单提交（单选或多选）
            if form_value:
                return await self._handle_form_submit(
                    user_open_id,
                    message_id,
                    form_value,
                    feishu_api
                )

            logger.warning(f"未知的交互类型: action={action_value}, form={form_value}")
            return None

        except Exception as e:
            logger.error(f"处理卡片交互时出错: {e}", exc_info=True)
            return None

    async def _handle_escape(
        self,
        user_id: str,
        message_id: str,
        feishu_api
    ) -> Dict[str, Any]:
        """
        处理 Escape 按钮

        Args:
            user_id: 用户 ID
            message_id: 消息 ID
            feishu_api: 飞书 API 实例

        Returns:
            交互结果
        """
        logger.info(f"用户选择 Escape，跳过交互")
        result = {
            "type": "escape",
            "user_id": user_id,
            "message_id": message_id,
            "value": None
        }
        await self._write_interaction_response(message_id, result)
        return result

    async def _handle_confirm(
        self,
        user_id: str,
        message_id: str,
        value: str,
        feishu_api
    ) -> Dict[str, Any]:
        """
        处理 Yes/No 确认

        Args:
            user_id: 用户 ID
            message_id: 消息 ID
            value: 选择的值 ("yes" 或 "no")
            feishu_api: 飞书 API 实例

        Returns:
            交互结果
        """
        logger.info(f"用户确认: {value}")
        result = {
            "type": "confirm",
            "user_id": user_id,
            "message_id": message_id,
            "value": value
        }
        await self._write_interaction_response(message_id, result)
        return result

    async def _handle_form_submit(
        self,
        user_id: str,
        message_id: str,
        form_value: Dict[str, Any],
        feishu_api
    ) -> Dict[str, Any]:
        """
        处理表单提交（单选或多选）

        Args:
            user_id: 用户 ID
            message_id: 消息 ID
            form_value: 表单数据
            feishu_api: 飞书 API 实例

        Returns:
            交互结果
        """
        # 单选 select_static
        if "select_option" in form_value:
            value = form_value["select_option"]
            logger.info(f"用户单选: {value}")
            result = {
                "type": "select",
                "user_id": user_id,
                "message_id": message_id,
                "value": value
            }
            await self._write_interaction_response(message_id, result)
            return result

        # 多选 checker
        if "multi_select_options" in form_value:
            values = form_value["multi_select_options"]
            # 如果是单个值，转换为列表
            if isinstance(values, str):
                values = [values]
            logger.info(f"用户多选: {values}")
            result = {
                "type": "multi_select",
                "user_id": user_id,
                "message_id": message_id,
                "value": values
            }
            await self._write_interaction_response(message_id, result)
            return result

        logger.warning(f"未知的表单类型: {form_value}")
        return None

    async def wait_for_interaction(self, task_id: str, timeout: float = 300.0) -> Optional[Any]:
        """
        等待用户交互结果

        Args:
            task_id: 任务 ID
            timeout: 超时时间（秒），默认 300 秒

        Returns:
            用户交互结果，超时返回 None
        """
        event = asyncio.Event()

        async with self._lock:
            self._result_events[task_id] = event

        try:
            # 等待用户交互或超时
            await asyncio.wait_for(event.wait(), timeout=timeout)

            async with self._lock:
                if task_id in self._interaction_results:
                    result = self._interaction_results.pop(task_id)
                    return result
                return None

        except asyncio.TimeoutError:
            logger.warning(f"任务 {task_id} 等待交互超时")
            async with self._lock:
                self._result_events.pop(task_id, None)
            return None
        finally:
            async with self._lock:
                self._result_events.pop(task_id, None)

    async def set_interaction_result(self, task_id: str, result: Any):
        """
        设置交互结果并触发等待事件

        Args:
            task_id: 任务 ID
            result: 交互结果
        """
        async with self._lock:
            self._interaction_results[task_id] = result
            if task_id in self._result_events:
                self._result_events[task_id].set()

    def remove_interaction(self, task_id: str):
        """
        移除等待中的交互

        Args:
            task_id: 任务 ID
        """
        asyncio.run_coroutine_threadsafe(
            self._remove_interaction(task_id),
            asyncio.get_event_loop()
        )

    async def _remove_interaction(self, task_id: str):
        """异步移除交互"""
        async with self._lock:
            self._pending_interactions.pop(task_id, None)
            self._interaction_results.pop(task_id, None)
            if task_id in self._result_events:
                self._result_events[task_id].set()
                self._result_events.pop(task_id, None)

    async def _write_interaction_response(self, message_id: str, result: Dict[str, Any]):
        """
        将交互响应写入文件（供 hook 读取）

        Args:
            message_id: 消息 ID
            result: 响应结果
        """
        if INTERACTION_RESPONSE_FILE is None:
            logger.warning("交互响应文件路径未设置，跳过写入")
            return

        try:
            response_data = {
                "message_id": message_id,
                "type": result.get("type"),
                "value": result.get("value"),
                "user_id": result.get("user_id"),
                "timestamp": time.time()
            }
            with open(INTERACTION_RESPONSE_FILE, "w", encoding="utf-8") as f:
                json.dump(response_data, f, ensure_ascii=False)
            logger.info(f"交互响应已写入文件: {response_data}")
        except Exception as e:
            logger.error(f"写入交互响应文件时出错: {e}", exc_info=True)


# 全局交互管理器实例
interaction_manager = InteractionManager()
