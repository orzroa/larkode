"""
Tmux 工具函数测试
"""
import pytest
from unittest.mock import MagicMock, patch


class TestTmuxUtils:
    """Tmux 工具函数测试"""

    @pytest.fixture
    def mock_settings(self):
        """模拟配置"""
        with patch("src.utils.tmux_utils.get_settings") as mock:
            settings = MagicMock()
            mock.return_value = settings
            yield mock

    def test_get_tmux_last_lines_with_workspace(self, mock_settings):
        """测试获取 tmux 输出（指定工作空间）"""
        mock_result = MagicMock()
        mock_result.stdout = "line1\nline2\nline3\n"

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result) as mock_run:
            from src.utils.tmux_utils import get_tmux_last_lines

            result = get_tmux_last_lines(lines=100, workspace="/home/user/project")

            # 验证 session 名称生成
            call_args = mock_run.call_args[0][0]
            # call_args 是列表，检查第4个元素（session 名称）
            assert "cc-home-user-project:0.0" in call_args[4]

    def test_get_tmux_last_lines_no_output(self, mock_settings):
        """测试 tmux 无输出"""
        mock_result = MagicMock()
        mock_result.stdout = ""

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result):
            from src.utils.tmux_utils import get_tmux_last_lines

            result = get_tmux_last_lines(lines=100, workspace="/home/user/project")
            assert result == "tmux 无输出"

    def test_get_tmux_last_lines_error(self, mock_settings):
        """测试 tmux 命令执行失败"""
        with patch("src.utils.tmux_utils.subprocess.run", side_effect=Exception("tmux error")):
            from src.utils.tmux_utils import get_tmux_last_lines

            result = get_tmux_last_lines(lines=100, workspace="/home/user/project")
            assert "读取失败" in result
            assert "tmux error" in result

    def test_get_tmux_last_lines_with_workspace_manager(self, mock_settings):
        """测试使用 WorkspaceManager 获取当前工作空间"""
        mock_result = MagicMock()
        mock_result.stdout = "output line 1\noutput line 2\n"

        mock_workspace_manager = MagicMock()
        mock_workspace_manager.get_current_workspace.return_value = "/home/user/current-project"

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result) as mock_run:
            with patch("src.workspace_manager.get_workspace_manager", return_value=mock_workspace_manager):
                from src.utils.tmux_utils import get_tmux_last_lines

                result = get_tmux_last_lines(lines=100)

                # 验证使用了 workspace manager
                mock_workspace_manager.get_current_workspace.assert_called_once()

    def test_get_tmux_last_lines_no_current_workspace(self, mock_settings):
        """测试无当前工作空间时使用默认 session"""
        mock_result = MagicMock()
        mock_result.stdout = "output\n"

        mock_workspace_manager = MagicMock()
        mock_workspace_manager.get_current_workspace.return_value = None

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result) as mock_run:
            with patch("src.workspace_manager.get_workspace_manager", return_value=mock_workspace_manager):
                from src.utils.tmux_utils import get_tmux_last_lines

                result = get_tmux_last_lines(lines=100)

                # 验证使用了默认 session
                call_args = mock_run.call_args[0][0]
                assert "cc:0.0" in call_args[4]

    def test_get_tmux_last_lines_workspace_manager_exception(self, mock_settings):
        """测试 WorkspaceManager 抛出异常时使用默认 session"""
        mock_result = MagicMock()
        mock_result.stdout = "output\n"

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result) as mock_run:
            with patch("src.workspace_manager.get_workspace_manager", side_effect=Exception("No workspace")):
                from src.utils.tmux_utils import get_tmux_last_lines

                result = get_tmux_last_lines(lines=100)

                # 验证使用了默认 session
                call_args = mock_run.call_args[0][0]
                assert "cc:0.0" in call_args[4]

    def test_get_tmux_last_lines_cleans_output(self, mock_settings):
        """测试清理 tmux 输出"""
        mock_result = MagicMock()
        # 包含 ANSI 转义序列和空行
        mock_result.stdout = "\x1b[32mgreen text\x1b[0m\n\n   \nline2\n"

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result):
            from src.utils.tmux_utils import get_tmux_last_lines

            result = get_tmux_last_lines(lines=100, workspace="/test")

            # 验证空行被移除
            lines = result.split('\n')
            assert all(line.strip() for line in lines)  # 没有空行

    def test_get_tmux_last_lines_deep_workspace_path(self, mock_settings):
        """测试深层工作空间路径"""
        mock_result = MagicMock()
        mock_result.stdout = "output\n"

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result) as mock_run:
            from src.utils.tmux_utils import get_tmux_last_lines

            result = get_tmux_last_lines(lines=100, workspace="/a/b/c/d/e")

            # 验证 session 名称正确生成
            call_args = mock_run.call_args[0][0]
            assert "cc-a-b-c-d-e:0.0" in call_args[4]

    def test_get_tmux_last_lines_default_lines(self, mock_settings):
        """测试默认行数"""
        mock_result = MagicMock()
        mock_result.stdout = "output\n"

        with patch("src.utils.tmux_utils.subprocess.run", return_value=mock_result) as mock_run:
            from src.utils.tmux_utils import get_tmux_last_lines

            get_tmux_last_lines(workspace="/test")

            # 验证默认行数 200
            call_args = mock_run.call_args[0][0]
            assert "-200" in call_args