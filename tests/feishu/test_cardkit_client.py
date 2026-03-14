"""
测试飞书 CardKit 客户端

主要测试：
1. CardKitClient 卡片实体创建、发送、更新功能
2. StreamingCardUpdater 流式卡片更新器
"""
import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCardKitClient:
    """测试 CardKit 客户端"""

    @pytest.fixture
    def cardkit_client(self):
        """创建 CardKit 客户端实例"""
        from src.feishu.cardkit_client import CardKitClient
        return CardKitClient("test_app_id", "test_app_secret")

    def test_init(self, cardkit_client):
        """测试初始化"""
        assert cardkit_client.app_id == "test_app_id"
        assert cardkit_client.app_secret == "test_app_secret"
        assert cardkit_client._client is None
        assert cardkit_client._card_sequence == {}
        assert cardkit_client._card_metadata == {}

    def test_get_next_sequence_first(self, cardkit_client):
        """测试首次获取 sequence"""
        result = cardkit_client._get_next_sequence("card_123")
        assert result == 1

    def test_get_next_sequence_increment(self, cardkit_client):
        """测试 sequence 递增"""
        cardkit_client._card_sequence["card_123"] = 5
        result = cardkit_client._get_next_sequence("card_123")
        assert result == 6

    @pytest.mark.asyncio
    async def test_create_card_entity_success(self, cardkit_client):
        """测试成功创建卡片实体"""
        mock_response = Mock()
        mock_response.success.return_value = True
        mock_response.code = 0
        mock_response.msg = "success"
        mock_response.data = Mock()
        mock_response.data.card_id = "card_123"
        mock_response.data.sequence = 1

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_client.cardkit.v1.card.create = Mock(return_value=mock_response)
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.create_card_entity(
                    "Test content",
                    title="Test Title",
                    template_color="blue"
                )

                assert result == "card_123"
                assert cardkit_client._card_metadata["card_123"]["title"] == "Test Title"
                assert cardkit_client._card_metadata["card_123"]["template_color"] == "blue"

    @pytest.mark.asyncio
    async def test_create_card_entity_failure(self, cardkit_client):
        """测试创建卡片实体失败"""
        mock_response = Mock()
        mock_response.success.return_value = False
        mock_response.code = 400
        mock_response.msg = "Bad request"

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.create_card_entity("Test content")

                assert result is None

    @pytest.mark.asyncio
    async def test_create_card_entity_exception(self, cardkit_client):
        """测试创建卡片实体异常"""
        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Network error")

            result = await cardkit_client.create_card_entity("Test content")

            assert result is None

    @pytest.mark.asyncio
    async def test_send_card_to_user_success(self, cardkit_client):
        """测试成功发送卡片消息给用户"""
        mock_response = Mock()
        mock_response.success.return_value = True

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.send_card_to_user(
                    "card_123",
                    "user_123",
                    "open_id"
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_send_card_to_user_failure(self, cardkit_client):
        """测试发送卡片消息失败"""
        mock_response = Mock()
        mock_response.success.return_value = False
        mock_response.code = 400
        mock_response.msg = "Send failed"

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.send_card_to_user(
                    "card_123",
                    "user_123"
                )

                assert result is False

    @pytest.mark.asyncio
    async def test_send_card_to_user_exception(self, cardkit_client):
        """测试发送卡片消息异常"""
        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Network error")

            result = await cardkit_client.send_card_to_user(
                "card_123",
                "user_123"
            )

            assert result is False

    @pytest.mark.asyncio
    async def test_update_card_content_success(self, cardkit_client):
        """测试成功更新卡片内容"""
        cardkit_client._card_metadata["card_123"] = {
            "title": "Original Title",
            "template_color": "grey"
        }

        mock_response = Mock()
        mock_response.success.return_value = True

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.update_card_content(
                    "card_123",
                    "New content"
                )

                assert result is True
                assert cardkit_client._card_sequence["card_123"] == 1

    @pytest.mark.asyncio
    async def test_update_card_content_with_custom_title(self, cardkit_client):
        """测试使用自定义标题更新卡片"""
        cardkit_client._card_metadata["card_123"] = {
            "title": "Original Title",
            "template_color": "grey"
        }

        mock_response = Mock()
        mock_response.success.return_value = True

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.update_card_content(
                    "card_123",
                    "New content",
                    title="Custom Title"
                )

                assert result is True

    @pytest.mark.asyncio
    async def test_update_card_content_cancelled(self, cardkit_client):
        """测试更新已取消的卡片"""
        cancelled_cards = {"card_123"}

        result = await cardkit_client.update_card_content(
            "card_123",
            "New content",
            cancelled_cards=cancelled_cards
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_update_card_content_failure_rollback(self, cardkit_client):
        """测试更新失败时回滚 sequence"""
        cardkit_client._card_sequence["card_123"] = 0

        mock_response = Mock()
        mock_response.success.return_value = False
        mock_response.code = 400
        mock_response.msg = "Update failed"

        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client

            with patch('asyncio.to_thread', new_callable=AsyncMock) as mock_to_thread:
                mock_to_thread.return_value = mock_response

                result = await cardkit_client.update_card_content(
                    "card_123",
                    "New content"
                )

                assert result is False
                assert cardkit_client._card_sequence["card_123"] == 0

    @pytest.mark.asyncio
    async def test_update_card_content_exception(self, cardkit_client):
        """测试更新卡片内容异常"""
        with patch.object(cardkit_client, '_get_client') as mock_get_client:
            mock_get_client.side_effect = Exception("Network error")

            result = await cardkit_client.update_card_content(
                "card_123",
                "New content"
            )

            assert result is False


class TestStreamingCardUpdater:
    """测试流式卡片更新器"""

    @pytest.fixture
    def cardkit_client(self):
        """创建 CardKit 客户端"""
        from src.feishu.cardkit_client import CardKitClient
        return CardKitClient("test_app_id", "test_app_secret")

    @pytest.fixture
    def streaming_updater(self, cardkit_client):
        """创建流式卡片更新器实例"""
        from src.feishu.cardkit_client import StreamingCardUpdater
        return StreamingCardUpdater(cardkit_client)

    def test_init(self, streaming_updater, cardkit_client):
        """测试初始化"""
        assert streaming_updater.cardkit == cardkit_client
        assert streaming_updater._state == {}

    def test_make_throttled_callback(self, streaming_updater):
        """测试创建节流回调函数"""
        callback = streaming_updater.make_throttled_callback(
            "card_123",
            lambda x: None
        )

        assert "card_123" in streaming_updater._state
        assert callable(callback)

    def test_throttled_callback_updates_on_last(self, streaming_updater):
        """测试最后一次更新时立即执行"""
        updates = []

        callback = streaming_updater.make_throttled_callback(
            "card_123",
            lambda x: updates.append(x)
        )

        callback("Final content", is_last=True)

        assert len(updates) == 1
        assert updates[0] == "Final content"

    def test_throttled_callback_respects_interval(self, streaming_updater):
        """测试节流间隔"""
        import time

        updates = []

        callback = streaming_updater.make_throttled_callback(
            "card_123",
            lambda x: updates.append(x),
            interval=1.0
        )

        # 第一次更新（节流间隔外）
        callback("Content 1", is_last=False)
        # 立即第二次更新（在节流间隔内，应该被跳过）
        callback("Content 2", is_last=False)

        # 只有第一次更新被执行
        assert len(updates) == 1
        assert updates[0] == "Content 1"

    def test_throttled_callback_updates_empty_content(self, streaming_updater):
        """测试空内容时显示占位符"""
        updates = []

        callback = streaming_updater.make_throttled_callback(
            "card_123",
            lambda x: updates.append(x)
        )

        callback(None, is_last=True)

        assert updates[0] == "正在处理..."

    def test_cleanup(self, streaming_updater, cardkit_client):
        """测试清理卡片状态"""
        cardkit_client._card_sequence["card_123"] = 5
        cardkit_client._card_metadata["card_123"] = {"title": "Test"}
        streaming_updater._state["card_123"] = {"last_update_time": 0}

        streaming_updater.cleanup("card_123")

        assert "card_123" not in streaming_updater._state
        assert "card_123" not in cardkit_client._card_sequence
        assert "card_123" not in cardkit_client._card_metadata

    def test_cleanup_nonexistent(self, streaming_updater):
        """测试清理不存在的卡片状态"""
        # 不应该抛出异常
        streaming_updater.cleanup("nonexistent_card")