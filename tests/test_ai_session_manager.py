"""
AI Session 管理器单元测试
"""
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import tempfile
import os

from src.ai_session_manager import AISessionManager


class TestAISessionManagerInit:
    """测试 AISessionManager 初始化"""

    def test_init_default(self):
        """测试默认初始化"""
        manager = AISessionManager()
        assert manager._workspace == Path.cwd()
        assert manager._projects_dir == AISessionManager.AI_PROJECTS_DIR

    def test_init_with_custom_projects_dir(self):
        """测试自定义项目目录初始化"""
        custom_dir = Path("/tmp/custom_projects")
        manager = AISessionManager(projects_dir=custom_dir)
        assert manager._projects_dir == custom_dir


class TestGetProjectName:
    """测试 _get_project_name 方法"""

    def test_get_project_name_root_path(self):
        """测试根路径转换"""
        manager = AISessionManager()
        manager._workspace = Path("/")

        # 根路径特殊处理
        result = manager._get_project_name()
        assert result.startswith("-")

    def test_get_project_name_normal_path(self):
        """测试普通路径转换"""
        manager = AISessionManager()
        manager._workspace = Path("/home/user/projects/myproject")

        result = manager._get_project_name()
        # 路径: /home/user/projects/myproject -> -home-user-projects-myproject
        assert result == "-home-user-projects-myproject"

    def test_get_project_name_with_spaces(self):
        """测试带空格的路径"""
        manager = AISessionManager()
        manager._workspace = Path("/home/user/my projects/test")

        result = manager._get_project_name()
        assert "my projects" in result.replace("-", " ") or "my-projects" in result.lower()


class TestFindRunningSession:
    """测试 find_running_session 方法"""

    def test_find_session_no_project_dir(self):
        """测试项目目录不存在的情况"""
        manager = AISessionManager()
        manager._projects_dir = Path("/nonexistent/path")

        result = manager.find_running_session()
        assert result is None

    def test_find_session_no_session_files(self):
        """测试没有 session 文件的情况"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建项目目录但不创建 session 文件
            project_name = "-test-project"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir(parents=True)

            manager = AISessionManager()
            manager._projects_dir = Path(tmpdir)
            manager._workspace = Path("/test/project")

            # 需要模拟 _get_project_name 返回正确的项目名
            with patch.object(manager, '_get_project_name', return_value=project_name):
                result = manager.find_running_session()
                assert result is None

    def test_find_session_with_valid_session_file(self):
        """测试找到有效的 session 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "-test-project"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir(parents=True)

            # 创建一个 session 文件
            session_file = project_dir / "test_session_123.jsonl"
            session_file.touch()

            manager = AISessionManager()
            manager._projects_dir = Path(tmpdir)

            with patch.object(manager, '_get_project_name', return_value=project_name):
                result = manager.find_running_session()
                assert result == "test_session_123"

    def test_find_session_multiple_files(self):
        """测试多个 session 文件时返回最新的"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "-test-project"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir(parents=True)

            # 创建多个 session 文件
            old_file = project_dir / "old_session.jsonl"
            old_file.touch()

            # 等待一小段时间确保时间戳不同
            import time
            time.sleep(0.01)

            new_file = project_dir / "new_session.jsonl"
            new_file.touch()

            manager = AISessionManager()
            manager._projects_dir = Path(tmpdir)

            with patch.object(manager, '_get_project_name', return_value=project_name):
                result = manager.find_running_session()
                assert result == "new_session"

    def test_find_session_with_stale_file(self):
        """测试过期的 session 文件"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "-test-project"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir(parents=True)

            # 创建一个旧的 session 文件
            session_file = project_dir / "stale_session.jsonl"
            session_file.touch()

            # 修改文件的修改时间为很久以前
            old_time = datetime.now() - timedelta(hours=2)
            os.utime(session_file, (old_time.timestamp(), old_time.timestamp()))

            manager = AISessionManager()
            manager._projects_dir = Path(tmpdir)

            with patch.object(manager, '_get_project_name', return_value=project_name):
                # 应该仍然返回 session ID，但会有警告日志
                result = manager.find_running_session()
                assert result == "stale_session"


