"""
pytest 配置 - 设置全局测试模式
"""
import pytest
import os


def pytest_configure(config):
    """pytest 启动时设置测试模式"""
    os.environ["TEST_MODE_ENABLED"] = "true"


def pytest_unconfigure(config):
    """pytest 结束时清除测试模式"""
    os.environ.pop("TEST_MODE_ENABLED", None)
