"""飞书 SDK 同步回调与服务主事件循环之间的安全桥接。"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from src.config.settings import get_settings

if TYPE_CHECKING:
    from src.feishu import FeishuAPI
    from src.interaction_manager import InteractionManager

logger = logging.getLogger(__name__)


def create_event_handlers(
    interaction_manager: "InteractionManager",
    feishu_api_instance: "FeishuAPI",
    owner_loop: Optional[asyncio.AbstractEventLoop] = None,
):
    """创建供 lark_oapi 调用的同步处理器。

    生产环境应传入服务主循环。飞书 SDK 的 WebSocket 线程只负责解析事件，
    不创建临时事件循环，也不直接操作绑定在主循环上的 asyncio 对象。
    """

    def _report_done(future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("飞书事件异步处理失败")

    def _submit(coro) -> None:
        if owner_loop is not None:
            if not owner_loop.is_running():
                coro.close()
                raise RuntimeError("Larkode 主事件循环尚未运行")
            future = asyncio.run_coroutine_threadsafe(coro, owner_loop)
            future.add_done_callback(_report_done)
            return

        # 仅供单元测试或嵌入式同步调用；生产入口总是传 owner_loop。
        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(coro)
        else:
            task = running_loop.create_task(coro)
            task.add_done_callback(_report_done)

    def _identity_values(identity) -> tuple[Optional[str], ...]:
        if identity is None:
            return ()
        return tuple(
            getattr(identity, name, None)
            for name in ("open_id", "user_id", "union_id")
        )

    def _authorized(identity) -> bool:
        ids = _identity_values(identity)
        if get_settings().is_feishu_user_authorized(*ids):
            return True
        logger.warning("拒绝未授权的飞书控制请求")
        return False

    async def _handle_message_once(event_data: dict, message_id: str) -> None:
        """在 owner loop 内原子认领；处理失败则释放，允许平台重投。"""
        from src.message_handler import message_handler
        from src.storage import db

        source = "feishu:im.message.receive_v1"
        if not db.claim_inbound_event(source, message_id):
            logger.info("忽略重复投递的飞书消息: message_id=%s", message_id)
            return
        try:
            await message_handler.handle_event(event_data)
        except BaseException:
            db.release_inbound_event(source, message_id)
            raise

    def do_p2_im_message_receive_v1(data):
        try:
            event_obj = data.event
            sender_id = event_obj.sender.sender_id
            message_id = event_obj.message.message_id
            if not _authorized(sender_id):
                return
            if not message_id:
                logger.warning("拒绝缺少 message_id 的飞书消息")
                return
            logger.info("收到飞书消息: message_id=%s", message_id)
            event_data = {
                "type": "im.message.receive_v1",
                "event": {
                    "sender": {
                        "sender_id": {
                            "open_id": getattr(sender_id, "open_id", None),
                            "user_id": getattr(sender_id, "user_id", None),
                            "union_id": getattr(sender_id, "union_id", None),
                        }
                    },
                    "message": {
                        "message_id": message_id,
                        "content": event_obj.message.content,
                        "msg_type": event_obj.message.message_type,
                        "create_time": event_obj.message.create_time,
                    },
                    "chat_type": event_obj.message.chat_type,
                },
            }
            _submit(_handle_message_once(event_data, message_id))
        except Exception:
            logger.exception("处理飞书消息事件失败")

    def do_p2_card_action_trigger(data):
        try:
            event_obj = data.event
            operator = getattr(event_obj, "operator", None)
            if not _authorized(operator):
                return
            action = getattr(event_obj, "action", None)
            context = getattr(event_obj, "context", None)
            action_value = getattr(action, "value", None)
            category = action_value.get("cat") if isinstance(action_value, dict) else None
            logger.info(
                "收到飞书卡片交互: category=%s message_id=%s",
                category,
                getattr(context, "open_message_id", None),
            )
            interaction_data = {
                "action_value": action_value,
                "form_value": getattr(action, "form_value", None),
                "operator": {
                    name: getattr(operator, name, None)
                    for name in ("open_id", "user_id", "union_id")
                },
                "context": {
                    "open_message_id": getattr(context, "open_message_id", None),
                    "open_chat_id": getattr(context, "open_chat_id", None),
                },
            }
            _submit(
                interaction_manager.handle_card_interaction(
                    interaction_data, feishu_api_instance
                )
            )
        except Exception:
            logger.exception("处理飞书卡片交互事件失败")

    return do_p2_im_message_receive_v1, do_p2_card_action_trigger
