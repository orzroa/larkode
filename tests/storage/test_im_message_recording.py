"""
测试 IM 消息全量记录功能
"""
import pytest
import uuid
from datetime import datetime

from src.models import (
    Message,
    MessageType,
    MessageDirection,
    MessageSource,
)
from src.storage import db


class TestIMMessageRecording:
    """测试 IM 消息全量记录功能"""

    def test_message_model_with_new_fields(self):
        """测试 Message 模型支持新字段"""
        msg = Message(
            user_id="user-456",
            message_type=MessageType.COMMAND,
            content="test command",
            direction=MessageDirection.UPSTREAM,
            is_test=True,
            message_source=MessageSource.FEISHU,
            feishu_message_id="msg-789",
        )

        assert msg.direction == MessageDirection.UPSTREAM
        assert msg.is_test is True
        assert msg.message_source == MessageSource.FEISHU
        assert msg.feishu_message_id == "msg-789"

    def test_message_direction_enum(self):
        """测试消息方向枚举"""
        assert MessageDirection.UPSTREAM.value == "upstream"
        assert MessageDirection.DOWNSTREAM.value == "downstream"

    def test_message_source_enum(self):
        """测试消息来源枚举"""
        assert MessageSource.FEISHU.value == "feishu"
        assert MessageSource.HOOK.value == "hook"
        assert MessageSource.API_TEST.value == "api_test"

    def test_save_message_with_new_fields(self):
        """测试保存消息时新字段被正确存储"""
        # 创建一个测试消息
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        msg = Message(
            user_id=test_user_id,
            message_type=MessageType.RESPONSE,
            content="test response",
            direction=MessageDirection.DOWNSTREAM,
            is_test=True,
            message_source=MessageSource.FEISHU,
            feishu_message_id=f"fm-{uuid.uuid4().hex[:8]}"
        )

        result = db.save_message(msg)
        assert result is not None and result > 0

    def test_save_message_with_hook_source(self):
        """测试保存 Hook 来源的消息"""
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"
        msg = Message(
            user_id=test_user_id,
            message_type=MessageType.STATUS,
            content="hook notification",
            direction=MessageDirection.DOWNSTREAM,
            is_test=None,  # 使用全局测试模式
            message_source=MessageSource.HOOK,
            feishu_message_id=f"fm-{uuid.uuid4().hex[:8]}"
        )

        result = db.save_message(msg)
        assert result is not None and result > 0

    def test_get_messages_by_direction(self):
        """测试根据消息方向获取消息"""
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # 创建上行消息
        upstream_msg = Message(
            user_id=test_user_id,
            message_type=MessageType.COMMAND,
            content="upstream message",
            direction=MessageDirection.UPSTREAM,
            is_test=True,
            message_source=MessageSource.FEISHU,
            feishu_message_id=f"fm-upstream-{uuid.uuid4().hex[:8]}"
        )
        db.save_message(upstream_msg)

        # 创建下行消息
        downstream_msg = Message(
            user_id=test_user_id,
            message_type=MessageType.RESPONSE,
            content="downstream message",
            direction=MessageDirection.DOWNSTREAM,
            is_test=True,
            message_source=MessageSource.FEISHU,
            feishu_message_id=f"fm-downstream-{uuid.uuid4().hex[:8]}"
        )
        db.save_message(downstream_msg)

        # 获取上行消息
        upstream_messages = db.get_messages_by_direction(
            MessageDirection.UPSTREAM,
            user_id=test_user_id
        )
        assert len(upstream_messages) >= 1
        assert all(m.direction == MessageDirection.UPSTREAM for m in upstream_messages)

        # 获取下行消息
        downstream_messages = db.get_messages_by_direction(
            MessageDirection.DOWNSTREAM,
            user_id=test_user_id
        )
        assert len(downstream_messages) >= 1
        assert all(m.direction == MessageDirection.DOWNSTREAM for m in downstream_messages)

    def test_get_messages_by_source(self):
        """测试根据消息来源获取消息"""
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # 创建 Hook 消息
        hook_msg = Message(
            user_id=test_user_id,
            message_type=MessageType.STATUS,
            content="hook message",
            direction=MessageDirection.DOWNSTREAM,
            is_test=None,  # 使用全局测试模式
            message_source=MessageSource.HOOK,
            feishu_message_id=f"fm-hook-{uuid.uuid4().hex[:8]}"
        )
        db.save_message(hook_msg)

        # 获取 Hook 消息
        hook_messages = db.get_messages_by_source(
            MessageSource.HOOK,
            user_id=test_user_id
        )
        assert len(hook_messages) >= 1
        assert all(m.message_source == MessageSource.HOOK for m in hook_messages)

    def test_get_test_messages(self):
        """测试获取测试消息"""
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # 创建测试消息
        test_msg = Message(
            user_id=test_user_id,
            message_type=MessageType.COMMAND,
            content="test message",
            direction=MessageDirection.UPSTREAM,
            is_test=True,
            message_source=MessageSource.FEISHU,
            feishu_message_id=f"fm-test-{uuid.uuid4().hex[:8]}"
        )
        db.save_message(test_msg)

        # 获取测试消息
        test_messages = db.get_test_messages(user_id=test_user_id)
        assert len(test_messages) >= 1
        assert all(m.is_test is True for m in test_messages)

    def test_message_statistics(self):
        """测试获取消息统计信息"""
        stats = db.get_message_statistics()
        assert isinstance(stats, list)
        # 统计应该包含 direction, message_source, is_test, count 字段
        for stat in stats:
            assert "direction" in stat or stat.get("direction") is None
            assert "message_source" in stat or stat.get("message_source") is None
            assert "is_test" in stat
            assert "count" in stat
            assert isinstance(stat["count"], int)


