"""
WorkspaceManager 单元测试补充 - 提升覆盖率
"""
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.workspace_manager import WorkspaceManager, get_workspace_manager


class TestWorkspaceManagerCoverage:
    """WorkspaceManager 覆盖率补充测试"""

    def test_get_session_name(self):
        """测试 session 名称生成"""
        manager = WorkspaceManager()

        # 测试路径转 session 名称
        session = manager._get_session_name("/home/user/project")
        assert session == "cc-home-user-project"

        session = manager._get_session_name("/home/sc/Workspaces/test")
        assert session == "cc-home-sc-Workspaces-test"

    def test_session_name_to_path(self):
        """测试 session 名称解析为路径"""
        manager = WorkspaceManager()

        # 测试 session 名称转路径
        path = manager._session_name_to_path("cc-home-user-project")
        assert path == "/home/user/project"

        path = manager._session_name_to_path("cc-home-sc-Workspaces-test")
        assert path == "/home/sc/Workspaces/test"

        # 无效的 session 名称
        path = manager._session_name_to_path("invalid-session")
        assert path is None

        path = manager._session_name_to_path("")
        assert path is None

    def test_get_workspace_manager_singleton(self):
        """测试全局单例"""
        manager1 = get_workspace_manager()
        manager2 = get_workspace_manager()

        assert manager1 is manager2

    def test_switch_workspace_invalid_path(self):
        """测试切换到不存在的路径"""
        manager = WorkspaceManager()

        success, message = manager.switch_workspace("/nonexistent/path")
        assert success is False
        assert "不存在" in message

    @patch('src.workspace_manager.discover_workspaces')
    @patch('src.workspace_manager.get_settings')
    def test_get_workspaces(self, mock_get_settings, mock_discover):
        """测试获取工作空间列表"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.workspace_default_dir = Path("/default/workspace")
        mock_get_settings.return_value = mock_settings

        # Mock discover_workspaces
        mock_discover.return_value = [
            {"name": "workspace1", "path": "/path/to/workspace1", "depth": 1},
            {"name": "workspace2", "path": "/path/to/workspace2", "depth": 2},
        ]

        manager = WorkspaceManager()
        manager._current_workspace = "/path/to/workspace1"

        # Mock _get_running_workspaces
        with patch.object(manager, '_get_running_workspaces', return_value=set()):
            workspaces = manager.get_workspaces()

        assert len(workspaces) == 2
        assert workspaces[0]["name"] == "workspace1"
        assert workspaces[0]["is_current"] is True
        assert workspaces[1]["is_current"] is False

    @patch('src.workspace_manager.subprocess.run')
    def test_get_running_workspaces(self, mock_run):
        """测试获取运行中的工作空间"""
        # Mock tmux list-sessions output
        mock_run.return_value = Mock(
            returncode=0,
            stdout="cc-home-user-project:/home/user/project\ncc-other:/other/path\n"
        )

        manager = WorkspaceManager()
        running = manager._get_running_workspaces()

        assert isinstance(running, set)

    @patch('src.workspace_manager.subprocess.run')
    def test_get_running_workspaces_no_sessions(self, mock_run):
        """测试没有运行中的 tmux sessions"""
        mock_run.return_value = Mock(returncode=1, stdout="")

        manager = WorkspaceManager()
        running = manager._get_running_workspaces()

        assert running == set()