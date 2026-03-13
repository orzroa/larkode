"""
测试流式卡片结束逻辑
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.streaming_output import StreamingOutputManager
from src.feishu.cardkit_client import CardKitClient


class TestStreamingCardTermination:
    """测试流式卡片结束逻辑"""

    @pytest.fixture
    def mock_cardkit(self):
        """创建 mock CardKitClient"""
        cardkit = Mock(spec=CardKitClient)
        cardkit.create_card_entity = AsyncMock(return_value="new_card_123")
        cardkit.send_card_to_user = AsyncMock(return_value=True)
        cardkit.update_card_content = AsyncMock(return_value=True)
        cardkit._card_sequence = {}
        cardkit._card_metadata = {}
        return cardkit

    @pytest.fixture
    def streaming_manager(self, mock_cardkit):
        """创建 StreamingOutputManager 实例（重置单例）"""
        # 重置单例
        StreamingOutputManager.reset_instance()
        manager = StreamingOutputManager(mock_cardkit)
        yield manager
        # 清理单例
        StreamingOutputManager.reset_instance()

    @pytest.mark.asyncio
    async def test_old_card_termination_message(self, streaming_manager, mock_cardkit):
        """测试旧卡片结束时添加提示消息"""

        # 1. 创建第一个卡片
        old_card_id = await streaming_manager.start_streaming(
            user_id="test_user",
            initial_message="正在处理第一个命令...",
            title="命令处理",
            template_color="blue"
        )

        assert old_card_id == "new_card_123"
        assert streaming_manager._active_card_id == old_card_id

        # 模拟旧卡片有一些内容
        streaming_manager._update_states[old_card_id]["last_content"] = "这是第一个命令的输出内容"

        # 2. 创建第二个卡片（应该结束第一个卡片）
        # Mock 返回新的 card_id
        mock_cardkit.create_card_entity = AsyncMock(return_value="new_card_456")

        new_card_id = await streaming_manager.start_streaming(
            user_id="test_user",
            initial_message="正在处理第二个命令...",
            title="命令处理",
            template_color="blue"
        )

        assert new_card_id == "new_card_456"
        assert streaming_manager._active_card_id == new_card_id

        # 3. 验证旧卡片被标记为已取消
        assert old_card_id in streaming_manager._cancelled_cards, "旧卡片应该被标记为已取消"

        # 4. 验证旧卡片被更新了提示消息
        # update_card_content 应该被调用，且内容包含提示消息
        assert mock_cardkit.update_card_content.called

        # 获取最后一次调用旧卡片的参数
        calls = mock_cardkit.update_card_content.call_args_list

        # 查找对旧卡片的调用
        old_card_update = None
        for call in calls:
            if call[0][0] == "new_card_123":  # 第一个参数是 card_id
                old_card_update = call
                break

        assert old_card_update is not None, "应该调用了旧卡片的更新"

        # 验证内容包含提示消息
        updated_content = old_card_update[0][1]  # 第二个参数是 content
        assert "新的流式卡片已创建" in updated_content, f"内容应包含提示消息，实际内容: {updated_content}"

        # 5. 验证后续对旧卡片的更新会被拒绝
        mock_cardkit.update_card_content.reset_mock()
        result = await streaming_manager.update_content(old_card_id, "后续更新")
        assert result is False, "已取消的卡片应该拒绝更新"
        assert not mock_cardkit.update_card_content.called, "已取消的卡片不应该调用API更新"

        # 6. 验证对旧卡片的完成也会被拒绝
        mock_cardkit.update_card_content.reset_mock()
        result = await streaming_manager.finish_streaming(old_card_id, "最终内容")
        assert result is False, "已取消的卡片应该拒绝完成"
        assert not mock_cardkit.update_card_content.called, "已取消的卡片不应该调用API完成"

        print(f"\n✅ 测试通过！旧卡片内容末尾包含提示消息，且后续更新被阻止")
        print(f"更新的内容:\n{updated_content}")

    @pytest.mark.asyncio
    async def test_no_old_card_scenario(self, streaming_manager, mock_cardkit):
        """测试没有旧卡片的情况"""

        # 创建第一个卡片（没有旧卡片）
        card_id = await streaming_manager.start_streaming(
            user_id="test_user",
            initial_message="开始处理...",
            title="命令处理",
            template_color="blue"
        )

        assert card_id == "new_card_123"

        # 没有旧卡片，update_card_content 不应该被调用（除了正常的流式更新）
        # 这里的 update_card_content 应该只被新卡片创建时的后续更新调用
        # 初始创建时不调用 update_card_content
        assert streaming_manager._active_card_id == card_id

        print(f"\n✅ 测试通过！没有旧卡片时正常创建新卡片")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])