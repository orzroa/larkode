"""
测试交互监控器
"""
import pytest
import json
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock, mock_open
from pathlib import Path

import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestInteractionMonitor:
    """测试交互监控器"""

    @pytest.fixture
    def mock_interaction_manager(self):
        """创建模拟的交互管理器"""
        manager = Mock()
        manager._pending_interactions = {}
        return manager

    @pytest.fixture
    def interaction_monitor(self, mock_interaction_manager):
        """创建交互监控器实例"""
        from src.handlers.interaction_monitor import InteractionMonitor
        return InteractionMonitor(mock_interaction_manager)

    @pytest.mark.asyncio
    async def test_handle_interaction_request(self, interaction_monitor, mock_interaction_manager):
        """测试处理交互请求"""
        request = {
            "message_id": "msg_123",
            "interaction_type": "button_click"
        }

        await interaction_monitor.handle_interaction_request(request)

        # 验证交互请求已存储
        assert len(mock_interaction_manager._pending_interactions) > 0

    def test_wait_for_card_interaction_returns_empty(self, interaction_monitor):
        """测试等待卡片交互返回空字典"""
        result = asyncio.run(interaction_monitor._wait_for_card_interaction("msg_123"))
        assert result == {}


class TestInteractionMonitorFileMonitoring:
    """测试交互监控器文件监控功能"""

    @pytest.fixture
    def mock_interaction_manager(self):
        """创建模拟的交互管理器"""
        manager = Mock()
        manager._pending_interactions = {}
        return manager

    @pytest.fixture
    def interaction_monitor(self, mock_interaction_manager):
        """创建交互监控器实例"""
        from src.handlers.interaction_monitor import InteractionMonitor
        return InteractionMonitor(mock_interaction_manager)

    @pytest.mark.asyncio
    async def test_monitor_detects_new_file(self, interaction_monitor):
        """测试监控检测到新文件"""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_mtime = 12345.0

        request_data = {"message_id": "msg_123", "interaction_type": "test"}

        with patch('src.handlers.interaction_monitor.INTERACTION_REQUEST_FILE', mock_file):
            with patch('builtins.open', mock_open(read_data=json.dumps(request_data))):
                with patch.object(interaction_monitor, 'handle_interaction_request', new_callable=AsyncMock) as mock_handle:
                    # 模拟 asyncio.sleep 来避免无限循环
                    with patch('asyncio.sleep', new_callable=AsyncMock):
                        # 启动监控任务但立即取消
                        task = asyncio.create_task(interaction_monitor.monitor_interaction_requests())
                        await asyncio.sleep(0.01)
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

    @pytest.mark.asyncio
    async def test_monitor_no_file_exists(self, interaction_monitor):
        """测试监控文件不存在时的行为"""
        mock_file = MagicMock()
        mock_file.exists.return_value = False

        with patch('src.handlers.interaction_monitor.INTERACTION_REQUEST_FILE', mock_file):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                task = asyncio.create_task(interaction_monitor.monitor_interaction_requests())
                await asyncio.sleep(0.01)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


class TestInteractionMonitorEdgeCases:
    """测试交互监控器边界情况"""

    @pytest.fixture
    def mock_interaction_manager(self):
        """创建模拟的交互管理器"""
        manager = Mock()
        manager._pending_interactions = {}
        return manager

    @pytest.fixture
    def interaction_monitor(self, mock_interaction_manager):
        """创建交互监控器实例"""
        from src.handlers.interaction_monitor import InteractionMonitor
        return InteractionMonitor(mock_interaction_manager)

    @pytest.mark.asyncio
    async def test_monitor_json_decode_error(self, interaction_monitor):
        """测试 JSON 解析错误"""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_mtime = 12345.0

        with patch('src.handlers.interaction_monitor.INTERACTION_REQUEST_FILE', mock_file):
            # 模拟无效的 JSON 内容
            with patch('builtins.open', mock_open(read_data="invalid json")):
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    mock_sleep.side_effect = asyncio.CancelledError
                    with patch('src.handlers.interaction_monitor.logger') as mock_logger:
                        try:
                            await interaction_monitor.monitor_interaction_requests()
                        except asyncio.CancelledError:
                            pass

                        # 应该记录错误日志
                        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_io_error(self, interaction_monitor):
        """测试 IO 错误"""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_mtime = 12345.0

        with patch('src.handlers.interaction_monitor.INTERACTION_REQUEST_FILE', mock_file):
            with patch('builtins.open', side_effect=IOError("File error")):
                with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                    mock_sleep.side_effect = asyncio.CancelledError
                    with patch('src.handlers.interaction_monitor.logger') as mock_logger:
                        try:
                            await interaction_monitor.monitor_interaction_requests()
                        except asyncio.CancelledError:
                            pass

                        mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_same_content_skipped(self, interaction_monitor):
        """测试相同内容不重复处理"""
        mock_file = MagicMock()
        mock_file.exists.return_value = True
        mock_file.stat.return_value.st_mtime = 12345.0

        request_data = {"message_id": "msg_123", "interaction_type": "test"}

        with patch('src.handlers.interaction_monitor.INTERACTION_REQUEST_FILE', mock_file):
            with patch('builtins.open', mock_open(read_data=json.dumps(request_data))):
                with patch.object(interaction_monitor, 'handle_interaction_request', new_callable=AsyncMock) as mock_handle:
                    with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                        # 第一次正常处理，第二次取消
                        sleep_count = 0

                        async def sleep_side_effect(*args, **kwargs):
                            nonlocal sleep_count
                            sleep_count += 1
                            if sleep_count >= 2:
                                raise asyncio.CancelledError()
                            return None

                        mock_sleep.side_effect = sleep_side_effect

                        try:
                            await interaction_monitor.monitor_interaction_requests()
                        except asyncio.CancelledError:
                            pass

                        # 只应该处理一次（内容相同）
                        mock_handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_monitor_exception_in_loop(self, interaction_monitor):
        """测试循环中的异常处理"""
        mock_file = MagicMock()
        mock_file.exists.side_effect = Exception("Unexpected error")

        with patch('src.handlers.interaction_monitor.INTERACTION_REQUEST_FILE', mock_file):
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                mock_sleep.side_effect = asyncio.CancelledError
                with patch('src.handlers.interaction_monitor.logger') as mock_logger:
                    try:
                        await interaction_monitor.monitor_interaction_requests()
                    except asyncio.CancelledError:
                        pass

                    mock_logger.error.assert_called()


