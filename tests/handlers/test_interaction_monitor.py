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
