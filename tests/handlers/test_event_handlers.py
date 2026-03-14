"""
测试事件处理器
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path
import asyncio

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestEventHandlers:
    """测试事件处理器"""

    @pytest.fixture
    def mock_interaction_manager(self):
        """创建模拟的交互管理器"""
        manager = Mock()
        manager.handle_card_interaction = AsyncMock()
        return manager

    @pytest.fixture
    def mock_feishu_api(self):
        """创建模拟的飞书 API"""
        return Mock()

    def test_create_event_handlers_returns_tuple(self, mock_interaction_manager, mock_feishu_api):
        """测试创建事件处理器返回元组"""
        from src.handlers.event_handlers import create_event_handlers
        handlers = create_event_handlers(mock_interaction_manager, mock_feishu_api)

        assert isinstance(handlers, tuple)
        assert len(handlers) == 2
        assert callable(handlers[0])
        assert callable(handlers[1])

    def test_do_p2_im_message_receive_v1_basic(self, mock_interaction_manager, mock_feishu_api):
        """测试消息接收处理器基本功能"""
        from src.handlers.event_handlers import create_event_handlers
        do_p2_im_message_receive_v1, _ = create_event_handlers(mock_interaction_manager, mock_feishu_api)

        # 创建模拟的 P2ImMessageReceiveV1 对象
        mock_data = Mock()
        mock_event = Mock()
        mock_sender = Mock()
        mock_sender_id = Mock()
        mock_sender_id.open_id = "ou_test123"
        mock_sender_id.user_id = "user_test123"
        mock_sender.sender_id = mock_sender_id

        mock_message = Mock()
        mock_message.message_id = "msg_123"
        mock_message.content = '{"text": "Hello"}'
        mock_message.message_type = "text"
        mock_message.create_time = "1234567890"
        mock_message.chat_type = "p2p"

        mock_event.sender = mock_sender
        mock_event.message = mock_message
        mock_data.event = mock_event

        with patch('src.message_handler.message_handler') as mock_msg_handler:
            mock_msg_handler.handle_event = AsyncMock()
            # 调用处理器 - 应该不抛出异常
            do_p2_im_message_receive_v1(mock_data)

    def test_do_p2_im_message_receive_v1_with_exception(self, mock_interaction_manager, mock_feishu_api):
        """测试消息接收处理器异常处理"""
        from src.handlers.event_handlers import create_event_handlers
        do_p2_im_message_receive_v1, _ = create_event_handlers(mock_interaction_manager, mock_feishu_api)

        # 创建会抛出异常的模拟对象
        mock_data = Mock()
        mock_data.event = Mock()
        mock_data.event.sender = Mock()
        mock_data.event.sender.sender_id = Mock()
        mock_data.event.sender.sender_id.open_id = "ou_test123"
        mock_data.event.sender.sender_id.user_id = "user_test123"
        mock_data.event.message = Mock()
        mock_data.event.message.message_id = "msg_123"
        mock_data.event.message.content = '{"text": "Hello"}'
        mock_data.event.message.message_type = "text"
        mock_data.event.message.create_time = "1234567890"
        mock_data.event.message.chat_type = "p2p"

        with patch('src.message_handler.message_handler') as mock_msg_handler:
            mock_msg_handler.handle_event = AsyncMock(side_effect=Exception("Test error"))
            # 应该捕获异常，不抛出
            do_p2_im_message_receive_v1(mock_data)

    def test_do_p2_card_action_trigger_basic(self, mock_interaction_manager, mock_feishu_api):
        """测试卡片交互处理器基本功能"""
        from src.handlers.event_handlers import create_event_handlers
        _, do_p2_card_action_trigger = create_event_handlers(mock_interaction_manager, mock_feishu_api)

        # 创建模拟的 P2CardActionTrigger 对象 - 使用简单类模拟
        class MockAction:
            value = {"action": "confirm"}
            form_value = {"input": "test"}

        class MockOperator:
            open_id = "ou_test123"

        class MockContext:
            open_message_id = "msg_123"

        class MockEvent:
            action = MockAction()
            operator = MockOperator()
            context = MockContext()

        class MockData:
            event = MockEvent()

        mock_data = MockData()

        # 调用处理器 - 应该不抛出异常
        do_p2_card_action_trigger(mock_data)

    def test_do_p2_card_action_trigger_with_exception(self, mock_interaction_manager, mock_feishu_api):
        """测试卡片交互处理器异常处理"""
        from src.handlers.event_handlers import create_event_handlers
        _, do_p2_card_action_trigger = create_event_handlers(mock_interaction_manager, mock_feishu_api)

        # 创建会抛出异常的模拟对象
        mock_data = Mock()
        mock_data.event = Mock()

        # 设置属性使其能正常解析，但在处理时抛出异常
        mock_action = Mock()
        mock_action.value = {"action": "confirm"}
        mock_action.form_value = None
        mock_event = Mock()
        mock_event.action = mock_action
        mock_event.operator = Mock()
        mock_event.operator.__dict__ = {"open_id": "ou_test123"}
        mock_event.context = Mock()
        mock_event.context.__dict__ = {"open_message_id": "msg_123"}
        mock_data.event = mock_event

        # 设置 interaction_manager 抛出异常
        mock_interaction_manager.handle_card_interaction = AsyncMock(side_effect=Exception("Test error"))

        # 应该捕获异常，不抛出
        do_p2_card_action_trigger(mock_data)

    def test_do_p2_im_message_receive_v1_handles_runtime_error(self, mock_interaction_manager, mock_feishu_api):
        """测试消息接收处理器处理 RuntimeError"""
        from src.handlers.event_handlers import create_event_handlers
        do_p2_im_message_receive_v1, _ = create_event_handlers(mock_interaction_manager, mock_feishu_api)

        mock_data = Mock()
        mock_event = Mock()
        mock_sender = Mock()
        mock_sender_id = Mock()
        mock_sender_id.open_id = "ou_test123"
        mock_sender_id.user_id = "user_test123"
        mock_sender.sender_id = mock_sender_id

        mock_message = Mock()
        mock_message.message_id = "msg_123"
        mock_message.content = '{"text": "Hello"}'
        mock_message.message_type = "text"
        mock_message.create_time = "1234567890"
        mock_message.chat_type = "p2p"

        mock_event.sender = mock_sender
        mock_event.message = mock_message
        mock_data.event = mock_event

        with patch('src.message_handler.message_handler') as mock_msg_handler:
            mock_msg_handler.handle_event = AsyncMock()
            with patch('asyncio.get_event_loop', side_effect=RuntimeError("No loop")):
                # 应该捕获异常，不抛出
                do_p2_im_message_receive_v1(mock_data)