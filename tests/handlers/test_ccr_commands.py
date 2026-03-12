"""
测试 CCR 模型切换命令处理器
"""
import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock, AsyncMock
from pathlib import Path

# 添加项目根目录到路径
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCCRCommands:
    """测试 CCR 模型切换命令处理器"""

    @pytest.fixture
    def ccr(self):
        """创建 CCRCommands 实例"""
        from src.handlers.ccr_commands import CCRCommands
        return CCRCommands()

    @pytest.fixture
    def mock_config(self):
        """模拟配置文件内容"""
        return {
            "Providers": [
                {
                    "name": "deepseek",
                    "models": ["deepseek-chat", "deepseek-coder"]
                },
                {
                    "name": "anthropic",
                    "models": ["claude-opus-4-6", "claude-sonnet-4-6"]
                }
            ],
            "Router": {
                "default": "deepseek,deepseek-chat"
            }
        }

    def test_extract_models_from_providers(self, ccr, mock_config):
        """测试从配置中提取模型列表"""
        models = ccr.extract_models_from_providers(mock_config)

        # 验证模型数量
        assert len(models) == 4

        # 验证模型格式
        assert "anthropic,claude-opus-4-6" in models
        assert "anthropic,claude-sonnet-4-6" in models
        assert "deepseek,deepseek-chat" in models
        assert "deepseek,deepseek-coder" in models

    def test_extract_models_skips_comments(self, ccr):
        """测试跳过以 # 开头的注释模型"""
        config = {
            "Providers": [
                {
                    "name": "test",
                    "models": ["#this-is-comment", "real-model"]
                }
            ]
        }
        models = ccr.extract_models_from_providers(config)

        assert len(models) == 1
        assert models[0] == "test,real-model"

    def test_get_current_model(self, ccr, mock_config):
        """测试获取当前模型"""
        current = ccr.get_current_model(mock_config)
        assert current == "deepseek,deepseek-chat"

    def test_get_current_model_none(self, ccr):
        """测试配置中没有当前模型"""
        config = {"Router": {}}
        current = ccr.get_current_model(config)
        assert current is None

    def test_find_model_by_index(self, ccr):
        """测试通过序号查找模型"""
        models = ["model-a", "model-b", "model-c"]

        assert ccr.find_model_by_input("1", models) == "model-a"
        assert ccr.find_model_by_input("2", models) == "model-b"
        assert ccr.find_model_by_input("3", models) == "model-c"

        # 超出范围
        assert ccr.find_model_by_input("0", models) is None
        assert ccr.find_model_by_input("4", models) is None

        # 带 * 后缀（当前标记）
        assert ccr.find_model_by_input("2*", models) == "model-b"

    def test_find_model_by_full_format(self, ccr):
        """测试通过完整格式查找模型"""
        models = ["deepseek,deepseek-chat", "anthropic,claude-opus-4-6"]

        # 完整格式直接返回
        assert ccr.find_model_by_input("deepseek,deepseek-chat", models) == "deepseek,deepseek-chat"
        assert ccr.find_model_by_input("anthropic,claude-opus-4-6", models) == "anthropic,claude-opus-4-6"

    def test_find_model_invalid_input(self, ccr):
        """测试无效输入"""
        models = ["model-a", "model-b"]

        # 无效格式（没有逗号也不是数字）
        assert ccr.find_model_by_input("invalid", models) is None

    @pytest.mark.asyncio
    async def test_handle_model_show_list(self, ccr, mock_config):
        """测试显示模型列表（无参数）"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=mock_config):
            await ccr.handle_model_command("test_user", "", send_mock)

        # 验证发送了消息
        assert send_mock.called
        call_args = send_mock.call_args
        assert call_args[0][0] == "test_user"
        card = call_args[1]['card']
        assert "模型列表" in card.title
        assert "deepseek,deepseek-chat" in card.content

    @pytest.mark.asyncio
    async def test_handle_model_switch_by_index(self, ccr, mock_config):
        """测试通过序号切换模型"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=mock_config), \
             patch.object(ccr, 'update_default_model', return_value=True), \
             patch.object(ccr, 'restart_ccr', return_value=(True, "CCR 服务重启完成")):

            # 序号1是 anthropic,claude-opus-4-6（排序后）
            await ccr.handle_model_command("test_user", "1", send_mock)

        # 验证发送了成功消息
        assert send_mock.called
        call_args = send_mock.call_args
        card = call_args[1]['card']
        assert "模型切换成功" in card.content
        assert "anthropic,claude-opus-4-6" in card.content

    @pytest.mark.asyncio
    async def test_handle_model_switch_by_full_format(self, ccr, mock_config):
        """测试通过完整格式切换模型"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=mock_config), \
             patch.object(ccr, 'update_default_model', return_value=True), \
             patch.object(ccr, 'restart_ccr', return_value=(True, "CCR 服务重启完成")):

            await ccr.handle_model_command(
                "test_user",
                "anthropic,claude-sonnet-4-6",
                send_mock
            )

        # 验证发送了成功消息
        assert send_mock.called
        call_args = send_mock.call_args
        card = call_args[1]['card']
        assert "模型切换成功" in card.content
        assert "anthropic,claude-sonnet-4-6" in card.content

    @pytest.mark.asyncio
    async def test_handle_model_already_current(self, ccr, mock_config):
        """测试切换到当前模型"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=mock_config):
            # 当前模型是 deepseek,deepseek-chat（序号 2 或 3，取决于排序）
            await ccr.handle_model_command("test_user", "deepseek,deepseek-chat", send_mock)

        # 验证发送了提示消息
        assert send_mock.called
        call_args = send_mock.call_args
        card = call_args[1]['card']
        assert "当前已是此模型" in card.content

    @pytest.mark.asyncio
    async def test_handle_model_invalid_index(self, ccr, mock_config):
        """测试无效序号"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=mock_config):
            await ccr.handle_model_command("test_user", "99", send_mock)

        # 验证发送了错误消息
        assert send_mock.called
        call_args = send_mock.call_args
        card = call_args[1]['card']
        assert "无效输入" in card.content

    @pytest.mark.asyncio
    async def test_handle_model_config_not_found(self, ccr):
        """测试配置文件不存在"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=None):
            await ccr.handle_model_command("test_user", "", send_mock)

        # 验证发送了错误消息
        assert send_mock.called
        call_args = send_mock.call_args
        card = call_args[1]['card']
        assert "配置文件不存在" in card.content

    @pytest.mark.asyncio
    async def test_handle_model_restart_failed(self, ccr, mock_config):
        """测试重启失败"""
        send_mock = AsyncMock()

        with patch.object(ccr, 'load_config', return_value=mock_config), \
             patch.object(ccr, 'update_default_model', return_value=True), \
             patch.object(ccr, 'restart_ccr', return_value=(False, "未找到 ccr 命令")):

            # 序号1是 anthropic,claude-opus-4-6（不是当前模型）
            await ccr.handle_model_command("test_user", "1", send_mock)

        # 验证发送了错误消息
        assert send_mock.called
        call_args = send_mock.call_args
        card = call_args[1]['card']
        assert "重启失败" in card.content or "未找到 ccr 命令" in card.content

    def test_restart_ccr_success(self, ccr):
        """测试重启 CCR 成功"""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch('subprocess.run', return_value=mock_result):
            success, msg = ccr.restart_ccr()

        assert success is True
        assert "重启完成" in msg

    def test_restart_ccr_fallback_to_start(self, ccr):
        """测试重启失败后尝试启动"""
        mock_fail = Mock()
        mock_fail.returncode = 1

        mock_success = Mock()
        mock_success.returncode = 0

        with patch('subprocess.run', side_effect=[mock_fail, mock_success]):
            success, msg = ccr.restart_ccr()

        assert success is True
        assert "启动完成" in msg

    def test_restart_ccr_not_found(self, ccr):
        """测试 ccr 命令不存在"""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            success, msg = ccr.restart_ccr()

        assert success is False
        assert "未找到 ccr 命令" in msg