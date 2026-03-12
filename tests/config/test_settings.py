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
        assert settings.ai_assistant_type == "claude_code"
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
        assert hasattr(settings, 'claude_code_workspace_dir')
        assert hasattr(settings, 'claude_code_cli_path')
        assert hasattr(settings, 'claude_code_session_id')
        assert hasattr(settings, 'claude_code_log_file')


class TestSettingsMethods:
    """测试配置方法"""

    def test_get_hook_script_claude(self):
        """测试获取 Claude Hook 脚本"""
        settings = Settings()
        settings.ai_assistant_type = "claude_code"

        hook_script = settings.get_hook_script()
        assert hook_script == settings.ai_hook_script

    def test_get_hook_script_iflow(self):
        """测试获取 iFlow Hook 脚本"""
        settings = Settings()
        settings.ai_assistant_type = "iflow"

        hook_script = settings.get_hook_script()
        assert hook_script == settings.iflow_hook_script

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
        settings.ai_assistant_type = "claude_code"

        assert settings.get_process_name() == "claude"

    def test_get_process_name_iflow(self):
        """测试获取 iFlow 进程名"""
        settings = Settings()
        settings.ai_assistant_type = "iflow"

        assert settings.get_process_name() == "iflow"

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


