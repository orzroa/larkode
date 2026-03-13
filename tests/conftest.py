"""
pytest 配置 - 设置全局测试模式
"""
import pytest
import os
from pathlib import Path

# 加载项目 .env 文件
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def pytest_configure(config):
    """pytest 启动时设置测试模式"""
    os.environ["TEST_MODE_ENABLED"] = "true"


def pytest_unconfigure(config):
    """pytest 结束时清除测试模式"""
    os.environ.pop("TEST_MODE_ENABLED", None)
