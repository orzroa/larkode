"""
测试交互管理器
"""
import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from pathlib import Path
import asyncio
import tempfile
import os

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestInteractionManager:
    """测试交互管理器"""

    @pytest.fixture
    def interaction_manager(self):
        """创建交互管理器实例"""
        from src.interaction_manager import InteractionManager
        return InteractionManager()

    @pytest.fixture
    def mock_feishu_api(self):
        """创建模拟的飞书 API"""
        return Mock()

    @pytest.mark.asyncio
    async def test_init(self, interaction_manager):
        """测试初始化"""
        assert interaction_manager._pending_interactions == {}
        assert interaction_manager._interaction_results == {}
        assert interaction_manager._result_events == {}
        assert isinstance(interaction_manager._lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_handle_card_interaction_escape(self, interaction_manager, mock_feishu_api):
        """测试处理 Escape 交互"""
        interaction_data = {
            "action_value": {"action": "escape"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

        assert result is not None
        assert result["type"] == "escape"
        assert result["user_id"] == "ou_test123"
        assert result["message_id"] == "msg_123"

    @pytest.mark.asyncio
    async def test_handle_card_interaction_confirm_yes(self, interaction_manager, mock_feishu_api):
        """测试处理确认 Yes 交互"""
        interaction_data = {
            "action_value": {"action": "confirm", "value": "yes"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

        assert result is not None
        assert result["type"] == "confirm"
        assert result["value"] == "yes"

    @pytest.mark.asyncio
    async def test_handle_card_interaction_confirm_no(self, interaction_manager, mock_feishu_api):
        """测试处理确认 No 交互"""
        interaction_data = {
            "action_value": {"action": "confirm", "value": "no"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

        assert result is not None
        assert result["type"] == "confirm"
        assert result["value"] == "no"

    @pytest.mark.asyncio
    async def test_handle_card_interaction_form_select(self, interaction_manager, mock_feishu_api):
        """测试处理单选表单提交"""
        interaction_data = {
            "action_value": {},
            "form_value": {"select_option": "option1"},
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

        assert result is not None
        assert result["type"] == "select"
        assert result["value"] == "option1"

    @pytest.mark.asyncio
    async def test_handle_card_interaction_form_multi_select(self, interaction_manager, mock_feishu_api):
        """测试处理多选表单提交"""
        interaction_data = {
            "action_value": {},
            "form_value": {"multi_select_options": ["option1", "option2"]},
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

        assert result is not None
        assert result["type"] == "multi_select"
        assert result["value"] == ["option1", "option2"]

    @pytest.mark.asyncio
    async def test_handle_card_interaction_form_multi_select_string(self, interaction_manager, mock_feishu_api):
        """测试处理多选表单提交（字符串值）"""
        interaction_data = {
            "action_value": {},
            "form_value": {"multi_select_options": "single_option"},
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

        assert result is not None
        assert result["type"] == "multi_select"
        assert result["value"] == ["single_option"]

    @pytest.mark.asyncio
    async def test_handle_card_interaction_no_user_id(self, interaction_manager, mock_feishu_api):
        """测试没有用户 ID 的情况"""
        interaction_data = {
            "action_value": {"action": "escape"},
            "form_value": None,
            "operator": {},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)
        assert result is None

    @pytest.mark.asyncio
    async def test_handle_card_interaction_unknown_type(self, interaction_manager, mock_feishu_api):
        """测试未知的交互类型"""
        interaction_data = {
            "action_value": {"action": "unknown"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_wait_for_interaction_result(self, interaction_manager):
        """测试设置和等待交互结果"""
        task_id = "task_123"

        # 启动等待任务
        async def wait_task():
            return await interaction_manager.wait_for_interaction(task_id, timeout=1.0)

        # 并行执行
        wait_future = asyncio.create_task(wait_task())

        # 等待一小段时间确保等待任务已经开始
        await asyncio.sleep(0.01)

        # 设置结果
        await interaction_manager.set_interaction_result(task_id, {"value": "test"})

        # 等待结果
        result = await wait_future

        assert result is not None
        assert result["value"] == "test"

    @pytest.mark.asyncio
    async def test_wait_for_interaction_timeout(self, interaction_manager):
        """测试等待交互超时"""
        task_id = "task_456"

        # 不设置结果，等待超时
        result = await interaction_manager.wait_for_interaction(task_id, timeout=0.1)

        assert result is None

    @pytest.mark.asyncio
    async def test_write_interaction_response(self, interaction_manager, mock_feishu_api):
        """测试写入交互响应文件"""
        import src.interaction_manager as im_module

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = Path(f.name)

        try:
            im_module.set_interaction_response_file_path(temp_path)

            interaction_data = {
                "action_value": {"action": "escape"},
                "form_value": None,
                "operator": {"open_id": "ou_test123"},
                "context": {"open_message_id": "msg_123"}
            }

            await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)

            # 验证文件写入
            import json
            with open(temp_path, 'r') as f:
                data = json.load(f)

            assert data["message_id"] == "msg_123"
            assert data["type"] == "escape"

        finally:
            os.unlink(temp_path)
            im_module.set_interaction_response_file_path(None)

    @pytest.mark.asyncio
    async def test_write_interaction_response_no_path(self, interaction_manager, mock_feishu_api):
        """测试没有设置文件路径时的写入"""
        import src.interaction_manager as im_module
        im_module.set_interaction_response_file_path(None)

        interaction_data = {
            "action_value": {"action": "escape"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        # 应该不抛出异常
        result = await interaction_manager.handle_card_interaction(interaction_data, mock_feishu_api)
        assert result is not None

    @pytest.mark.asyncio
    async def test_remove_interaction(self, interaction_manager):
        """测试移除交互"""
        task_id = "task_789"

        # 添加一个结果
        await interaction_manager.set_interaction_result(task_id, {"value": "test"})

        # 创建事件循环来运行 remove_interaction
        loop = asyncio.get_event_loop()

        # 使用异步方法直接移除
        await interaction_manager._remove_interaction(task_id)

        # 验证结果被移除
        assert task_id not in interaction_manager._interaction_results


class TestInteractionManagerGlobal:
    """测试全局实例"""

    def test_global_instance_exists(self):
        """测试全局实例存在"""
        from src.interaction_manager import interaction_manager
        assert interaction_manager is not None
        from src.interaction_manager import InteractionManager
        assert isinstance(interaction_manager, InteractionManager)