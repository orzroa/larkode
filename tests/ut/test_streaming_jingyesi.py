"""
测试流式卡片输出 - 静夜思
"""
import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch
from src.streaming_output import StreamingOutputManager
from src.feishu.cardkit_client import CardKitClient


class TestStreamingOutputJingYeSi:
    """测试流式卡片输出 - 静夜思"""

    @pytest.fixture
    def mock_cardkit(self):
        """创建 mock CardKitClient"""
        cardkit = Mock(spec=CardKitClient)
        cardkit.create_card_entity = AsyncMock(return_value="test_card_123")
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
    async def test_streaming_jing_ye_si(self, streaming_manager, mock_cardkit):
        """测试流式输出静夜思"""

        # 静夜思诗句
        poems = [
            "床前明月光，",
            "疑是地上霜。",
            "举头望明月，",
            "低头思故乡。"
        ]

        # 1. 开始流式输出
        card_id = await streaming_manager.start_streaming(
            user_id="test_user",
            initial_message="准备输出静夜思...",
            title="古诗欣赏",
            template_color="blue"
        )

        assert card_id == "test_card_123"
        assert streaming_manager.is_active(card_id)

        # 2. 逐句发送诗句（模拟流式输出）
        accumulated_content = ""
        for i, verse in enumerate(poems, 1):
            accumulated_content += verse + "\n"

            # 重置 last_update_time 以避免节流
            streaming_manager._update_states[card_id]["last_update_time"] = 0

            # 更新卡片内容
            success = await streaming_manager.update_content(card_id, accumulated_content.strip())

            print(f"第 {i} 句发送: {verse} - {'✅' if success else '❌'}")
            assert success is True

            # 模拟延迟（模拟真实场景）
            await asyncio.sleep(0.1)

        # 3. 完成流式输出
        final_content = "**静夜思**\n\n" + accumulated_content.strip() + "\n\n—— 李白"
        success = await streaming_manager.finish_streaming(card_id, final_content)

        print(f"\n最终内容:\n{final_content}")
        print(f"流式输出完成: {'✅' if success else '❌'}")

        assert success is True
        assert not streaming_manager.is_active(card_id)  # 卡片已不活跃

        # 4. 验证调用次数
        # create_card_entity 应该被调用 1 次
        assert mock_cardkit.create_card_entity.call_count == 1

        # update_card_content 应该被调用 4 次（4 句诗）+ 1 次（最终完成）= 5 次
        # 但由于 finish_streaming 也调用 update_card_content，所以是 4 + 1 = 5 次
        assert mock_cardkit.update_card_content.call_count == 5

        print("\n✅ 静夜思流式输出测试通过！")

    @pytest.mark.asyncio
    async def test_streaming_with_sequence_management(self, streaming_manager, mock_cardkit):
        """测试 sequence 管理"""

        # 模拟 update_card_content 递增 sequence
        async def mock_update(card_id, content, cancelled_cards=None, title=None):
            mock_cardkit._card_sequence[card_id] = mock_cardkit._card_sequence.get(card_id, 0) + 1
            return True

        mock_cardkit.update_card_content = AsyncMock(side_effect=mock_update)

        # 模拟 sequence 从 1 开始
        mock_cardkit._card_sequence["test_card_123"] = 0

        card_id = await streaming_manager.start_streaming("test_user", "开始...")

        # 发送多次更新
        for i in range(1, 4):
            streaming_manager._update_states[card_id]["last_update_time"] = 0
            success = await streaming_manager.update_content(card_id, f"内容 {i}")
            assert success is True

            # 验证 sequence 递增
            # 注意：现在是在 update_card_content 内部管理，我们检查 _card_sequence
            if i == 1:
                assert mock_cardkit._card_sequence[card_id] == 1
            elif i == 2:
                assert mock_cardkit._card_sequence[card_id] == 2
            elif i == 3:
                assert mock_cardkit._card_sequence[card_id] == 3

        print(f"✅ Sequence 管理测试通过，最终 sequence: {mock_cardkit._card_sequence[card_id]}")

    @pytest.mark.asyncio
    async def test_streaming_error_handling(self, streaming_manager, mock_cardkit):
        """测试错误处理"""

        card_id = await streaming_manager.start_streaming("test_user", "开始...")

        # 模拟更新失败
        mock_cardkit.update_card_content.return_value = False

        streaming_manager._update_states[card_id]["last_update_time"] = 0
        success = await streaming_manager.update_content(card_id, "失败的内容")

        assert success is False

        # 验证失败后 sequence 不变
        current_seq = mock_cardkit._card_sequence.get(card_id, 0)

        # 再次尝试，仍用相同的 sequence
        streaming_manager._update_states[card_id]["last_update_time"] = 0
        success = await streaming_manager.update_content(card_id, "重试的内容")

        # sequence 应该还是不变（因为仍然失败）
        assert mock_cardkit._card_sequence.get(card_id, 0) == current_seq

        print(f"✅ 错误处理测试通过，失败后 sequence 保持不变")

    @pytest.mark.asyncio
    async def test_streaming_throttling(self, streaming_manager, mock_cardkit):
        """测试节流机制"""

        card_id = await streaming_manager.start_streaming("test_user", "开始...")

        # 第一次更新（应该成功）
        success1 = await streaming_manager.update_content(card_id, "内容 1")
        assert success1 is True

        # 立即第二次更新（应该被节流，但仍返回 True）
        success2 = await streaming_manager.update_content(card_id, "内容 2")
        assert success2 is True

        # 验证只调用了一次 update_card_content（第二次被节流）
        # 注意：节流不调用 API，所以只调用 1 次
        assert mock_cardkit.update_card_content.call_count == 1

        print(f"✅ 节流机制测试通过")


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "-s"])