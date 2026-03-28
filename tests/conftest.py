"""
pytest 配置 - 设置全局测试模式
"""
import os
import subprocess
from pathlib import Path

import pytest


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def pytest_configure(config):
    """pytest 启动时设置测试模式"""
    os.environ["TEST_MODE_ENABLED"] = "true"


def pytest_unconfigure(config):
    """pytest 结束时清除测试模式"""
    os.environ.pop("TEST_MODE_ENABLED", None)


@pytest.fixture(autouse=True)
def cleanup_after_test():
    """每个测试后恢复 settings"""
    yield
    try:
        from src.config.settings import reload_settings
        reload_settings()
    except Exception:
        pass


# ==================== 工作空间测试 fixture ====================

@pytest.fixture
def test_workspaces():
    """设置测试工作空间（使用 docs/testcases/workspace_switch_test 目录）
    
    自动处理：
    - 设置环境变量
    - 更新 settings
    - 清理 tmux sessions
    - 恢复环境变量
    """
    from src.config.settings import get_settings, reload_settings
    
    test_root = PROJECT_ROOT / "docs" / "testcases" / "workspace_switch_test"
    alpha = test_root / "workspace_alpha"
    beta = test_root / "workspace_beta"

    # 验证测试目录存在
    assert test_root.exists(), f"测试工作空间根目录不存在: {test_root}"
    assert alpha.exists(), f"workspace_alpha 目录不存在: {alpha}"
    assert beta.exists(), f"workspace_beta 目录不存在: {beta}"

    # 保存原始环境变量
    original_env = {
        "WORKSPACE_ROOT_DIR": os.environ.get("WORKSPACE_ROOT_DIR"),
        "WORKSPACE_DEFAULT_DIR": os.environ.get("WORKSPACE_DEFAULT_DIR"),
        "WORKSPACE_DISCOVERY_ENABLED": os.environ.get("WORKSPACE_DISCOVERY_ENABLED"),
    }

    # 设置测试环境变量
    os.environ["WORKSPACE_ROOT_DIR"] = str(test_root)
    os.environ["WORKSPACE_DEFAULT_DIR"] = str(alpha)
    os.environ["WORKSPACE_DISCOVERY_ENABLED"] = "True"

    # 更新 settings
    settings = get_settings()
    settings.workspace_root_dir = test_root
    settings.workspace_default_dir = alpha
    settings.workspace_discovery_enabled = True

    yield {
        "root": test_root,
        "alpha": alpha,
        "beta": beta,
    }

    # 清理 tmux sessions
    try:
        from src.workspace_manager import WorkspaceManager
        manager = WorkspaceManager()
        # 计算测试工作空间的 session 名称
        sessions_to_kill = [
            manager._get_session_name(str(alpha)),
            manager._get_session_name(str(beta))
        ]

        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            running_sessions = result.stdout.strip().split('\n')
            for session in running_sessions:
                if session in sessions_to_kill:
                    subprocess.run(
                        ["tmux", "kill-session", "-t", session],
                        capture_output=True, timeout=5
                    )
    except Exception:
        pass

    # 恢复环境变量
    for key, original in original_env.items():
        if original is not None:
            os.environ[key] = original
        else:
            os.environ.pop(key, None)

    reload_settings()
