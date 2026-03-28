#!/bin/bash

# Claude Feishu Integration 停止脚本

PID_FILE="data/service.pid"

# 优先使用 PID 文件
if [ -f "$PID_FILE" ]; then
    MAIN_PID=$(cat $PID_FILE)
    if [ -n "$MAIN_PID" ] && kill -0 $MAIN_PID 2>/dev/null; then
        echo "停止服务 (PID: $MAIN_PID)..."
        kill $MAIN_PID 2>/dev/null || true
        sleep 2

        # 检查是否还在运行
        if kill -0 $MAIN_PID 2>/dev/null; then
            echo "进程未响应，强制停止..."
            kill -9 $MAIN_PID 2>/dev/null || true
            sleep 1
        fi
    fi
    rm -f $PID_FILE
fi

# 强制杀掉所有 larkode.py 进程
PIDS=$(pgrep -f "larkode.py")
if [ -n "$PIDS" ]; then
    echo "强制停止所有 larkode.py 进程: $PIDS"
    for pid in $PIDS; do
        kill -9 $pid 2>/dev/null || true
    done
fi

# 再次检查是否还有残留进程
REMAINING=$(pgrep -f "larkode.py")
if [ -z "$REMAINING" ]; then
    echo "服务已停止"
else
    echo "警告: 仍有残留进程: $REMAINING"
fi
