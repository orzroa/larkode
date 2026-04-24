#!/bin/bash

# Claude Code 启动脚本
# 使用 larkode 的配置，在任意工作空间启动 Claude Code
#
# 用法：
#   cc.sh [工作空间路径]
#   如果不指定工作空间，使用当前目录
#
# 定位 larkode 项目的方式：
#   1. 环境变量 LARKODE_DIR
#   2. 从当前目录向上查找
#   3. 硬编码默认路径

set -e

# ===== 定位 larkode 项目 =====
find_larkode_dir() {
    # 优先级 1: 环境变量
    if [ -n "$LARKODE_DIR" ] && [ -d "$LARKODE_DIR" ]; then
        echo "$LARKODE_DIR"
        return 0
    fi

    # 优先级 2: 从当前目录向上查找 larkode 项目
    local current_dir=$(pwd)
    while [ "$current_dir" != "/" ]; do
        # 检查是否是 larkode 项目（通过特征文件识别）
        if [ -f "$current_dir/.env" ] && \
           grep -q "CLAUDE_CODE_CLI_PATH" "$current_dir/.env" 2>/dev/null && \
           [ -f "$current_dir/CLAUDE.md" ]; then
            echo "$current_dir"
            return 0
        fi
        # 向上一级
        current_dir=$(dirname "$current_dir")
    done

    # 优先级 3: 硬编码默认路径
    local default_path="$HOME/Workspaces/github/larkode"
    if [ -d "$default_path" ] && [ -f "$default_path/.env" ]; then
        echo "$default_path"
        return 0
    fi

    # 未找到
    return 1
}

# 查找 larkode 目录
LARKODE_DIR=$(find_larkode_dir)
if [ $? -ne 0 ]; then
    echo "❌ 错误：未找到 larkode 项目"
    echo ""
    echo "💡 解决方法："
    echo "  1. 设置环境变量: export LARKODE_DIR=/path/to/larkode"
    echo "  2. 在 larkode 项目或其子目录中运行"
    echo "  3. 确保 ~/Workspaces/github/larkode 存在"
    echo ""
    echo "📋 当前查找位置："
    echo "  - 环境变量 LARKODE_DIR: ${LARKODE_DIR:-未设置}"
    echo "  - 默认路径: ~/Workspaces/github/larkode"
    exit 1
fi

LARKODE_ENV="$LARKODE_DIR/.env"

# 检查 larkode/.env 是否存在
if [ ! -f "$LARKODE_ENV" ]; then
    echo "❌ 错误：未找到 larkode 配置文件: $LARKODE_ENV"
    echo "💡 请确保脚本位于 larkode 项目目录"
    exit 1
fi

echo "📋 加载 larkode 配置: $LARKODE_ENV"

# ===== 读取启动命令配置 =====
# 使用 awk 读取整行，避免 shell 解释分号等特殊字符
CLI_PATH=$(awk -F'=' '/^CLAUDE_CODE_CLI_PATH=/ {print substr($0, index($0, "=") + 1)}' "$LARKODE_ENV")
# 移除可能的前后引号
CLI_PATH="${CLI_PATH#\"}"
CLI_PATH="${CLI_PATH%\"}"
# 只展开 $HOME 等简单变量，不执行命令
# 使用 sed 替换，而不是 eval
CLI_PATH=$(echo "$CLI_PATH" | sed "s|~|$HOME|g" | sed "s|\$HOME|$HOME|g")

# 读取 WORKSPACE_ROOT_DIR 配置（用于生成 session 名称）
WORKSPACE_ROOT_DIR=$(awk -F'=' '/^WORKSPACE_ROOT_DIR=/ {print substr($0, index($0, "=") + 1)}' "$LARKODE_ENV")
WORKSPACE_ROOT_DIR="${WORKSPACE_ROOT_DIR#\"}"
WORKSPACE_ROOT_DIR="${WORKSPACE_ROOT_DIR%\"}"
WORKSPACE_ROOT_DIR=$(echo "$WORKSPACE_ROOT_DIR" | sed "s|~|$HOME|g" | sed "s|\$HOME|$HOME|g")

echo "📋 启动命令: $CLI_PATH"
echo ""

