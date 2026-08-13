"""
配置管理单元测试
"""
import pytest
import os
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config.settings import Settings, get_settings, reload_settings


class TestSettings:
    """测试 Pydantic Settings 配置"""

    def test_settings_creation(self):
        """测试 Settings 创建"""
        settings = Settings()
        assert settings is not None

    def test_settings_basic_values(self):
        """测试基本配置值"""
        settings = Settings()

        assert settings.im_platform == "feishu"
        assert settings.agent_backend in {"claude_code", "codex"}
        assert settings.task_timeout >= 300  # 允许环境变量覆盖
        assert settings.card_max_length >= 100  # 允许环境变量覆盖

    def test_settings_model_dump(self):
        """测试配置导出"""
        settings = Settings()
        dump = settings.model_dump()

        assert isinstance(dump, dict)
        assert len(dump) > 0



    def test_claude_code_properties(self):
        """测试 Claude Code 配置属性"""
        settings = Settings()

        # 测试 Claude Code 配置属性
        assert hasattr(settings, 'claude_code_cli_path')
        assert hasattr(settings, 'claude_code_session_id')
        assert hasattr(settings, 'claude_code_log_file')

    def test_codex_legacy_protocol_values_are_normalized(self):
        settings = Settings(
            codex_approval_policy="onRequest",
            codex_sandbox="workspaceWrite",
        )

        assert settings.codex_approval_policy == "on-request"
        assert settings.codex_sandbox == "workspace-write"

    def test_invalid_codex_protocol_values_fail_fast(self):
        with pytest.raises(ValueError, match="CODEX_SANDBOX"):
            Settings(codex_sandbox="invalid")
        with pytest.raises(ValueError, match="CODEX_APPROVAL_POLICY"):
            Settings(codex_approval_policy="granular")

    def test_set_codex_session_preferences_does_not_write_env_file(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("AGENT_BACKEND=codex\nCODEX_MODEL=old\n", encoding="utf-8")
        monkeypatch.setattr("src.config.settings.ENV_FILE", env_file)
        settings = Settings(codex_model="old")

        settings.set_codex_session_preferences(model="gpt-test", reasoning_effort="high")

        content = env_file.read_text(encoding="utf-8")
        assert content == "AGENT_BACKEND=codex\nCODEX_MODEL=old\n"
        assert settings.codex_model == "gpt-test"
        assert settings.codex_reasoning_effort == "high"

    def test_feishu_controller_uses_explicit_id_and_defaults_to_deny(self):
        explicit = Settings(
            feishu_allowed_user_id="ou_1",
            feishu_hook_notification_user_id="on_fallback",
        )
        assert explicit.is_feishu_user_authorized("ou_1") is True
        assert explicit.is_feishu_user_authorized("ou_intruder") is False

        empty = Settings(
            feishu_allowed_user_id="",
            feishu_hook_notification_user_id="",
        )
        assert empty.is_feishu_user_authorized("ou_1") is False

    @pytest.mark.parametrize("value", ["*", "ou_1,on_2"])
    def test_feishu_controller_rejects_multi_user_configuration(self, value):
        with pytest.raises(ValueError, match="不支持多用户|通配符"):
            Settings(feishu_allowed_user_id=value)

    def test_legacy_plural_env_name_accepts_only_one_controller(self):
        legacy = Settings(FEISHU_ALLOWED_USER_IDS="ou_legacy")
        assert legacy.get_feishu_allowed_user_id() == "ou_legacy"

        with pytest.raises(ValueError, match="不支持多用户"):
            Settings(FEISHU_ALLOWED_USER_IDS="ou_1,ou_2")


class TestSettingsMethods:
    """测试配置方法"""

    def test_get_hook_script_claude(self):
        """测试获取 Claude Hook 脚本"""
        settings = Settings()
        hook_script = settings.get_hook_script()
        assert hook_script == settings.ai_hook_script

    def test_get_hook_script_codex(self):
        """Codex 不使用独立 Hook 脚本，兼容方法仍返回通用脚本"""
        settings = Settings()
        settings.agent_backend = "codex"

        hook_script = settings.get_hook_script()
        assert hook_script == settings.ai_hook_script

    def test_is_hook_enabled(self):
        """测试 Hook 是否启用"""
        settings = Settings()
        assert isinstance(settings.is_hook_enabled(), bool)

    def test_get_enabled_platforms(self):
        """测试获取启用的平台"""
        settings = Settings()
        platforms = settings.get_enabled_platforms()

        assert isinstance(platforms, list)

    def test_is_platform_enabled(self):
        """测试平台是否启用"""
        settings = Settings()
        settings.enabled_im_platforms = "feishu,slack"

        assert settings.is_platform_enabled("feishu") is True
        assert settings.is_platform_enabled("slack") is True
        assert settings.is_platform_enabled("dingtalk") is False

    def test_get_process_name_claude(self):
        """测试获取 Claude 进程名"""
        settings = Settings()
        settings.agent_backend = "claude_code"
        assert settings.get_process_name() == "claude"

    def test_get_process_name_codex(self):
        """测试获取 Codex 进程名"""
        settings = Settings()
        settings.agent_backend = "codex"

        assert settings.get_process_name() == "codex"

    def test_get_platform_config_feishu(self):
        """测试获取飞书配置"""
        settings = Settings()
        config = settings.get_platform_config("feishu")

        assert "app_id" in config
        assert "app_secret" in config

    def test_get_platform_config_unknown(self):
        """测试获取未知平台配置"""
        settings = Settings()
        config = settings.get_platform_config("unknown")

        assert config == {}

    def test_init_directories(self):
        """测试初始化目录"""
        settings = Settings()

        # 不应该抛出异常
        settings.init_directories()

    def test_init_directories_enforces_private_permissions(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("FEISHU_APP_ID=test\n", encoding="utf-8")
        env_file.chmod(0o664)
        monkeypatch.setattr("src.config.settings.ENV_FILE", env_file)

        settings = Settings(
            data_dir=tmp_path / "data",
            db_path=tmp_path / "data" / "larkode.db",
            log_dir=tmp_path / "logs",
            upload_dir=tmp_path / "uploads",
        )
        settings.log_dir.mkdir(mode=0o755)
        old_log = settings.log_dir / "old.log"
        old_log.write_text("sensitive", encoding="utf-8")
        old_log.chmod(0o644)

        settings.init_directories()

        assert env_file.stat().st_mode & 0o777 == 0o600
        assert settings.data_dir.stat().st_mode & 0o777 == 0o700
        assert settings.log_dir.stat().st_mode & 0o777 == 0o700
        assert settings.upload_dir.stat().st_mode & 0o777 == 0o700
        assert old_log.stat().st_mode & 0o777 == 0o600


class TestEnvExpansion:
    """测试环境变量展开"""

    def test_expand_home_variable_from_env(self, monkeypatch):
        """测试从环境变量加载时展开 $HOME"""
        monkeypatch.setenv('HOME', '/home/testuser')
        monkeypatch.setenv('WORKSPACE_ROOT_DIR', '$HOME/Workspaces')
        monkeypatch.setenv('WORKSPACE_DEFAULT_DIR', '$HOME/Workspaces/larkode')

        # 重新加载设置
        from src.config.settings import reload_settings
        settings = reload_settings()

        assert str(settings.workspace_root_dir) == "/home/testuser/Workspaces"
        assert str(settings.workspace_default_dir) == "/home/testuser/Workspaces/larkode"

    def test_expand_tilde_from_env(self, monkeypatch):
        """测试从环境变量加载时展开 ~"""
        monkeypatch.setenv('HOME', '/home/testuser')
        monkeypatch.setenv('WORKSPACE_ROOT_DIR', '~/Workspaces')
        monkeypatch.setenv('WORKSPACE_DEFAULT_DIR', '~/Workspaces/larkode')

        from src.config.settings import reload_settings
        settings = reload_settings()

        assert str(settings.workspace_root_dir) == "/home/testuser/Workspaces"
        assert str(settings.workspace_default_dir) == "/home/testuser/Workspaces/larkode"

    def test_expand_custom_env_var_from_env(self, monkeypatch):
        """测试从环境变量加载时展开自定义环境变量"""
        monkeypatch.setenv('MY_WORKSPACE', '/custom/workspace')
        monkeypatch.setenv('WORKSPACE_ROOT_DIR', '$MY_WORKSPACE')
        monkeypatch.setenv('WORKSPACE_DEFAULT_DIR', '${MY_WORKSPACE}/larkode')

        from src.config.settings import reload_settings
        settings = reload_settings()

        assert str(settings.workspace_root_dir) == "/custom/workspace"
        assert str(settings.workspace_default_dir) == "/custom/workspace/larkode"
