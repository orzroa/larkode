#!/bin/bash
# 只运行单个测试用例的脚本

cd /home/ubuntu/Workspaces/github/larkode

# 使用 uv run 确保使用正确的环境
uv run --no-project python -m pytest tests/test_exceptions.py::TestBaseAppError::test_base_error_creation -v
