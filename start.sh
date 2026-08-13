#!/bin/bash

# 配置、日志、数据库和上传内容仅允许服务用户访问。
umask 077

# Claude Feishu Integration 启动脚本

# larkode 会再启动 Codex App Server。若从 Codex 自己的受管终端启动，内部
# sandbox 会嵌套在外层 bwrap/network namespace 中，常见结果是：
# bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted
if [ -n "${CODEX_PERMISSION_PROFILE:-}" ] || [ -n "${CODEX_THREAD_ID:-}" ]; then
    echo "错误: 检测到当前终端位于 Codex 受管沙箱中。"
    echo "请在普通系统终端中重新运行: cd $(pwd) && ./start.sh"
    echo "不要从 Codex/VS Code Agent 的命令执行窗口启动 larkode。"
    exit 1
fi

# 设置环境变量
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# 检查.env文件
if [ ! -f .env ]; then
    echo "错误: .env 文件不存在"
    echo "请复制 .env.example 为 .env 并配置相关参数"
    exit 1
fi

# 创建必要的目录
mkdir -p data logs

# 检查服务是否已在运行
PID_FILE="data/service.pid"
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "错误: 服务已在运行 (PID: $OLD_PID)"
        echo "请先停止现有服务: kill $OLD_PID"
        exit 1
    else
        # PID 文件存在但进程已退出，清理并继续
        echo "发现 stale PID 文件，清理后继续..."
        rm -f "$PID_FILE"
    fi

fi

# Supervisor 不写本脚本的 PID 文件；仍需阻止误启动第二个实例。
RUNNING_PIDS=$(pgrep -f '[l]arkode.py' 2>/dev/null || true)
if [ -n "$RUNNING_PIDS" ]; then
    echo "错误: 已有 larkode.py 进程运行: $RUNNING_PIDS"
    echo "如果由 Supervisor 管理，请使用 supervisorctl restart larkode。"
    exit 1
fi

# 确保虚拟环境存在（避免 PEP 668 externally-managed-environment 错误）
if [ ! -d ".venv" ]; then
    echo "创建虚拟环境 .venv..."
    uv venv
fi

# 在虚拟环境中安装依赖
echo "检查依赖..."
uv pip install -r requirements.lock || {
    echo "错误: 依赖安装失败"
    exit 1
}

# 清缓存
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# 启动服务（使用虚拟环境的 Python，避免依赖缺失）
echo "启动服务..."
nohup .venv/bin/python larkode.py > logs/stdout.log 2>&1 &
PID=$!
echo $PID > "$PID_FILE"
echo "服务已启动 (PID: $PID)"
echo "日志: logs/stdout.log"

# 等待 2 秒确认服务启动成功
sleep 2
if ps -p "$PID" > /dev/null 2>&1; then
    echo "服务启动成功"
else
    echo "错误: 服务启动失败，请检查日志: logs/stdout.log"
    rm -f "$PID_FILE"
    exit 1
fi
