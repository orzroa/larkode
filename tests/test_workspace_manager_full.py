"""
WorkspaceManager 完整测试 - 覆盖switch_workspace等核心方法
"""
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess

import pytest

from src.workspace_manager import WorkspaceManager, get_workspace_manager


class TestWorkspaceManagerSwitch:
    """测试工作空间切换功能"""

    @patch('src.workspace_manager.TmuxSessionManager')
    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.subprocess.run')
    def test_switch_workspace_create_new_session(self, mock_run, mock_get_settings, mock_tmux_class):
        """测试创建新 session"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.workspace_default_dir = None
        mock_get_settings.return_value = mock_settings

        # Mock TmuxSessionManager
        mock_tmux = Mock()
        mock_tmux._check_tmux_session.return_value = False
        mock_tmux._create_tmux_session.return_value = True
        mock_tmux_class.return_value = mock_tmux

        manager = WorkspaceManager()
        
        # 创建临时目录
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            success, message = manager.switch_workspace(tmpdir)
            
            assert success is True
            assert "已启动并切换" in message
            mock_tmux._create_tmux_session.assert_called_once()

    @patch('src.workspace_manager.TmuxSessionManager')
    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.subprocess.run')
    def test_switch_workspace_existing_session(self, mock_run, mock_get_settings, mock_tmux_class):
        """测试连接到已存在的 session"""
        # Mock settings
        mock_settings = Mock()
        mock_settings.workspace_default_dir = None
        mock_get_settings.return_value = mock_settings

        # Mock subprocess.run for setting env var
        mock_run.return_value = Mock(returncode=0)

        # Mock TmuxSessionManager
        mock_tmux = Mock()
        mock_tmux._check_tmux_session.return_value = True
        mock_tmux_class.return_value = mock_tmux

        manager = WorkspaceManager()
        
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            success, message = manager.switch_workspace(tmpdir)
            
            assert success is True
            assert "已存在 session" in message

    @patch('src.workspace_manager.get_settings')
    def test_get_current_workspace_from_memory(self, mock_get_settings):
        """测试从内存获取当前工作空间"""
        mock_settings = Mock()
        mock_settings.workspace_default_dir = None
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()
        manager._current_workspace = "/test/workspace"

        result = manager.get_current_workspace()
        assert result == "/test/workspace"

    @patch('src.workspace_manager.get_settings')
    def test_get_current_workspace_default(self, mock_get_settings):
        """测试返回默认工作空间"""
        mock_settings = Mock()
        mock_settings.workspace_default_dir = Path("/default/workspace")
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()
        manager._current_workspace = None

        result = manager.get_current_workspace()
        assert result == "/default/workspace"