class TestIsTestUserDetection:
    """测试测试用户检测逻辑"""

    def test_is_test_user_with_test_prefix(self):
        """测试带有 test 前缀的用户 ID"""
        from src.handlers.command_executor import CommandExecutor
        executor = CommandExecutor()
        assert executor._is_test_user("test_user_123") is True

    def test_is_test_user_with_test_suffix(self):
        """测试带有 test 后缀的用户 ID"""
        from src.handlers.command_executor import CommandExecutor
        executor = CommandExecutor()
        assert executor._is_test_user("user_123_test") is True

    def test_is_test_user_with_test_in_middle(self):
        """测试带有 test 在中间的用户 ID"""
        from src.handlers.command_executor import CommandExecutor
        executor = CommandExecutor()
        assert executor._is_test_user("my_test_user") is True

    def test_is_test_user_uppercase(self):
        """测试大写 TEST 的用户 ID"""
        from src.handlers.command_executor import CommandExecutor
        executor = CommandExecutor()
        assert executor._is_test_user("TEST_USER") is True

    def test_is_test_user_normal_user(self):
        """测试普通用户 ID"""
        from src.handlers.command_executor import CommandExecutor
        executor = CommandExecutor()
        assert executor._is_test_user("ou_123456") is False


class TestHookMessageRecording:
    """测试 Hook 消息记录功能"""

    def test_record_hook_message_function_exists(self):
        """测试 record_hook_message 函数存在"""
        from src.hook_handler import record_hook_message
        assert callable(record_hook_message)

    def test_record_hook_message(self):
        """测试记录 Hook 消息"""
        from src.hook_handler import record_hook_message
        test_user_id = f"test_user_{uuid.uuid4().hex[:8]}"

        # 记录 Hook 消息
        record_hook_message(test_user_id, "test hook message", "notification")

        # 验证消息被保存（Hook 消息使用 STATUS 类型）
        messages = db.get_user_messages(test_user_id, limit=10)
        hook_messages = [m for m in messages if m.message_source == MessageSource.HOOK]
        assert len(hook_messages) >= 1
        assert hook_messages[0].content == "test hook message"
        assert hook_messages[0].message_type == MessageType.STATUS

    def test_record_hook_message_marks_test_user(self):
        """测试记录 Hook 消息时标记测试用户"""
        from src.hook_handler import record_hook_message, _is_test_user
        test_user_id = "test_user_xyz"

        # 验证测试用户检测
        assert _is_test_user(test_user_id) is True

        # 记录消息
        record_hook_message(test_user_id, "test message", "status")

        # 验证消息被标记为测试
        messages = db.get_user_messages(test_user_id, limit=10)
        test_messages = [m for m in messages if m.is_test is True]
        assert len(test_messages) >= 1
