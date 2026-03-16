"""
WorkspaceManager 更多测试 - 覆盖异常分支
"""
import os
import subprocess
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.workspace_manager import WorkspaceManager, get_workspace_manager


class TestWorkspaceManagerExceptions:
    """测试 WorkspaceManager 异常分支"""

    @patch('src.workspace_manager.get_settings')
    def test_get_current_workspace_from_tmux_parse_failure(self, mock_get_settings):
        """测试从 tmux session 解析失败的情况"""
        mock_settings = Mock()
        mock_settings.workspace_default_dir = Path("/default/workspace")
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        # Mock subprocess.run 返回有效的 session，但路径不存在
        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="cc-invalid-session:/some/path\n"
            )

            # Mock _session_name_to_path 返回不存在的路径
            with patch.object(manager, '_session_name_to_path', return_value="/nonexistent/path"):
                # Mock Path.exists 返回 False
                with patch('src.workspace_manager.Path') as mock_path:
                    mock_path.return_value.exists.return_value = False
                    mock_path.return_value.__str__ = lambda self: "/nonexistent/path"

                    result = manager.get_current_workspace()

                    # 应该返回默认工作空间
                    assert result == str(mock_settings.workspace_default_dir)

    @patch('src.workspace_manager.get_settings')
    def test_get_current_workspace_tmux_error(self, mock_get_settings):
        """测试 tmux 命令失败的情况"""
        mock_settings = Mock()
        mock_settings.workspace_default_dir = Path("/default/workspace")
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        # Mock subprocess.run 抛出异常
        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

            result = manager.get_current_workspace()

            # 应该返回默认工作空间
            assert result == str(mock_settings.workspace_default_dir)

    @patch('src.workspace_manager.get_settings')
    def test_get_current_workspace_no_default(self, mock_get_settings):
        """测试没有默认工作空间的情况"""
        mock_settings = Mock()
        mock_settings.workspace_default_dir = None
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        # Mock subprocess.run 返回无 session
        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="")

            result = manager.get_current_workspace()

            # 应该返回 None
            assert result is None

    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.TmuxSessionManager')
    def test_switch_workspace_set_env_failure(self, mock_tmux_mgr, mock_get_settings):
        """测试设置环境变量失败"""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        # 创建临时目录
        with patch('src.workspace_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            # Mock session 存在
            mock_session_mgr = Mock()
            mock_session_mgr._check_tmux_session.return_value = True
            mock_tmux_mgr.return_value = mock_session_mgr

            # Mock subprocess.run 设置环境变量失败
            with patch('src.workspace_manager.subprocess.run') as mock_run:
                mock_run.side_effect = [Exception("set-environment failed"), None]

                success, message = manager.switch_workspace("/test/workspace")

                # 仍然应该成功（环境变量失败不影响主流程）
                assert success is True

    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.TmuxSessionManager')
    def test_switch_workspace_attach_timeout(self, mock_tmux_mgr, mock_get_settings):
        """测试 attach 超时"""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        with patch('src.workspace_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            mock_session_mgr = Mock()
            mock_session_mgr._check_tmux_session.return_value = True
            mock_tmux_mgr.return_value = mock_session_mgr

            with patch('src.workspace_manager.subprocess.run') as mock_run:
                # 第一次调用成功（set-environment），第二次超时（attach）
                call_count = [0]
                def side_effect(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return Mock()
                    else:
                        raise subprocess.TimeoutExpired("tmux", 10)

                mock_run.side_effect = side_effect

                success, message = manager.switch_workspace("/test/workspace")

                # 仍然应该成功
                assert success is True

    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.TmuxSessionManager')
    def test_switch_workspace_attach_error(self, mock_tmux_mgr, mock_get_settings):
        """测试 attach 失败"""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        with patch('src.workspace_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            mock_session_mgr = Mock()
            mock_session_mgr._check_tmux_session.return_value = True
            mock_tmux_mgr.return_value = mock_session_mgr

            with patch('src.workspace_manager.subprocess.run') as mock_run:
                # 第一次调用成功，第二次失败
                call_count = [0]
                def side_effect(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        return Mock()
                    else:
                        raise Exception("attach failed")

                mock_run.side_effect = side_effect

                success, message = manager.switch_workspace("/test/workspace")

                # 仍然应该成功
                assert success is True

    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.TmuxSessionManager')
    def test_switch_workspace_create_failure(self, mock_tmux_mgr, mock_get_settings):
        """测试创建 session 失败"""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        with patch('src.workspace_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            mock_session_mgr = Mock()
            mock_session_mgr._check_tmux_session.return_value = False
            mock_session_mgr._create_tmux_session.return_value = False
            mock_tmux_mgr.return_value = mock_session_mgr

            success, message = manager.switch_workspace("/test/workspace")

            assert success is False
            assert "失败" in message

    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.TmuxSessionManager')
    def test_switch_workspace_create_attach_timeout(self, mock_tmux_mgr, mock_get_settings):
        """测试创建新 session 后 attach 超时"""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        with patch('src.workspace_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            mock_session_mgr = Mock()
            mock_session_mgr._check_tmux_session.return_value = False
            mock_session_mgr._create_tmux_session.return_value = True
            mock_tmux_mgr.return_value = mock_session_mgr

            with patch('src.workspace_manager.subprocess.run') as mock_run:
                mock_run.side_effect = subprocess.TimeoutExpired("tmux", 10)

                success, message = manager.switch_workspace("/test/workspace")

                # 应该成功（attach 超时不影响主流程）
                assert success is True

    @patch('src.workspace_manager.get_settings')
    @patch('src.workspace_manager.TmuxSessionManager')
    def test_switch_workspace_create_attach_error(self, mock_tmux_mgr, mock_get_settings):
        """测试创建新 session 后 attach 失败"""
        mock_settings = Mock()
        mock_get_settings.return_value = mock_settings

        manager = WorkspaceManager()

        with patch('src.workspace_manager.Path') as mock_path:
            mock_path.return_value.exists.return_value = True

            mock_session_mgr = Mock()
            mock_session_mgr._check_tmux_session.return_value = False
            mock_session_mgr._create_tmux_session.return_value = True
            mock_tmux_mgr.return_value = mock_session_mgr

            with patch('src.workspace_manager.subprocess.run') as mock_run:
                mock_run.side_effect = Exception("attach failed")

                success, message = manager.switch_workspace("/test/workspace")

                # 应该成功
                assert success is True

    def test_get_running_workspaces_timeout(self):
        """测试获取运行中的工作空间超时"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("tmux", 5)

            result = manager._get_running_workspaces()

            assert result == set()

    def test_get_running_workspaces_error(self):
        """测试获取运行中的工作空间失败"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.side_effect = Exception("tmux error")

            result = manager._get_running_workspaces()

            assert result == set()

    def test_get_running_workspaces_empty_line(self):
        """测试空行处理"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="\n\n")

            result = manager._get_running_workspaces()

            assert result == set()

    def test_get_running_workspaces_invalid_format(self):
        """测试无效格式处理"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="invalid-format\n")

            result = manager._get_running_workspaces()

            assert result == set()

    def test_get_running_workspaces_old_format(self):
        """测试旧格式 session（cc）"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="cc:/home/user/project\n"
            )

            result = manager._get_running_workspaces()

            assert "/home/user/project" in result

    def test_get_running_workspaces_old_format_empty_path(self):
        """测试旧格式 session 路径为空"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="cc:\n"
            )

            result = manager._get_running_workspaces()

            assert result == set()

    def test_get_running_workspaces_new_format(self):
        """测试新格式 session（cc-home-user-project）"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="cc-home-user-project:\n"
            )

            # Mock _session_name_to_path 返回有效路径
            with patch.object(manager, '_session_name_to_path', return_value="/home/user/project"):
                result = manager._get_running_workspaces()

                assert "/home/user/project" in result

    def test_get_running_workspaces_new_format_parse_failure(self):
        """测试新格式 session 解析失败"""
        manager = WorkspaceManager()

        with patch('src.workspace_manager.subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="cc-invalid:\n"
            )

            # Mock _session_name_to_path 返回 None
            with patch.object(manager, '_session_name_to_path', return_value=None):
                result = manager._get_running_workspaces()

                assert result == set()