# ===== 确定工作空间 =====
# 如果提供了参数，使用参数；否则使用当前目录
if [ $# -ge 1 ]; then
    WORKSPACE="$1"
    # 如果是相对路径，转换为绝对路径
    if [[ "$WORKSPACE" != /* ]]; then
        WORKSPACE="$(cd "$WORKSPACE" && pwd)"
    fi
else
    WORKSPACE=$(pwd)
fi

# 验证工作空间存在
if [ ! -d "$WORKSPACE" ]; then
    echo "❌ 错误：工作空间不存在: $WORKSPACE"
    exit 1
fi

echo "📋 工作空间: $WORKSPACE"

# ===== 检查是否在 tmux 中 =====
if [ -n "$TMUX" ]; then
    echo "⚠️  你已经在 tmux session 中了"
    echo "当前 session: $(tmux display-message -p '#{session_name}')"
    echo ""
    echo "选项："
    echo "  1. 保持现状，继续使用当前 session"
    echo "  2. detach 当前 session: tmux detach"
    echo "  3. 切换到新 session: tmux switch-client -t <session-name>"
    exit 1
fi

# 从工作空间路径生成 session 名称（使用与 Python 相同的逻辑）
generate_session_name() {
    local workspace_path="$1"
    local workspace_root="${WORKSPACE_ROOT_DIR:-$HOME/Workspaces}"

    # 尝试使用相对于 workspace_root 的路径
    if [ -d "$workspace_root" ]; then
        # 计算相对路径（去掉 workspace_root 部分）
        local rel_path="${workspace_path#$workspace_root/}"
        if [ "$rel_path" != "$workspace_path" ] && [ -n "$rel_path" ]; then
            # 使用相对路径：dds/cccframework -> dds-cccframework
            echo "cc-${rel_path//\//-}"
            return 0
        fi
    fi

    # 回退策略：使用最后 2 级路径
    local parent_dir=$(dirname "$workspace_path")
    local project_name=$(basename "$workspace_path")
    local parent_name=$(basename "$parent_dir")

    # 如果父目录不是 Workspaces 或根目录，包含父目录名
    if [ "$parent_name" != "Workspaces" ] && [ "$parent_name" != "/" ]; then
        echo "cc-${parent_name}-${project_name}"
    else
        echo "cc-${project_name}"
    fi
}

SESSION_NAME=$(generate_session_name "$WORKSPACE")

echo "📋 工作空间: $WORKSPACE"
echo "📋 Session: $SESSION_NAME"
echo "📋 CLI 命令: $CLI_PATH"
echo ""

# 检查 session 是否已存在
if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "✅ Session '$SESSION_NAME' 已存在"

    # 检查 Claude Code 是否在运行
    CLI_KEYWORD=$(echo "$CLI_PATH" | awk '{print $NF}' | sed 's/--.*//g' | xargs basename)

    if tmux list-windows -t "$SESSION_NAME" -F '#{window_name}' | grep -q "ai"; then
        # 检查 ai window 中是否有 claude 进程
        PID=$(tmux list-windows -t "$SESSION_NAME" -F '#{window_panes}' | head -1)
        if pgrep -f "$CLI_KEYWORD" | grep -q "$(tmux display-message -t "$SESSION_NAME:ai" -p '#{pane_pid}')"; then
            echo "✅ Claude Code 正在运行"
        else
            echo "⚠️  Session 存在但 Claude Code 未运行"
            echo "启动 Claude Code..."
            tmux send-keys -t "$SESSION_NAME:ai" "CLAUDE_STARTUP=1 $CLI_PATH" Enter
            sleep 3
        fi
    fi

    echo ""
    echo "🔗 Attach 到 session: $SESSION_NAME"
    tmux attach-session -t "$SESSION_NAME"
else
    echo "🆕 创建新 session: $SESSION_NAME"

    # 使用 .env 中的完整配置（包含 -c 和 fallback）
    echo "  → 执行命令: CLAUDE_STARTUP=1 cd $WORKSPACE && $CLI_PATH"

    tmux new-session -d -s "$SESSION_NAME" -n "ai" \
        "CLAUDE_STARTUP=1 cd $WORKSPACE && $CLI_PATH"

    # 检查 session 是否创建成功
    if ! tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
        echo "❌ Session 创建失败"
        exit 1
    fi

    echo "  → Session 创建成功"

    # 设置环境变量，让 hook 能获取正确的工作空间
    tmux set-environment -t "$SESSION_NAME" AI_WORKSPACE_DIR "$WORKSPACE"

    # 等待启动
    sleep 3

    echo "✅ Claude Code 已启动"
    echo ""
    echo "🔗 Attach 到 session: $SESSION_NAME"
    echo "💡 提示: 按 Ctrl+B 然后按 D 可以 detach session"
    echo ""
    tmux attach-session -t "$SESSION_NAME"
fi