class TestIsAIRunning:
    """测试 is_ai_running 方法"""

    def test_is_ai_running_no_processes(self):
        """测试没有运行中的 AI 进程"""
        manager = AISessionManager()

        with patch('psutil.process_iter') as mock_iter:
            mock_iter.return_value = []

            result = manager.is_ai_running()
            assert result is False

    def test_is_ai_running_with_matching_process(self):
        """测试有匹配的 AI 进程"""
        manager = AISessionManager()

        # 创建模拟进程
        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 12345,
            'name': 'claude',
            'cwd': str(manager._workspace),
            'cmdline': ['claude', 'code']
        }

        with patch('psutil.process_iter') as mock_iter:
            mock_iter.return_value = [mock_proc]

            result = manager.is_ai_running()
            assert result is True

    def test_is_ai_running_process_in_different_workspace(self):
        """测试进程在不同工作目录"""
        manager = AISessionManager()

        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 12345,
            'name': 'claude',
            'cwd': '/different/workspace',
            'cmdline': ['claude', 'code']
        }

        with patch('psutil.process_iter') as mock_iter:
            mock_iter.return_value = [mock_proc]

            result = manager.is_ai_running()
            assert result is False

    def test_is_ai_running_process_access_denied(self):
        """测试进程访问被拒绝"""
        import psutil
        manager = AISessionManager()

        mock_proc = MagicMock()
        # 模拟进程迭代器抛出 psutil.AccessDenied
        mock_proc.info = MagicMock()
        mock_proc.info.__getitem__.side_effect = psutil.AccessDenied(12345)

        with patch('psutil.process_iter') as mock_iter:
            mock_iter.return_value = [mock_proc]

            # 不应该抛出异常
            result = manager.is_ai_running()
            assert result is False

    def test_is_ai_running_with_iflow_process(self):
        """测试 iFlow 进程"""
        manager = AISessionManager()

        mock_proc = MagicMock()
        mock_proc.info = {
            'pid': 12345,
            'name': 'iflow',
            'cwd': str(manager._workspace),
            'cmdline': ['iflow']
        }

        with patch('src.ai_session_manager.get_settings') as mock_settings:
            mock_settings.return_value.get_process_name.return_value = "iflow"

            with patch('psutil.process_iter') as mock_iter:
                mock_iter.return_value = [mock_proc]

                result = manager.is_ai_running()
                assert result is True


class TestGetSession:
    """测试 get_session 方法"""

    def test_get_session_found(self):
        """测试找到现有 session"""
        manager = AISessionManager()

        with patch.object(manager, 'find_running_session', return_value="test_session_id"):
            result = manager.get_session()
            assert result == "test_session_id"

    def test_get_session_not_found(self):
        """测试找不到 session"""
        manager = AISessionManager()

        with patch.object(manager, 'find_running_session', return_value=None):
            result = manager.get_session()
            assert result is None


class TestClaudeRunningAlias:
    """测试 is_claude_running 别名方法"""

    def test_is_claude_running_alias(self):
        """测试 is_claude_running 是 is_ai_running 的别名"""
        manager = AISessionManager()

        with patch.object(manager, 'is_ai_running', return_value=True):
            result = manager.is_claude_running()
            assert result is True

        with patch.object(manager, 'is_ai_running', return_value=False):
            result = manager.is_claude_running()
            assert result is False


class TestEdgeCases:
    """测试边界情况"""

    def test_workspace_with_trailing_slash(self):
        """测试工作目录有尾随斜杠"""
        manager = AISessionManager()
        manager._workspace = Path("/home/user/project/")

        project_name = manager._get_project_name()
        assert project_name.startswith("-")

    def test_special_characters_in_path(self):
        """测试路径中的特殊字符"""
        manager = AISessionManager()
        manager._workspace = Path("/home/user/project-test_v2")

        project_name = manager._get_project_name()
        assert project_name.startswith("-")

    def test_empty_session_file_list(self):
        """测试空文件列表"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "-test-project"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir(parents=True)

            manager = AISessionManager()
            manager._projects_dir = Path(tmpdir)

            with patch.object(manager, '_get_project_name', return_value=project_name):
                result = manager.find_running_session()
                assert result is None

    def test_permission_error_on_file_access(self):
        """测试文件访问权限错误"""
        manager = AISessionManager()

        with tempfile.TemporaryDirectory() as tmpdir:
            project_name = "-test-project"
            project_dir = Path(tmpdir) / project_name
            project_dir.mkdir(parents=True)

            session_file = project_dir / "test_session.jsonl"
            session_file.touch()

            manager._projects_dir = Path(tmpdir)

            # 模拟文件 stat 访问错误
            with patch.object(manager, '_get_project_name', return_value=project_name):
                with patch.object(Path, 'glob') as mock_glob:
                    mock_glob.side_effect = PermissionError("Access denied")

                    # 当前代码不捕获 PermissionError，会抛出异常
                    with pytest.raises(PermissionError):
                        manager.find_running_session()


