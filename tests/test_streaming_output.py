"""
流式输出管理器测试
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.streaming_output import StreamingOutputManager, create_streaming_manager
from src.feishu.cardkit_client import CardKitClient


class TestStreamingOutputManager:
    """StreamingOutputManager 测试"""

    @pytest.fixture
    def mock_cardkit(self):
        """创建 mock CardKitClient"""
        cardkit = Mock(spec=CardKitClient)
        cardkit.create_card_entity = AsyncMock(return_value="test_card_id")
        cardkit.update_card_content = AsyncMock(return_value=True)
        cardkit.send_card_to_user = AsyncMock(return_value=True)
        cardkit._card_sequence = {}
        cardkit._card_metadata = {}
        return cardkit

    @pytest.fixture
    def streaming_manager(self, mock_cardkit):
        """创建 StreamingOutputManager 实例"""
        manager = StreamingOutputManager(mock_cardkit)
        yield manager
        # 清理单例
        StreamingOutputManager.reset_instance()

    @pytest.mark.asyncio
    async def test_start_streaming_success(self, streaming_manager):
        """测试成功启动流式输出"""
        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")

        assert card_id == "test_card_id"
        assert card_id in streaming_manager._update_states
        assert streaming_manager._update_states[card_id]["user_id"] == "user_123"

    @pytest.mark.asyncio
    async def test_start_streaming_create_card_failed(self, streaming_manager, mock_cardkit):
        """测试创建卡片失败"""
        mock_cardkit.create_card_entity.return_value = None

        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")

        assert card_id is None
        assert "test_card_id" not in streaming_manager._update_states

    @pytest.mark.asyncio
    async def test_update_content_success(self, streaming_manager):
        """测试更新卡片内容"""
        # 先启动流式输出
        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")
        streaming_manager._update_states[card_id]["last_update_time"] = 0  # 重置时间以避免节流

        # 更新内容
        success = await streaming_manager.update_content(card_id, "新内容")

        assert success is True

    @pytest.mark.asyncio
    async def test_update_content_throttled(self, streaming_manager):
        """测试更新内容被节流"""
        # 先启动流式输出
        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")

        # 第一次更新
        success1 = await streaming_manager.update_content(card_id, "新内容1")

        # 立即第二次更新（会被节流）
        success2 = await streaming_manager.update_content(card_id, "新内容2")

        assert success1 is True
        assert success2 is True  # 节流不返回失败，只是跳过更新

    @pytest.mark.asyncio
    async def test_update_content_unknown_card(self, streaming_manager):
        """测试更新未知卡片"""
        success = await streaming_manager.update_content("unknown_card", "内容")

        assert success is False

    @pytest.mark.asyncio
    async def test_finish_streaming_success(self, streaming_manager, mock_cardkit):
        """测试完成流式输出"""
        # 先启动流式输出
        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")

        # 完成流式输出
        success = await streaming_manager.finish_streaming(card_id, "最终内容")

        assert success is True
        assert card_id not in streaming_manager._update_states
        assert card_id not in mock_cardkit._card_sequence

    @pytest.mark.asyncio
    async def test_handle_error(self, streaming_manager, mock_cardkit):
        """测试错误处理"""
        # 先启动流式输出
        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")

        # 处理错误
        success = await streaming_manager.handle_error(card_id, "发生错误")

        assert success is True
        assert card_id not in streaming_manager._update_states

    @pytest.mark.asyncio
    async def test_cleanup(self, streaming_manager, mock_cardkit):
        """测试清理资源"""
        # 先启动流式输出
        card_id = await streaming_manager.start_streaming("user_123", "正在处理...")

        # 手动添加 sequence
        mock_cardkit._card_sequence[card_id] = 5

        # 清理
        streaming_manager.cleanup(card_id)

        assert card_id not in streaming_manager._update_states
        assert card_id not in mock_cardkit._card_sequence

    def test_is_active(self, streaming_manager):
        """测试检查卡片是否活跃"""
        assert streaming_manager.is_active("unknown_card") is False

        # 手动添加状态
        streaming_manager._update_states["test_card"] = {}

        assert streaming_manager.is_active("test_card") is True


class TestCreateStreamingManager:
    """create_streaming_manager 工厂函数测试"""

    @patch('src.streaming_output.get_settings')
    def test_create_manager_disabled(self, mock_get_settings):
        """测试流式输出未启用"""
        mock_settings = Mock()
        mock_settings.STREAMING_OUTPUT_ENABLED = False
        mock_get_settings.return_value = mock_settings

        manager = create_streaming_manager()

        assert manager is None

    @patch('src.streaming_output.get_settings')
    def test_create_manager_missing_config(self, mock_get_settings):
        """测试配置不完整"""
        mock_settings = Mock()
        mock_settings.STREAMING_OUTPUT_ENABLED = True
        mock_settings.FEISHU_APP_ID = ""
        mock_settings.FEISHU_APP_SECRET = ""
        mock_get_settings.return_value = mock_settings

        manager = create_streaming_manager()

        assert manager is None

    @patch('src.streaming_output.get_settings')
    @patch('src.streaming_output.CardKitClient')
    def test_create_manager_success(self, mock_cardkit_class, mock_get_settings):
        """测试成功创建管理器"""
        # 清理可能存在的单例
        StreamingOutputManager.reset_instance()

        mock_settings = Mock()
        mock_settings.STREAMING_OUTPUT_ENABLED = True
        mock_settings.FEISHU_APP_ID = "test_app_id"
        mock_settings.FEISHU_APP_SECRET = "test_secret"
        mock_settings.STREAMING_UPDATE_INTERVAL = 1.0
        mock_get_settings.return_value = mock_settings

        manager = create_streaming_manager()

        assert manager is not None
        assert isinstance(manager, StreamingOutputManager)
        mock_cardkit_class.assert_called_once_with(
            app_id="test_app_id",
            app_secret="test_secret"
        )

        # 清理单例
        StreamingOutputManager.reset_instance()