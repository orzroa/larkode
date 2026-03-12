"""
测试 storage 层处理 sqlite3.Row 的正确性
"""
import pytest
import sqlite3
import tempfile
from pathlib import Path
from src.storage import Database
from src.models import Message, MessageType, MessageDirection, MessageSource
from datetime import datetime


class TestStorageRowHandling:
    """测试 Database 类正确处理 sqlite3.Row"""

    def setup_method(self):
        """创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.db = Database(self.db_path)

    def teardown_method(self):
        """清理临时数据库"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_and_get_user_messages(self):
        """测试保存和获取用户消息"""
        user_id = "test_user"

        # 保存消息
        msg1 = Message(
            user_id=user_id,
            message_type=MessageType.COMMAND,
            content="ls -la",
            direction=MessageDirection.UPSTREAM,
            message_source=MessageSource.FEISHU,
            feishu_message_id="fm-msg1"
        )
        msg2 = Message(
            user_id=user_id,
            message_type=MessageType.RESPONSE,
            content="output",
            direction=MessageDirection.DOWNSTREAM,
            message_source=MessageSource.FEISHU,
            feishu_message_id="fm-msg2"
        )
        self.db.save_message(msg1)
        self.db.save_message(msg2)

        # 获取消息列表
        messages = self.db.get_user_messages(user_id, limit=5)

        # 验证返回的是 Message 对象
        assert len(messages) == 2
        for msg in messages:
            assert isinstance(msg, Message)
            assert isinstance(msg.message_type, MessageType)
            assert msg.id is not None

    def test_get_messages_by_direction(self):
        """测试按方向获取消息"""
        user_id = "test_user"

        # 保存消息
        msg1 = Message(
            user_id=user_id,
            message_type=MessageType.COMMAND,
            content="command",
            direction=MessageDirection.UPSTREAM,
            feishu_message_id="fm-msg1"
        )
        msg2 = Message(
            user_id=user_id,
            message_type=MessageType.RESPONSE,
            content="response",
            direction=MessageDirection.DOWNSTREAM,
            feishu_message_id="fm-msg2"
        )
        self.db.save_message(msg1)
        self.db.save_message(msg2)

        # 按方向获取
        upstream = self.db.get_messages_by_direction(MessageDirection.UPSTREAM, user_id)
        downstream = self.db.get_messages_by_direction(MessageDirection.DOWNSTREAM, user_id)

        assert len(upstream) == 1
        assert len(downstream) == 1
        assert upstream[0].content == "command"
        assert downstream[0].content == "response"

    def test_get_messages_by_source(self):
        """测试按来源获取消息"""
        user_id = "test_user"

        # 保存消息
        msg1 = Message(
            user_id=user_id,
            message_type=MessageType.COMMAND,
            content="feishu message",
            message_source=MessageSource.FEISHU,
            feishu_message_id="fm-msg1"
        )
        msg2 = Message(
            user_id=user_id,
            message_type=MessageType.RESPONSE,
            content="hook message",
            message_source=MessageSource.HOOK,
            feishu_message_id="fm-msg2"
        )
        self.db.save_message(msg1)
        self.db.save_message(msg2)

        # 按来源获取
        feishu_msgs = self.db.get_messages_by_source(MessageSource.FEISHU, user_id)
        hook_msgs = self.db.get_messages_by_source(MessageSource.HOOK, user_id)

        assert len(feishu_msgs) == 1
        assert len(hook_msgs) == 1

    def test_get_test_messages(self):
        """测试获取测试消息"""
        user_id = "test_user"

        # 保存测试和非测试消息
        msg1 = Message(
            user_id=user_id,
            message_type=MessageType.COMMAND,
            content="normal message",
            is_test=False,
            feishu_message_id="fm-msg1"
        )
        msg2 = Message(
            user_id=user_id,
            message_type=MessageType.COMMAND,
            content="test message",
            is_test=True,
            feishu_message_id="fm-msg2"
        )
        self.db.save_message(msg1)
        self.db.save_message(msg2)

        # 获取测试消息
        test_msgs = self.db.get_test_messages(user_id)
        assert len(test_msgs) == 1
        assert test_msgs[0].is_test is True

    def test_get_message_statistics(self):
        """测试消息统计"""
        # 保存不同类型的消息
        for i in range(3):
            msg = Message(
                user_id=f"user-{i % 2}",
                message_type=MessageType.COMMAND,
                content=f"content-{i}",
                direction=MessageDirection.UPSTREAM if i % 2 == 0 else MessageDirection.DOWNSTREAM,
                message_source=MessageSource.FEISHU if i % 2 == 0 else MessageSource.HOOK,
                feishu_message_id=f"fm-msg-{i}"
            )
            self.db.save_message(msg)

        # 获取统计
        stats = self.db.get_message_statistics()
        assert len(stats) > 0
        assert any(s["direction"] == "upstream" for s in stats)
        assert any(s["direction"] == "downstream" for s in stats)