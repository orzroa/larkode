"""
IM 平台实现包

包含不同 IM 平台的具体实现
"""
from src.im_platforms.feishu import (
    FeishuPlatform,
    FeishuCardBuilder,
    register_feishu_platform
)

# Slack 平台（可选，需要安装依赖）
try:
    from src.im_platforms.slack import (
        SlackPlatform,
        SlackCardBuilder,
        register_slack_platform
    )
    _slack_available = True
except ImportError:
    _slack_available = False

__all__ = [
    "FeishuPlatform",
    "FeishuCardBuilder",
    "register_feishu_platform",
    # Slack 平台（如果可用）
    "SlackPlatform" if _slack_available else None,
    "SlackCardBuilder" if _slack_available else None,
    "register_slack_platform" if _slack_available else None,
]

# 过滤掉 None 值
__all__ = [x for x in __all__ if x is not None]

# 自动注册飞书平台
register_feishu_platform()
