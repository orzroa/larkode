"""
集成测试公共 fixtures

提供飞书相关的共享 fixtures
"""
import os
import subprocess
from pathlib import Path

import pytest

from src.config.settings import get_settings, reload_settings
from src.feishu import FeishuAPI
from src.im_platforms.feishu import FeishuPlatform, FeishuCardBuilder
from src.interfaces.im_platform import NormalizedCard, PlatformConfig

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent


# ==================== 飞书相关 fixtures ====================

@pytest.fixture(scope="module")
def user_id():
    """获取飞书用户 ID（从 .env 读取）"""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")

    uid = os.getenv("FEISHU_HOOK_NOTIFICATION_USER_ID")
    if not uid:
        pytest.skip("未配置 FEISHU_HOOK_NOTIFICATION_USER_ID，跳过集成测试")
    return uid


@pytest.fixture(scope="module")
def feishu_api():
    """获取飞书 API 实例"""
    settings = get_settings()
    return FeishuAPI(settings.FEISHU_APP_ID, settings.FEISHU_APP_SECRET)


@pytest.fixture(scope="module")
def feishu_platform():
    """创建飞书平台实例"""
    settings = get_settings()
    config = PlatformConfig(
        app_id=settings.FEISHU_APP_ID,
        app_secret=settings.FEISHU_APP_SECRET,
        domain=settings.FEISHU_MESSAGE_DOMAIN,
        receive_id_type=settings.FEISHU_MESSAGE_RECEIVE_ID_TYPE,
    )
    return FeishuPlatform(config)


@pytest.fixture
def send_func(feishu_platform):
    """创建真实的飞书发送函数，支持 card 和 message 参数"""
    async def _send(user_id: str, card: NormalizedCard = None, message: str = None):
        if card:
            return await feishu_platform.send_card(user_id, card)
        elif message:
            return await feishu_platform.api.send_message(user_id, message)
        return False
    return _send


# ==================== 工作空间测试 fixtures ====================

@pytest.fixture
def test_workspaces():
    """设置测试工作空间（使用 docs/testcases/workspace_switch_test 目录）
    
    自动处理：
    - 设置环境变量
    - 更新 settings
    - 清理 tmux sessions
    - 恢复环境变量
    """
    test_root = PROJECT_ROOT / "docs" / "testcases" / "workspace_switch_test"
    alpha = test_root / "workspace_alpha"
    beta = test_root / "workspace_beta"

    # 验证测试目录存在
    assert test_root.exists(), f"测试工作空间根目录不存在: {test_root}"
    assert alpha.exists(), f"workspace_alpha 目录不存在: {alpha}"
    assert beta.exists(), f"workspace_beta 目录不存在: {beta}"

    # 计算需要清理的 session 名称
    def get_session_name(workspace_path: str) -> str:
        path_str = str(workspace_path).strip('/')
        return f"cc-{path_str.replace('/', '-')}"

    sessions_to_kill = [
        get_session_name(str(alpha)),
        get_session_name(str(beta))
    ]

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
        "sessions_to_kill": sessions_to_kill
    }

    # 清理 tmux sessions
    try:
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
