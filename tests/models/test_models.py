"""
数据模型单元测试
"""
import pytest
from datetime import datetime

# 添加项目根目录到路径
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import (
    MessageType,
    MessageDirection,
    MessageSource,
    Message,
)


class TestEnums:
    """测试枚举类型"""

    def test_message_type_values(self):
        """测试消息类型枚举值"""
        assert MessageType.COMMAND == "command"
        assert MessageType.RESPONSE == "response"
        assert MessageType.STATUS == "status"
        assert MessageType.ERROR == "error"

    def test_message_direction_values(self):
        """测试消息方向枚举值"""
        assert MessageDirection.UPSTREAM == "upstream"
        assert MessageDirection.DOWNSTREAM == "downstream"

    def test_message_source_values(self):
        """测试消息来源枚举值"""
        assert MessageSource.FEISHU == "feishu"
        assert MessageSource.HOOK == "hook"
        assert MessageSource.API_TEST == "api_test"

    def test_enums_are_strings(self):
        """测试枚举继承自 str"""
        assert isinstance(MessageType.COMMAND, str)
        assert isinstance(MessageDirection.UPSTREAM, str)
        assert isinstance(MessageSource.FEISHU, str)


class TestMessageModel:
    """测试 Message 模型"""

    def test_message_creation_minimal(self):
        """测试最小参数创建消息"""
        msg = Message(
            user_id="user-001",
            message_type=MessageType.COMMAND,
            content="hello world",
            feishu_message_id="fm-001"
        )

        assert msg.user_id == "user-001"
        assert msg.message_type == MessageType.COMMAND
        assert msg.content == "hello world"
        assert msg.feishu_message_id == "fm-001"
        assert isinstance(msg.created_at, datetime)
        assert msg.direction is None
        assert msg.is_test is None  # 默认使用全局测试模式
        assert msg.message_source is None

    def test_message_creation_full(self):
        """测试完整参数创建消息"""
        now = datetime.now()
        msg = Message(
            id=1,
            user_id="user-001",
            message_type=MessageType.RESPONSE,
            content="response content",
            created_at=now,
            direction=MessageDirection.DOWNSTREAM,
            is_test=True,
            message_source=MessageSource.HOOK,
            feishu_message_id="fm-123",
        )

        assert msg.id == 1
        assert msg.direction == MessageDirection.DOWNSTREAM
        assert msg.is_test is True
        assert msg.message_source == MessageSource.HOOK
        assert msg.feishu_message_id == "fm-123"

    def test_message_model_dump(self):
        """测试 Message 导出为字典"""
        msg = Message(
            user_id="user-001",
            message_type=MessageType.STATUS,
            content="status update",
            feishu_message_id="fm-003"
        )
        data = msg.model_dump()

        assert isinstance(data, dict)
        assert data["feishu_message_id"] == "fm-003"
        assert data["message_type"] == "status"

    def test_message_direction_types(self):
        """测试消息方向类型"""
        msg_up = Message(
            user_id="user-001",
            message_type=MessageType.COMMAND,
            content="user command",
            direction=MessageDirection.UPSTREAM,
            feishu_message_id="fm-up"
        )
        assert msg_up.direction == MessageDirection.UPSTREAM

        msg_down = Message(
            user_id="user-001",
            message_type=MessageType.RESPONSE,
            content="bot response",
            direction=MessageDirection.DOWNSTREAM,
            feishu_message_id="fm-down"
        )
        assert msg_down.direction == MessageDirection.DOWNSTREAM

    def test_message_source_types(self):
        """测试消息来源类型"""
        for source in [MessageSource.FEISHU, MessageSource.HOOK, MessageSource.API_TEST]:
            msg = Message(
                user_id="user-001",
                message_type=MessageType.COMMAND,
                content="test",
                message_source=source,
                feishu_message_id=f"fm-{source.value}"
            )
            assert msg.message_source == source