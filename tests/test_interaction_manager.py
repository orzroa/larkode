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
    async def test_handle_codex_approval(self, interaction_manager, mock_feishu_api):
        from src.agent.approval import codex_approval_broker

        approval_id, future = codex_approval_broker.create("test_user")
        interaction_data = {
            "action_value": {
                "action": "codex_approval",
                "approval_id": approval_id,
                "decision": "accept",
            },
            "operator": {"open_id": "test_user"},
            "context": {},
        }

        result = await interaction_manager.handle_card_interaction(
            interaction_data, mock_feishu_api
        )

        assert result["resolved"] is True
        assert await asyncio.wait_for(future, timeout=1) == "accept"

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


class TestOptionCardDispatch:
    """测试选项卡（OptionCard）交互分发"""

    @pytest.fixture
    def interaction_manager(self):
        from src.interaction_manager import InteractionManager
        return InteractionManager()

    @pytest.fixture
    def mock_feishu_api(self):
        api = Mock()
        api.send_message = AsyncMock(return_value="msg_id_xyz")
        return api

    @pytest.mark.asyncio
    async def test_option_card_select_ws(self, interaction_manager, mock_feishu_api):
        """选项卡 ws 类别 select 应触发工作空间切换（含文字确认 + handler 回调）"""
        interaction_data = {
            "action_value": {"opt": "select", "cat": "ws", "key": "3", "page": 1},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_select",
            new=AsyncMock(),
        ) as mock_select, patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_option_card",
            new=AsyncMock(),
        ):
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result is not None
        assert result["type"] == "option_card_select"
        assert result["category"] == "ws"
        assert result["key"] == "3"
        mock_select.assert_awaited_once()
        # 检查传参
        call_args = mock_select.await_args
        assert call_args.args[0] == "ou_test123"
        assert call_args.args[1] == "3"
        # 文字确认消息至少被发送 1 次（"正在切换..." 提示）
        assert mock_feishu_api.send_message.await_count >= 1
        # send_message_func 应可调用
        send_func = call_args.args[2]
        await send_func("ou_test123", card={"foo": "bar"})
        # 又多了一次 send_message（卡片）
        assert mock_feishu_api.send_message.await_count >= 2

    @pytest.mark.asyncio
    async def test_option_card_page_ws(self, interaction_manager, mock_feishu_api):
        """选项卡 ws 类别 page 应触发翻页重渲染"""
        interaction_data = {
            "action_value": {"opt": "page", "cat": "ws", "page": 2},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_option_card",
            new=AsyncMock(),
        ) as mock_show, patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_select",
            new=AsyncMock(),
        ):
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result is not None
        assert result["type"] == "option_card_page"
        assert result["category"] == "ws"
        assert result["page"] == 2
        mock_show.assert_awaited_once_with("ou_test123", mock_show.await_args.args[1], page=2)

    @pytest.mark.asyncio
    async def test_option_card_select_model(self, interaction_manager, mock_feishu_api):
        """选项卡 model 类别 select 应触发模型切换"""
        interaction_data = {
            "action_value": {"opt": "select", "cat": "model", "key": "5", "page": 1},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.ccr_commands.CCRCommands.handle_model_select",
            new=AsyncMock(),
        ) as mock_select, patch(
            "src.handlers.ccr_commands.CCRCommands.show_model_option_card",
            new=AsyncMock(),
        ):
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result is not None
        assert result["type"] == "option_card_select"
        assert result["category"] == "model"
        assert result["key"] == "5"
        mock_select.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_option_card_page_model(self, interaction_manager, mock_feishu_api):
        """选项卡 model 类别 page 应触发翻页重渲染"""
        interaction_data = {
            "action_value": {"opt": "page", "cat": "model", "page": 3},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.ccr_commands.CCRCommands.show_model_option_card",
            new=AsyncMock(),
        ) as mock_show, patch(
            "src.handlers.ccr_commands.CCRCommands.handle_model_select",
            new=AsyncMock(),
        ):
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result is not None
        assert result["type"] == "option_card_page"
        assert result["category"] == "model"
        assert result["page"] == 3
        mock_show.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_option_card_unknown_cat(self, interaction_manager, mock_feishu_api):
        """未知的 cat 应返回 None，不抛出异常"""
        interaction_data = {
            "action_value": {"opt": "select", "cat": "unknown", "key": "1"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        result = await interaction_manager.handle_card_interaction(
            interaction_data, mock_feishu_api
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_stale_codex_think_card_returns_explicit_chat_error(
        self, interaction_manager, mock_feishu_api
    ):
        """模型切换后点击旧 Think 卡，应明确提示重新发送 #think。"""
        interaction_data = {
            "action_value": {
                "opt": "select",
                "cat": "codex_effort",
                "key": "high",
                "model_id": "gpt-5.6-luna",
            },
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"},
        }
        send_card = AsyncMock(return_value=("om_error", None))
        stale_error = ValueError(
            "该 Think 卡片属于模型 gpt-5.6-luna，当前模型已切换为 "
            "gpt-5.6-terra，请重新发送 #think"
        )

        with patch(
            "src.handlers.codex_commands.CodexCommands.handle_effort_select",
            new=AsyncMock(side_effect=stale_error),
        ), patch("src.card_dispatcher.CardDispatcher.send_card", send_card):
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result["type"] == "option_card_error"
        assert result["error"] == "原 Think 卡片已因模型切换失效，请重新发送 #think"
        mock_feishu_api.send_message.assert_awaited_once_with(
            "ou_test123", result["error"]
        )
        assert send_card.await_args.kwargs["title"] == "Think 卡片已失效"
        assert send_card.await_args.kwargs["content"] == result["error"]

    @pytest.mark.asyncio
    async def test_option_card_select_ws_group(self, interaction_manager, mock_feishu_api):
        """选项卡 ws_group 类别 select 应展示该一级目录的 level-2 内容"""
        interaction_data = {
            "action_value": {"opt": "select", "cat": "ws_group", "key": "github", "page": 1},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_group_contents_option_card",
            new=AsyncMock(),
        ) as mock_show:
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result is not None
        assert result["type"] == "option_card_select"
        assert result["category"] == "ws_group"
        assert result["key"] == "github"
        mock_show.assert_awaited_once()
        call_args = mock_show.await_args
        assert call_args.args[0] == "ou_test123"
        assert call_args.args[1] == "github"

    @pytest.mark.asyncio
    async def test_option_card_select_ws_parent(self, interaction_manager, mock_feishu_api):
        """选项卡 ws_parent 类别 select 应切换到一级目录（含文字确认）"""
        interaction_data = {
            "action_value": {"opt": "select", "cat": "ws_parent", "key": "github"},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_parent_select",
            new=AsyncMock(),
        ) as mock_parent:
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result is not None
        assert result["type"] == "option_card_select"
        assert result["category"] == "ws_parent"
        assert result["key"] == "github"
        mock_parent.assert_awaited_once_with("ou_test123", "github", mock_parent.await_args.args[2])
        # 文字确认消息应至少 1 次被送出
        assert mock_feishu_api.send_message.await_count >= 1

    @pytest.mark.asyncio
    async def test_option_card_quick_confirm_text_first(self, interaction_manager, mock_feishu_api):
        """点击 select 时，先发"正在切换..."文字消息给用户即时反馈"""
        mock_feishu_api.send_message.reset_mock()
        interaction_data = {
            "action_value": {"opt": "select", "cat": "model", "key": "deepseek", "page": 1},
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.ccr_commands.CCRCommands.handle_model_select",
            new=AsyncMock(),
        ):
            await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        # 至少一次 send_message 携带"⏳"提示文本
        texts = [
            call.args[1] for call in mock_feishu_api.send_message.call_args_list
            if isinstance(call.args[1], str) and "⏳" in call.args[1]
        ]
        assert texts, "select 操作前应先发文字确认"

    @pytest.mark.asyncio
    async def test_send_message_func_serializes_normalized_card(self, interaction_manager, mock_feishu_api):
        """send_message_func 应能正确把 NormalizedCard 序列化成飞书 V2 schema 字符串"""
        from src.interfaces.im_platform import NormalizedCard
        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_select",
            new=AsyncMock(),
        ) as mock_select, patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_option_card",
            new=AsyncMock(),
        ):
            interaction_data = {
                "action_value": {"opt": "select", "cat": "ws", "key": "1", "page": 1},
                "form_value": None,
                "operator": {"open_id": "ou_user"},
                "context": {"open_message_id": "msg_1"}
            }
            await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        send_func = mock_select.await_args.args[2]
        card = NormalizedCard(
            card_type="success",
            title="成功",
            content="已切换",
            template_color="green",
        )
        await send_func("ou_user", card=card)
        # 最后一次 send_message 调用应是 NormalizedCard 转成的 V2 schema
        last_call = mock_feishu_api.send_message.call_args_list[-1]
        import json
        payload = json.loads(last_call.args[1])
        assert payload["schema"] == "2.0"
        assert payload["header"]["title"]["content"] == "成功"
        assert payload["header"]["template"] == "green"

    @pytest.mark.asyncio
    async def test_option_card_action_value_from_string_json(self, interaction_manager, mock_feishu_api):
        """action.value 以 JSON 字符串形式传入也应正确分发（飞书偶尔会这样）"""
        interaction_data = {
            "action_value": '{"opt": "select", "cat": "ws", "key": "2", "page": 1}',
            "form_value": None,
            "operator": {"open_id": "ou_test123"},
            "context": {"open_message_id": "msg_123"}
        }

        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_select",
            new=AsyncMock(),
        ) as mock_select, patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_option_card",
            new=AsyncMock(),
        ):
            result = await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        assert result == {"type": "option_card_select", "category": "ws", "key": "2"}
        mock_select.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_send_message_func_forwards_dict_card(self, interaction_manager, mock_feishu_api):
        """send_message_func 应将 dict 卡片 JSON 化后通过 feishu_api.send_message 发送"""
        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_select",
            new=AsyncMock(),
        ) as mock_select, patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_option_card",
            new=AsyncMock(),
        ):
            interaction_data = {
                "action_value": {"opt": "select", "cat": "ws", "key": "1", "page": 1},
                "form_value": None,
                "operator": {"open_id": "ou_user"},
                "context": {"open_message_id": "msg_1"}
            }
            await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        # 抓取 send_func
        send_func = mock_select.await_args.args[2]
        before = mock_feishu_api.send_message.await_count
        await send_func("ou_user", card={
            "schema": "2.0",
            "header": {"title": {"tag": "plain_text", "content": "测试选项"}},
            "body": {},
        })
        after = mock_feishu_api.send_message.await_count
        assert after - before == 1, "send_message_func 应将 dict 卡片转发给 feishu_api.send_message"
        # 最近一次调用：第二个位置参数应是序列化后的字符串
        last_call = mock_feishu_api.send_message.call_args_list[-1]
        assert last_call.args[0] == "ou_user"
        import json
        payload = json.loads(last_call.args[1])
        assert payload["header"]["title"]["content"].startswith("[")
        assert payload["body"]["elements"][0]["content"].startswith("📨 卡片编号:")

    @pytest.mark.asyncio
    async def test_send_message_func_forwards_text(self, interaction_manager, mock_feishu_api):
        """send_message_func 应直接将文本转发给 feishu_api.send_message"""
        with patch(
            "src.handlers.workspace_commands.WorkspaceCommands.handle_workspace_select",
            new=AsyncMock(),
        ) as mock_select, patch(
            "src.handlers.workspace_commands.WorkspaceCommands.show_workspace_option_card",
            new=AsyncMock(),
        ):
            interaction_data = {
                "action_value": {"opt": "select", "cat": "ws", "key": "1", "page": 1},
                "form_value": None,
                "operator": {"open_id": "ou_user"},
                "context": {"open_message_id": "msg_1"}
            }
            await interaction_manager.handle_card_interaction(
                interaction_data, mock_feishu_api
            )

        send_func = mock_select.await_args.args[2]
        await send_func("ou_user", message="hello")
        # 最近一次 send_message 调用应是 (ou_user, "hello")
        last_call = mock_feishu_api.send_message.call_args_list[-1]
        assert last_call.args == ("ou_user", "hello")