class TestHandleInteractionRequest:
    """测试处理交互请求"""

    @pytest.fixture
    def mock_interaction_manager(self):
        """创建模拟的交互管理器"""
        manager = Mock()
        manager._pending_interactions = {}
        return manager

    @pytest.fixture
    def interaction_monitor(self, mock_interaction_manager):
        """创建交互监控器实例"""
        from src.handlers.interaction_monitor import InteractionMonitor
        return InteractionMonitor(mock_interaction_manager)

    @pytest.mark.asyncio
    async def test_handle_request_writes_response(self, interaction_monitor, mock_interaction_manager):
        """测试成功写入响应"""
        request = {
            "message_id": "msg_123",
            "interaction_type": "button_click"
        }

        mock_response_file = MagicMock()

        with patch('src.handlers.interaction_monitor.INTERACTION_RESPONSE_FILE', mock_response_file):
            with patch('builtins.open', mock_open()) as mock_file_open:
                with patch.object(interaction_monitor, '_wait_for_card_interaction', new_callable=AsyncMock, return_value={"value": "ok", "type": "click"}):
                    await interaction_monitor.handle_interaction_request(request)

                    # 验证响应被写入
                    mock_file_open.assert_called()

    @pytest.mark.asyncio
    async def test_handle_request_timeout(self, interaction_monitor, mock_interaction_manager):
        """测试交互超时"""
        request = {
            "message_id": "msg_123",
            "interaction_type": "button_click"
        }

        mock_response_file = MagicMock()

        with patch('src.handlers.interaction_monitor.INTERACTION_RESPONSE_FILE', mock_response_file):
            with patch('builtins.open', mock_open()) as mock_file_open:
                with patch.object(interaction_monitor, '_wait_for_card_interaction', new_callable=AsyncMock, side_effect=asyncio.TimeoutError):
                    with patch('src.handlers.interaction_monitor.logger') as mock_logger:
                        await interaction_monitor.handle_interaction_request(request)

                        # 验证超时日志
                        mock_logger.warning.assert_called()

    @pytest.mark.asyncio
    async def test_handle_request_no_result(self, interaction_monitor, mock_interaction_manager):
        """测试无结果返回"""
        request = {
            "message_id": "msg_123",
            "interaction_type": "button_click"
        }

        mock_response_file = MagicMock()

        with patch('src.handlers.interaction_monitor.INTERACTION_RESPONSE_FILE', mock_response_file):
            with patch('builtins.open', mock_open()) as mock_file_open:
                with patch.object(interaction_monitor, '_wait_for_card_interaction', new_callable=AsyncMock, return_value=None):
                    with patch('src.handlers.interaction_monitor.logger') as mock_logger:
                        await interaction_monitor.handle_interaction_request(request)

                        # 验证超时/取消日志
                        mock_logger.info.assert_called()

    @pytest.mark.asyncio
    async def test_handle_request_exception(self, interaction_monitor, mock_interaction_manager):
        """测试处理请求异常"""
        request = {
            "message_id": "msg_123",
            "interaction_type": "button_click"
        }

        # 模拟 _wait_for_card_interaction 抛出异常
        with patch.object(interaction_monitor, '_wait_for_card_interaction', new_callable=AsyncMock, side_effect=Exception("Wait error")):
            with patch('src.handlers.interaction_monitor.logger') as mock_logger:
                # 不应该抛出异常
                await interaction_monitor.handle_interaction_request(request)

                # 验证错误被记录
                mock_logger.error.assert_called()

    @pytest.mark.asyncio
    async def test_handle_request_missing_fields(self, interaction_monitor, mock_interaction_manager):
        """测试缺少必要字段"""
        request = {}  # 缺少 message_id 和 interaction_type

        with patch.object(interaction_monitor, '_wait_for_card_interaction', new_callable=AsyncMock, return_value={}):
            with patch('src.handlers.interaction_monitor.INTERACTION_RESPONSE_FILE', MagicMock()):
                with patch('builtins.open', mock_open()):
                    # 应该正常处理，使用 None 作为值
                    await interaction_monitor.handle_interaction_request(request)


class TestWaitForCardInteraction:
    """测试等待卡片交互"""

    @pytest.fixture
    def mock_interaction_manager(self):
        """创建模拟的交互管理器"""
        manager = Mock()
        manager._pending_interactions = {}
        return manager

    @pytest.fixture
    def interaction_monitor(self, mock_interaction_manager):
        """创建交互监控器实例"""
        from src.handlers.interaction_monitor import InteractionMonitor
        return InteractionMonitor(mock_interaction_manager)

    @pytest.mark.asyncio
    async def test_wait_returns_empty_dict(self, interaction_monitor):
        """测试返回空字典"""
        result = await interaction_monitor._wait_for_card_interaction("msg_123")
        assert result == {}

    @pytest.mark.asyncio
    async def test_wait_with_custom_timeout(self, interaction_monitor):
        """测试自定义超时"""
        result = await interaction_monitor._wait_for_card_interaction("msg_123", timeout=60.0)
        assert result == {}
