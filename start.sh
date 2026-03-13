#!/bin/bash

# Claude Feishu Integration 启动脚本

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

    # 额外检查：是否有其他 larkode.py 进程在运行
    RUNNING_PIDS=$(pgrep -f "larkode.py" 2>/dev/null)
    if [ -n "$RUNNING_PIDS" ]; then
        echo "警告: 发现运行中的 larkode.py 进程: $RUNNING_PIDs"
        echo "正在停止..."
        pkill -f "larkode.py"
        sleep 1
    fi
fi

# 安装依赖 (使用 uv)
echo "检查依赖..."
uv pip install -r requirements.txt --system 2>/dev/null || pip3 install -q -r requirements.txt

# 清缓存
find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

# 启动服务
echo "启动服务..."
nohup uv run --no-project larkode.py > logs/stdout.log 2>&1 &
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
