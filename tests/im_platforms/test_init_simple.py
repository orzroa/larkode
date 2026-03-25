"""
简单测试 im_platforms __init__
"""
import src.im_platforms


def test_slack_available_flag():
    """测试 _slack_available 标志"""
    assert hasattr(src.im_platforms, '_slack_available')
    # 检查 __all__ 没有 None 值
    assert all(x is not None for x in src.im_platforms.__all__)
    # 检查飞书相关导入
    assert hasattr(src.im_platforms, 'FeishuPlatform')
    assert hasattr(src.im_platforms, 'FeishuCardBuilder')
    assert hasattr(src.im_platforms, 'register_feishu_platform')


def test_all_exports():
    """测试 __all__ 导出"""
    # 验证导出的内容都存在
    for export in src.im_platforms.__all__:
        assert hasattr(src.im_platforms, export)
