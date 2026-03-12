"""
事件处理器

处理飞书消息事件和卡片交互事件
"""
import json
import logging
import asyncio
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.config.settings import get_settings

# 避免循环导入
if TYPE_CHECKING:
    from src.feishu import FeishuAPI
    from src.interaction_manager import InteractionManager

logger = logging.getLogger(__name__)


def create_event_handlers(interaction_manager: "InteractionManager", feishu_api_instance: "FeishuAPI"):
    """
    创建事件处理器（同步函数，供 lark_oapi SDK 调用）

    注意：lark_oapi SDK 的 EventDispatcherHandler.do() 是同步方法，
    因此处理器必须是同步函数，内部使用 asyncio.create_task() 来运行异步代码

    Args:
        interaction_manager: 交互管理器实例
        feishu_api_instance: 飞书 API 实例

    Returns:
        tuple: (do_p2_im_message_receive_v1, do_p2_card_action_trigger)
    """

    def do_p2_im_message_receive_v1(data):
        """
        处理消息接收事件（同步包装器）

        Args:
            data: P2ImMessageReceiveV1 对象
        """
        try:
            logger.info(f"收到消息事件")

            # 将 event 对象转换为 JSON 打印出来
            try:
                # 尝试获取原始数据字典
                if hasattr(data, '__dict__'):
                    event_dict = data.__dict__
                    logger.info(f"原始事件数据 (JSON): {json.dumps(event_dict, ensure_ascii=False, default=str)}")

                # 打印 event_obj 的详细属性
                event_obj = data.event
                if hasattr(event_obj, '__dict__'):
                    logger.info(f"event_obj (JSON): {json.dumps(event_obj.__dict__, ensure_ascii=False, default=str)}")
                if hasattr(event_obj.sender, '__dict__'):
                    logger.info(f"sender (JSON): {json.dumps(event_obj.sender.__dict__, ensure_ascii=False, default=str)}")
                if hasattr(event_obj.message, '__dict__'):
                    logger.info(f"message (JSON): {json.dumps(event_obj.message.__dict__, ensure_ascii=False, default=str)}")
            except Exception as e:
                logger.info(f"无法转换事件为 JSON: {e}")

            # data 是 P2ImMessageReceiveV1 对象
            event_obj = data.event

            # 解析事件数据为 message_handler 期望的格式
            # 注意：content 是一个 JSON 字符串，需要解析
            event_data = {
                "type": "im.message.receive_v1",
                "event": {
                    "sender": {
                        "sender_id": {
                            "open_id": event_obj.sender.sender_id.open_id,
                            "user_id": event_obj.sender.sender_id.user_id
                        }
                    },
                    "message": {
                        "message_id": event_obj.message.message_id,
                        "content": event_obj.message.content,  # JSON 字符串
                        "msg_type": event_obj.message.message_type,
                        "create_time": event_obj.message.create_time
                    },
                    "chat_type": event_obj.message.chat_type
                }
            }

            # 打印事件数据（调试用）
            logger.info(f"事件数据类型: {event_data.get('type')}")
            msg_type = event_data.get("event", {}).get("message", {}).get("msg_type")
            logger.info(f"消息类型: {msg_type}")

            # 使用 asyncio.create_task 在后台运行消息处理器
            # 这样可以避免阻塞 SDK 的事件循环
            from src.message_handler import message_handler
            logger.info(f"准备调用 message_handler.handle_event...")

            # 在新的事件循环中运行异步代码（因为 SDK 可能在非异步上下文中调用）
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # 如果当前有事件循环在运行，创建任务
                    task = asyncio.create_task(message_handler.handle_event(event_data))
                    # 确保任务完成或被正确处理
                    task.add_done_callback(lambda t: t.exception() if not t.done() else None)
                else:
                    # 如果没有事件循环在运行，运行异步代码
                    loop.run_until_complete(message_handler.handle_event(event_data))
            except RuntimeError:
                # 如果没有事件循环，创建新的
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(message_handler.handle_event(event_data))
                finally:
                    new_loop.close()

            logger.info(f"message_handler.handle_event 已调用")

        except Exception as e:
            logger.error(f"处理消息事件时出错: {e}", exc_info=True)

    def do_p2_card_action_trigger(data):
        """
        处理卡片交互触发事件（同步包装器）

        Args:
            data: P2CardActionTrigger 对象
        """
        try:
            logger.info(f"收到卡片交互事件")

            # 打印原始事件数据（用于调试）
            try:
                if hasattr(data, '__dict__'):
                    event_dict = data.__dict__
                    logger.info(f"卡片交互原始事件 (JSON): {json.dumps(event_dict, ensure_ascii=False, default=str)}")

                event_obj = data.event
                if hasattr(event_obj, '__dict__'):
                    logger.info(f"event_obj (JSON): {json.dumps(event_obj.__dict__, ensure_ascii=False, default=str)}")

                # 提取关键信息
                action_value = None
                form_value = None
                if hasattr(event_obj, 'action'):
                    if hasattr(event_obj.action, 'value'):
                        action_value = event_obj.action.value
                    if hasattr(event_obj.action, 'form_value'):
                        form_value = event_obj.action.form_value

                operator_info = {}
                if hasattr(event_obj, 'operator'):
                    if hasattr(event_obj.operator, '__dict__'):
                        operator_info = event_obj.operator.__dict__

                context_info = {}
                if hasattr(event_obj, 'context'):
                    if hasattr(event_obj.context, '__dict__'):
                        context_info = event_obj.context.__dict__

                logger.info(f"Action value: {action_value}")
                logger.info(f"Form value: {form_value}")
                logger.info(f"Operator: {operator_info}")
                logger.info(f"Context: {context_info}")

            except Exception as e:
                logger.info(f"无法转换卡片交互事件为 JSON: {e}")

            # 构建交互数据
            interaction_data = {
                "action_value": action_value,
                "form_value": form_value,
                "operator": operator_info,
                "context": context_info
            }

            # 在新的事件循环中运行异步代码
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(interaction_manager.handle_card_interaction(interaction_data, feishu_api_instance))
                else:
                    loop.run_until_complete(interaction_manager.handle_card_interaction(interaction_data, feishu_api_instance))
            except RuntimeError:
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    new_loop.run_until_complete(interaction_manager.handle_card_interaction(interaction_data, feishu_api_instance))
                finally:
                    new_loop.close()

        except Exception as e:
            logger.error(f"处理卡片交互事件时出错: {e}", exc_info=True)

    return do_p2_im_message_receive_v1, do_p2_card_action_trigger
