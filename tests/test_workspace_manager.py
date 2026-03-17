"""
工作空间管理器测试
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import tempfile
import os

from src.workspace_discovery import WorkspaceDiscovery, discover_workspaces
from src.workspace_manager import WorkspaceManager


class TestWorkspaceDiscovery:
    """测试 WorkspaceDiscovery 类"""

    def test_discover_depth_1(self):
        """测试深度为 1 的扫描"""
        # 创建临时目录结构
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "project1").mkdir()
            (root / "project2").mkdir()
            (root / "project3").mkdir()

            discovery = WorkspaceDiscovery(root_dir=root, depth=1)
            workspaces = discovery.discover()

            assert len(workspaces) == 3
            assert workspaces[0]['name'] == 'project1'
            assert workspaces[1]['name'] == 'project2'
            assert workspaces[2]['name'] == 'project3'

            # 验证所有工作空间深度为 1
            for ws in workspaces:
                assert ws['depth'] == 1

    def test_discover_depth_2(self):
        """测试深度为 2 的扫描"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "project1").mkdir()
            (root / "monorepo" / "frontend").mkdir(parents=True)
            (root / "monorepo" / "backend").mkdir(parents=True)

            discovery = WorkspaceDiscovery(root_dir=root, depth=2)
            workspaces = discovery.discover()

            # 应该发现 4 个工作空间（depth=1 和 depth=2）
            assert len(workspaces) == 4

            # 验证排序：深度优先，字母排序
            assert workspaces[0]['name'] == 'monorepo'
            assert workspaces[0]['depth'] == 1

            assert workspaces[1]['name'] == 'monorepo/backend'
            assert workspaces[1]['depth'] == 2

            assert workspaces[2]['name'] == 'monorepo/frontend'
            assert workspaces[2]['depth'] == 2

            assert workspaces[3]['name'] == 'project1'
            assert workspaces[3]['depth'] == 1

    def test_discover_with_exclude_patterns(self):
        """测试排除模式"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "project1").mkdir()
            (root / ".git").mkdir()
            (root / "node_modules").mkdir()

            discovery = WorkspaceDiscovery(
                root_dir=root,
                depth=1,
                exclude_patterns=[".git", "node_modules"]
            )
            workspaces = discovery.discover()

            # 应该只发现 project1
            assert len(workspaces) == 1
            assert workspaces[0]['name'] == 'project1'

    def test_discover_hidden_directories_excluded(self):
        """测试隐藏目录自动排除"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "project1").mkdir()
            (root / ".hidden").mkdir()

            discovery = WorkspaceDiscovery(root_dir=root, depth=1)
            workspaces = discovery.discover()

            # 应该只发现 project1，.hidden 被排除
            assert len(workspaces) == 1
            assert workspaces[0]['name'] == 'project1'

    def test_discover_nonexistent_root(self):
        """测试根目录不存在"""
        discovery = WorkspaceDiscovery(root_dir=Path("/nonexistent/path"), depth=1)
        workspaces = discovery.discover()
        assert workspaces == []

    def test_discover_empty_directory(self):
        """测试空目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            discovery = WorkspaceDiscovery(root_dir=root, depth=1)
            workspaces = discovery.discover()
            assert workspaces == []

    def test_discover_sorting(self):
        """测试排序（字母顺序）"""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "zebra").mkdir()
            (root / "alpha").mkdir()
            (root / "beta").mkdir()

            discovery = WorkspaceDiscovery(root_dir=root, depth=1)
            workspaces = discovery.discover()

            # 验证按字母排序
            assert workspaces[0]['name'] == 'alpha'
            assert workspaces[1]['name'] == 'beta'
            assert workspaces[2]['name'] == 'zebra'


class TestWorkspaceManager:
    """测试 WorkspaceManager 类"""

    def test_get_session_name(self):
        """测试 session 名称生成"""
        manager = WorkspaceManager()

        # 测试路径转 session 名称
        session_name = manager._get_session_name("/home/user/Workspaces/github/larkode")
        assert session_name == "cc-home-user-Workspaces-github-larkode"

    def test_session_name_to_path(self):
        """测试从 session 名称解析路径"""
        manager = WorkspaceManager()

        # 测试 session 名称转路径
        path = manager._session_name_to_path("cc-home-user-Workspaces-github-larkode")
        assert path == "/home/user/Workspaces/github/larkode"

        # 测试非 cc- 开头的 session
        path = manager._session_name_to_path("other-session")
        assert path is None

    def test_get_workspaces_disabled(self):
        """测试禁用自动发现时获取工作空间"""
        manager = WorkspaceManager()

        # Mock settings for workspace_discovery module
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = False

        with patch('src.workspace_discovery.get_settings', return_value=mock_settings):
            workspaces = manager.get_workspaces()
            assert workspaces == []

    def test_get_current_workspace_default(self):
        """测试获取当前工作空间（未设置时返回默认）"""
        manager = WorkspaceManager()

        # Mock settings
        mock_settings = MagicMock()
        mock_settings.workspace_default_dir = Path("/home/test/project")

        with patch('src.workspace_manager.get_settings', return_value=mock_settings):
            with patch.dict('os.environ', {'TMUX': ''}, clear=False):
                # 清空 TMUX 环境变量，避免检测到真实的 tmux session
                # 同时清空内存缓存
                manager._current_workspace = None
                current = manager.get_current_workspace()
                # 因为没有 tmux session，且没有缓存，应该返回默认工作空间
                assert current == "/home/test/project"

    def test_get_current_workspace_set(self):
        """测试获取当前工作空间（已设置但无 tmux 环境）"""
        manager = WorkspaceManager()
        manager._current_workspace = "/home/test/custom"

        # Mock TMUX env to be empty (not in tmux)
        with patch.dict('os.environ', {'TMUX': ''}, clear=False):
            current = manager.get_current_workspace()
            # 因为不在 tmux 中，所以使用内存缓存
            assert current == "/home/test/custom"


class TestDiscoverWorkspaces:
    """测试 discover_workspaces 便捷函数"""

    def test_discover_workspaces_disabled(self):
        """测试禁用自动发现"""
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = False

        with patch('src.workspace_discovery.get_settings', return_value=mock_settings):
            workspaces = discover_workspaces()
            assert workspaces == []

    def test_discover_workspaces_no_root(self):
        """测试未配置根目录"""
        mock_settings = MagicMock()
        mock_settings.workspace_discovery_enabled = True
        mock_settings.workspace_root_dir = None

        with patch('src.workspace_discovery.get_settings', return_value=mock_settings):
            workspaces = discover_workspaces()
            assert workspaces == []