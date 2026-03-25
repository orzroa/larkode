"""
测试 im_platforms 的 Slack 导入 fallback
"""
import sys
import importlib
from unittest.mock import patch


def test_slack_import_fallback():
    """测试 Slack 导入失败时的 fallback 逻辑"""
    # 清除缓存
    for mod in ['src.im_platforms', 'src.im_platforms.slack']:
        if mod in sys.modules:
            del sys.modules[mod]

    # 模拟导入 Slack 失败
    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == 'src.im_platforms.slack':
            raise ImportError("Slack module not available")
        return original_import(name, *args, **kwargs)

    with patch('builtins.__import__', side_effect=mock_import):
        # 重新导入模块
        import src.im_platforms
        importlib.reload(src.im_platforms)

        # 验证 Slack 相关导出不存在
        assert not hasattr(src.im_platforms, 'SlackPlatform')
        assert not hasattr(src.im_platforms, 'SlackCardBuilder')
        assert not hasattr(src.im_platforms, 'register_slack_platform')

        # 验证 __all__ 中没有 Slack 相关内容
        assert 'SlackPlatform' not in src.im_platforms.__all__
        assert 'SlackCardBuilder' not in src.im_platforms.__all__
        assert 'register_slack_platform' not in src.im_platforms.__all__

        # 验证 _slack_available 为 False
        assert src.im_platforms._slack_available is False
