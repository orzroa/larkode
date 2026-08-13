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
            from src.option_card import parse_action_value
            action_value = parse_action_value(interaction_data.get("action_value")) or {}
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

                if action_value.get("action") == "codex_approval":
                    return await self._handle_codex_approval(
                        user_open_id, action_value, feishu_api
                    )

                # 选项卡（OptionCard）：opt 字段标识具体动作
                opt = action_value.get("opt")
                if opt in ("select", "page"):
                    return await self._handle_option_card_action(
                        user_open_id, action_value, feishu_api
                    )

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

    async def _handle_codex_approval(
        self, user_id: str, action_value: Dict[str, Any], feishu_api
    ) -> Dict[str, Any]:
        """处理 Codex App Server 审批按钮。"""
        from src.agent.approval import codex_approval_broker

        approval_id = action_value.get("approval_id", "")
        decision = action_value.get("decision", "")
        allowed = {"accept", "acceptForSession", "decline", "cancel"}
        resolved = decision in allowed and codex_approval_broker.resolve(
            approval_id, user_id, decision
        )
        if resolved:
            labels = {
                "accept": "已允许本次操作",
                "acceptForSession": "已允许本会话中的同类操作",
                "decline": "已拒绝操作",
                "cancel": "已取消操作",
            }
            await self._quick_confirm(user_id, labels[decision], feishu_api)
        else:
            await self._quick_confirm(user_id, "该审批已失效或不属于当前用户", feishu_api)
        return {
            "type": "codex_approval",
            "user_id": user_id,
            "value": decision,
            "resolved": resolved,
        }

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

    async def _handle_option_card_action(
        self,
        user_id: str,
        action_value: Dict[str, Any],
        feishu_api,
    ) -> Optional[Dict[str, Any]]:
        """
        处理选项卡（OptionCard）交互：opt=select 或 opt=page

        Args:
            user_id: 用户 ID
            action_value: 解析后的 action.value，结构: {opt, cat, key?, page?}
            feishu_api: 飞书 API 实例
        """
        from src.handlers.workspace_commands import WorkspaceCommands
        from src.handlers.ccr_commands import CCRCommands

        opt = action_value.get("opt")
        cat = action_value.get("cat")

        from src.card_dispatcher import CardDispatcher
        card_dispatcher = CardDispatcher(feishu_api=feishu_api)

        async def send_message_func(uid, card=None, message=None):
            if isinstance(card, dict):
                return await card_dispatcher.send_interactive_card(uid, card)
            if card is not None:
                payload = _serialize_card(card)
                return await feishu_api.send_message(uid, payload)
            if message is not None:
                return await feishu_api.send_message(uid, message)
            return False

        def _serialize_card(card):
            """把 NormalizedCard / dict / str 统一转成飞书卡片 JSON 字符串"""
            if isinstance(card, str):
                return card
            # NormalizedCard：转成飞书 V2 schema 后再 JSON 序列化
            try:
                from src.interfaces.im_platform import NormalizedCard
                is_nc = isinstance(card, NormalizedCard)
            except ImportError:
                is_nc = False
            if is_nc:
                feishu_card = {
                    "schema": "2.0",
                    "config": {"wide_screen_mode": True},
                    "header": {
                        "title": {"tag": "plain_text", "content": card.title},
                        "template": card.template_color,
                    },
                    "body": {
                        "elements": [
                            {"tag": "markdown", "content": card.content},
                        ],
                    },
                }
                return json.dumps(feishu_card, ensure_ascii=False)
            return json.dumps(card, ensure_ascii=False, default=_default_json)

        def _default_json(obj):
            """JSON 序列化兜底：对象若有 to_dict() 就用其输出"""
            to_dict = getattr(obj, "to_dict", None)
            if callable(to_dict):
                return to_dict()
            raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

        if cat == "ws":
            handler = WorkspaceCommands()
            if opt == "page":
                page = action_value.get("page", 1)
                await handler.show_workspace_option_card(user_id, send_message_func, page=page)
                return {"type": "option_card_page", "category": "ws", "page": page}
            if opt == "select":
                key = action_value.get("key", "")
                # 先发文字确认（让用户立即看到反馈）
                await self._quick_confirm(
                    user_id, f"⏳ 正在切换到工作空间 `{key}`...",
                    feishu_api,
                )
                await handler.handle_workspace_select(user_id, key, send_message_func)
                return {"type": "option_card_select", "category": "ws", "key": key}

        if cat == "ws_group":
            handler = WorkspaceCommands()
            group_name = action_value.get("key", "")
            page = action_value.get("page", 1)
            await handler.show_workspace_group_contents_option_card(
                user_id, group_name, send_message_func, page=page,
            )
            return {"type": "option_card_select", "category": "ws_group", "key": group_name}

        if cat == "ws_parent":
            handler = WorkspaceCommands()
            group_name = action_value.get("key", "")
            # 先发文字确认
            await self._quick_confirm(
                user_id, f"⏳ 正在切换到 `{group_name}/` 目录...",
                feishu_api,
            )
            await handler.handle_workspace_parent_select(user_id, group_name, send_message_func)
            return {"type": "option_card_select", "category": "ws_parent", "key": group_name}

        elif cat == "model":
            handler = CCRCommands()
            if opt == "page":
                page = action_value.get("page", 1)
                await handler.show_model_option_card(user_id, send_message_func, page=page)
                return {"type": "option_card_page", "category": "model", "page": page}
            if opt == "select":
                key = action_value.get("key", "")
                # 先发文字确认
                await self._quick_confirm(
                    user_id, f"⏳ 正在切换模型 `{key}`...",
                    feishu_api,
                )
                await handler.handle_model_select(user_id, key, send_message_func)
                return {"type": "option_card_select", "category": "model", "key": key}

        if cat in {"codex_model", "codex_effort"}:
            from src.handlers.codex_commands import CodexCommands
            from src.task_manager import task_manager

            handler = CodexCommands(task_manager)
            try:
                if opt == "page":
                    page = action_value.get("page", 1)
                    if cat == "codex_model":
                        await handler.show_model_option_card(user_id, send_message_func, page=page)
                    else:
                        await handler.show_effort_option_card(user_id, send_message_func, page=page)
                    return {"type": "option_card_page", "category": cat, "page": page}
                if opt == "select":
                    key = action_value.get("key", "")
                    if cat == "codex_model":
                        await handler.handle_model_select(user_id, key, send_message_func)
                    else:
                        await handler.handle_effort_select(
                            user_id,
                            key,
                            send_message_func,
                            expected_model_id=action_value.get("model_id", ""),
                        )
                    return {"type": "option_card_select", "category": cat, "key": key}
            except Exception as exc:
                logger.error(f"处理 Codex 选项失败: {exc}", exc_info=True)
                error_text = str(exc)
                stale_effort_card = (
                    cat == "codex_effort"
                    and "Think 卡片属于模型" in error_text
                    and "请重新发送 #think" in error_text
                )
                user_message = (
                    "原 Think 卡片已因模型切换失效，请重新发送 #think"
                    if stale_effort_card else f"设置失败：{error_text}"
                )

                # 卡片交互失败时必须给用户可见回执。先发纯文本，避免错误卡片
                # 自身派发失败而导致用户只看到服务端日志。
                await self._quick_confirm(user_id, user_message, feishu_api)

                # 错误卡片仅作为增强展示；其失败不能影响已发送的文本回执。
                try:
                    await card_dispatcher.send_card(
                        user_id=user_id,
                        card_type="error",
                        title="Think 卡片已失效" if stale_effort_card else "设置失败",
                        content=user_message,
                        message_type="error",
                        template_color="red",
                    )
                except Exception as card_exc:
                    logger.warning(f"发送 Codex 选项错误卡片失败: {card_exc}", exc_info=True)
                return {
                    "type": "option_card_error",
                    "category": cat,
                    "error": user_message,
                }

        logger.warning(f"未知的选项卡交互: opt={opt}, cat={cat}, action_value={action_value}")
        return None

    async def _quick_confirm(self, user_id: str, text: str, feishu_api):
        """立即发一条文字消息，给用户即时反馈（卡片操作完成前先行送达）"""
        try:
            await feishu_api.send_message(user_id, text)
        except Exception as e:
            logger.warning(f"快速反馈发送失败（不影响主流程）: {e}")

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
