"""
交互监控器

监控交互请求文件并处理用户交互
"""
import asyncio
import json
import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from src.config.settings import get_settings

logger = logging.getLogger(__name__)

# 交互文件路径
INTERACTION_REQUEST_FILE = get_settings().LOG_DIR / "interaction_request.json"
INTERACTION_RESPONSE_FILE = get_settings().LOG_DIR / "interaction_response.json"


class InteractionMonitor:
    """交互监控器"""

    def __init__(self, interaction_manager: Any):
        """
        初始化交互监控器

        Args:
            interaction_manager: 交互管理器实例
        """
        self._interaction_manager = interaction_manager

    async def monitor_interaction_requests(self):
        """监控交互请求文件"""
        last_request_time = 0
        last_request_hash = ""

        while True:
            try:
                if INTERACTION_REQUEST_FILE.exists():
                    # 检查文件是否更新（通过比较修改时间和内容哈希）
                    stat = INTERACTION_REQUEST_FILE.stat()
                    current_time = stat.st_mtime

                    if current_time > last_request_time:
                        try:
                            with open(INTERACTION_REQUEST_FILE, "r", encoding="utf-8") as f:
                                request = json.load(f)

                            # 计算内容哈希
                            current_hash = json.dumps(request, sort_keys=True)
                            if current_hash != last_request_hash:
                                last_request_time = current_time
                                last_request_hash = current_hash
                                logger.info(f"检测到新的交互请求: {request}")

                                # 处理交互请求
                                await self.handle_interaction_request(request)

                        except (json.JSONDecodeError, IOError) as e:
                            logger.error(f"读取交互请求文件失败: {e}")

                # 每秒检查一次
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"监控交互请求时出错: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def handle_interaction_request(self, request: dict):
        """
        处理交互请求

        Args:
            request: 交互请求数据
        """
        try:
            message_id = request.get("message_id")
            interaction_type = request.get("interaction_type")

            logger.info(f"等待用户交互: type={interaction_type}, msg_id={message_id}")

            # 存储交互请求，等待响应
            interaction_request_id = f"{message_id}_{int(time.time())}"
            self._interaction_manager._pending_interactions[interaction_request_id] = request

            # 设置超时（5分钟）
            timeout = 300.0

            # 等待用户响应（通过 Feishu 卡片交互）
            try:
                result = await asyncio.wait_for(
                    self._wait_for_card_interaction(message_id),
                    timeout=timeout
                )

                # 写入响应文件
                if result:
                    response_data = {
                        "message_id": message_id,
                        "interaction_type": interaction_type,
                        "value": result.get("value"),
                        "type": result.get("type"),
                        "timestamp": time.time()
                    }
                    with open(INTERACTION_RESPONSE_FILE, "w", encoding="utf-8") as f:
                        json.dump(response_data, f, ensure_ascii=False)
                    logger.info(f"用户响应已写入: {response_data}")
                else:
                    # 超时或 Escape
                    response_data = {
                        "message_id": message_id,
                        "interaction_type": interaction_type,
                        "value": None,
                        "type": "timeout",
                        "timestamp": time.time()
                    }
                    with open(INTERACTION_RESPONSE_FILE, "w", encoding="utf-8") as f:
                        json.dump(response_data, f, ensure_ascii=False)
                    logger.info(f"交互超时或取消")

            except asyncio.TimeoutError:
                logger.warning(f"等待用户交互超时")
                response_data = {
                    "message_id": message_id,
                    "interaction_type": interaction_type,
                    "value": None,
                    "type": "timeout",
                    "timestamp": time.time()
                }
                with open(INTERACTION_RESPONSE_FILE, "w", encoding="utf-8") as f:
                    json.dump(response_data, f, ensure_ascii=False)

        except Exception as e:
            logger.error(f"处理交互请求时出错: {e}", exc_info=True)

    async def _wait_for_card_interaction(self, message_id: str, timeout: float = 300.0):
        """
        等待卡片交互

        Args:
            message_id: 消息 ID
            timeout: 超时时间

        Returns:
            dict: 交互结果
        """
        # 创建一个事件来等待响应
        response_event = asyncio.Event()

        # 注册临时的事件处理器
        temp_handler = None

        def on_message(event_data):
            nonlocal temp_handler
            try:
                msg_content = event_data.get("message", {})
                if msg_content.get("message_id") == message_id:
                    # 检查是否是交互类型（卡片交互事件会通过事件处理器处理）
                    # 这里需要等待 interaction_manager 触发
                    pass
            except Exception as e:
                logger.error(f"处理等待交互消息时出错: {e}")

        return {}
