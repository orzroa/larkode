"""
IM 平台工厂单元测试
"""
import pytest
from unittest.mock import MagicMock

# 添加项目根目录到路径
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.factories.platform_factory import IMPlatformFactory
from src.interfaces.im_platform import PlatformConfig


class MockPlatform:
    """Mock 平台实现"""

    def __init__(self, config: PlatformConfig):
        self.config = config


class MockCardBuilder:
    """Mock 卡片构建器实现"""

    def __init__(self):
        pass


class TestIMPlatformFactory:
    """测试 IM 平台工厂"""

    def setup_method(self):
        """设置测试环境"""
        # 清空注册表
        IMPlatformFactory._platforms = {}

    def test_register_platform(self):
        """测试注册平台"""
        IMPlatformFactory.register_platform(
            "feishu",
            MockPlatform,
            MockCardBuilder
        )

        assert IMPlatformFactory.is_platform_registered("feishu")
        assert "feishu" in IMPlatformFactory._platforms

    def test_create_platform(self):
        """测试创建平台实例"""
        IMPlatformFactory.register_platform(
            "feishu",
            MockPlatform,
            MockCardBuilder
        )

        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret"
        )

        platform = IMPlatformFactory.create_platform("feishu", config)

        assert platform is not None
        assert isinstance(platform, MockPlatform)
        assert platform.config == config

    def test_create_platform_unregistered_type(self):
        """测试创建未注册类型的平台"""
        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret"
        )

        platform = IMPlatformFactory.create_platform("unknown", config)

        assert platform is None

    def test_create_card_builder(self):
        """测试创建卡片构建器实例"""
        IMPlatformFactory.register_platform(
            "feishu",
            MockPlatform,
            MockCardBuilder
        )

        builder = IMPlatformFactory.create_card_builder("feishu")

        assert builder is not None
        assert isinstance(builder, MockCardBuilder)

    def test_create_card_builder_unregistered_type(self):
        """测试创建未注册类型的卡片构建器"""
        builder = IMPlatformFactory.create_card_builder("unknown")

        assert builder is None

    def test_get_registered_platforms(self):
        """测试获取已注册的平台列表"""
        IMPlatformFactory.register_platform("feishu", MockPlatform, MockCardBuilder)
        IMPlatformFactory.register_platform("slack", MockPlatform, MockCardBuilder)

        registered = IMPlatformFactory.get_registered_platforms()

        assert isinstance(registered, list)
        assert "feishu" in registered
        assert "slack" in registered

    def test_is_platform_registered_true(self):
        """测试检查已注册的平台"""
        IMPlatformFactory.register_platform("feishu", MockPlatform, MockCardBuilder)

        assert IMPlatformFactory.is_platform_registered("feishu") is True

    def test_is_platform_registered_false(self):
        """测试检查未注册的平台"""
        assert IMPlatformFactory.is_platform_registered("unknown") is False

    def test_unregister_platform(self):
        """测试注销平台"""
        IMPlatformFactory.register_platform("feishu", MockPlatform, MockCardBuilder)

        result = IMPlatformFactory.unregister_platform("feishu")

        assert result is True
        assert not IMPlatformFactory.is_platform_registered("feishu")

    def test_unregister_platform_not_exists(self):
        """测试注销不存在的平台"""
        result = IMPlatformFactory.unregister_platform("unknown")

        assert result is False

    def test_create_platform_with_exception(self):
        """测试创建平台时抛出异常"""
        class FailingPlatform:
            def __init__(self, config):
                raise RuntimeError("Failed to initialize")

        IMPlatformFactory.register_platform(
            "failing",
            FailingPlatform,
            MockCardBuilder
        )

        config = PlatformConfig(
            app_id="test_app_id",
            app_secret="test_secret"
        )

        platform = IMPlatformFactory.create_platform("failing", config)

        assert platform is None

    def test_create_card_builder_with_exception(self):
        """测试创建卡片构建器时抛出异常"""
        class FailingCardBuilder:
            def __init__(self):
                raise RuntimeError("Failed to initialize")

        IMPlatformFactory.register_platform(
            "failing_builder",
            MockPlatform,
            FailingCardBuilder
        )

        builder = IMPlatformFactory.create_card_builder("failing_builder")

        assert builder is None