#!/bin/bash
# 运行所有测试，包括集成测试
# 测试结果会记录到 logs 目录，方便排查问题
#
# 用法:
#   ./run_all_tests.sh           # 运行测试，生成覆盖率报告
#   ./run_all_tests.sh --no-cov  # 运行测试，不生成覆盖率报告
#   ./run_all_tests.sh --cov-report  # 生成详细覆盖率报告（HTML）

set -e

# 解析命令行参数
NO_COV=false
COV_REPORT=false
for arg in "$@"; do
    case $arg in
        --no-cov) NO_COV=true ;;
        --cov-report) COV_REPORT=true ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMP_FILE="/tmp/test_output_$$.txt"

# 切换到项目目录
cd "$PROJECT_ROOT"

# 验证 uv 环境可用
if ! uv run python -c "import pytest" 2>/dev/null; then
    echo "错误: uv 环境未正确配置，请运行: uv sync"
    exit 1
fi

# 日志目录
LOG_DIR="$PROJECT_ROOT/logs"
mkdir -p "$LOG_DIR"

# 生成时间戳
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
TEST_LOG_FILE="$LOG_DIR/test_${TIMESTAMP}.log"

# 数据库路径
DB_PATH="$PROJECT_ROOT/data/larkode.db"

# 获取测试前的 id 范围
get_seq_before() {
    if [ -f "$DB_PATH" ]; then
        sqlite3 "$DB_PATH" "SELECT COALESCE(MAX(id), 0) FROM messages" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

# 获取测试后的统计信息
get_test_stats() {
    local seq_before=$1
    local seq_after=$(sqlite3 "$DB_PATH" "SELECT COALESCE(MAX(id), 0) FROM messages" 2>/dev/null || echo "0")

    if [ "$seq_after" -eq 0 ] || [ "$seq_after" -eq "$seq_before" ]; then
        echo "seq_before=$seq_before"
        echo "seq_after=$seq_after"
        echo "new_count=0"
        echo "is_test_0_count=0"
        echo "is_test_1_count=0"
        return
    fi

    # 查询新增消息的 is_test 分布
    local is_test_0_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM messages WHERE id > $seq_before AND is_test = 0" 2>/dev/null || echo "0")
    local is_test_1_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM messages WHERE id > $seq_before AND is_test = 1" 2>/dev/null || echo "0")
    local new_count=$((is_test_0_count + is_test_1_count))

    echo "seq_before=$seq_before"
    echo "seq_after=$seq_after"
    echo "new_count=$new_count"
    echo "is_test_0_count=$is_test_0_count"
    echo "is_test_1_count=$is_test_1_count"

    # 如果有 is_test=0 的消息，显示明细
    if [ "$is_test_0_count" -gt 0 ]; then
        echo "---is_test_0_messages---"
        sqlite3 "$DB_PATH" "SELECT 'id: ' || id || ', user_id: ' || user_id || ', content: ' || substr(content, 1, 50) FROM messages WHERE id > $seq_before AND is_test = 0" 2>/dev/null || true
    fi
}

cd "$PROJECT_ROOT"

# 记录测试开始前的 seq_id
SEQ_BEFORE=$(get_seq_before)
echo ""
echo "=== 测试前 seq_id: $SEQ_BEFORE ==="

# 覆盖率参数：pytest.ini 已默认启用，--no-cov 时禁用
COV_ARGS=""
if [ "$NO_COV" = true ]; then
    COV_ARGS="-p no:cov"
    echo "   覆盖率报告: 已禁用"
elif [ "$COV_REPORT" = true ]; then
    # --cov-report 只是额外生成 HTML，默认已经有了
    echo "   覆盖率报告: 已启用 (HTML)"
else
    echo "   覆盖率报告: 已启用"
fi

echo "=== 运行单元测试（单线程模式）==="
uv run pytest tests/ -v --ignore=tests/integration/ --ignore=tests/manual_test_hook_interaction_scenarios.py $COV_ARGS 2>&1 | tee "$TEMP_FILE"
# 从 pytest summary 中提取失败和通过的数量：X failed, Y passed
UNIT_FAILED=$(grep -Eo '[0-9]+ failed' "$TEMP_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")
UNIT_PASSED=$(grep -Eo '[0-9]+ passed' "$TEMP_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")

# 提取覆盖率百分比
if [ "$NO_COV" = false ]; then
    COVERAGE=$(grep -Eo 'TOTAL.*[0-9]+%' "$TEMP_FILE" 2>/dev/null | grep -oE '[0-9]+%' | tail -1 || echo "N/A")
fi
rm -f "$TEMP_FILE"

echo ""
echo "=== 运行集成测试（单线程模式）==="
export TEST_MODE_ENABLED=true
uv run pytest tests/integration/ -v 2>&1 | tee "$TEMP_FILE"
INT_FAILED=$(grep -Eo '[0-9]+ failed' "$TEMP_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")
INT_PASSED=$(grep -Eo '[0-9]+ passed' "$TEMP_FILE" 2>/dev/null | grep -oE '[0-9]+' | head -1 || echo "0")
rm -f "$TEMP_FILE"

echo ""
echo "============================================"
# 确保变量是数字
UNIT_FAILED=${UNIT_FAILED:-0}
UNIT_PASSED=${UNIT_PASSED:-0}
INT_FAILED=${INT_FAILED:-0}
INT_PASSED=${INT_PASSED:-0}

TOTAL_PASSED=$((UNIT_PASSED + INT_PASSED))
TOTAL_FAILED=$((UNIT_FAILED + INT_FAILED))

echo "   单元测试: ${UNIT_PASSED} 通过 / ${UNIT_FAILED} 失败"
echo "   集成测试: ${INT_PASSED} 通过 / ${INT_FAILED} 失败"
echo "   总计:     ${TOTAL_PASSED} 通过 / ${TOTAL_FAILED} 失败"
if [ "$NO_COV" = false ] && [ -n "$COVERAGE" ]; then
    echo "   覆盖率:   ${COVERAGE}"
fi
if [ "$NO_COV" = false ] && [ "$COV_REPORT" = true ]; then
    echo "   HTML报告: $PROJECT_ROOT/htmlcov/index.html"
fi
echo "============================================"

# 获取测试后的统计信息
echo ""
echo "=== 测试消息统计 ==="
TEST_STATS=$(get_test_stats $SEQ_BEFORE)
echo "$TEST_STATS" | while IFS= read -r line; do
    case "$line" in
        seq_before=*) echo "   测试前 seq_id: ${line#*=}" ;;
        seq_after=*) echo "   测试后 seq_id: ${line#*=}" ;;
        new_count=*) echo "   新增消息数: ${line#*=}" ;;
        is_test_0_count=*) echo "   is_test=0: ${line#*=}" ;;
        is_test_1_count=*) echo "   is_test=1: ${line#*=}" ;;
        ---is_test_0_messages---) echo ""; echo "   is_test=0 消息明细:" ;;
        seq_id:*|user_id:*|content:*) echo "      ${line}" ;;
    esac
done

# 检查是否所有新增消息都是 is_test=1
NEW_COUNT=$(echo "$TEST_STATS" | grep "new_count=" | cut -d= -f2)
IS_TEST_0_COUNT=$(echo "$TEST_STATS" | grep "is_test_0_count=" | cut -d= -f2)
if [ "$NEW_COUNT" -gt 0 ] && [ "$IS_TEST_0_COUNT" -eq 0 ]; then
    echo ""
    echo "   ✅ 所有新增消息 is_test=1 (符合预期)"
elif [ "$NEW_COUNT" -gt 0 ] && [ "$IS_TEST_0_COUNT" -gt 0 ]; then
    echo ""
    echo "   ⚠️  存在 is_test=0 的消息，请检查代码！"
fi

# 记录到日志文件
{
    echo "=== 自动化测试日志 ==="
    echo "时间: $TIMESTAMP"
    echo "单元测试: ${UNIT_PASSED} 通过 / ${UNIT_FAILED} 失败"
    echo "集成测试: ${INT_PASSED} 通过 / ${INT_FAILED} 失败"
    echo "总计: ${TOTAL_PASSED} 通过 / ${TOTAL_FAILED} 失败"
    if [ "$NO_COV" = false ] && [ -n "$COVERAGE" ]; then
        echo "覆盖率: ${COVERAGE}"
    fi
    if [ "$TOTAL_FAILED" -gt 0 ]; then
        echo "状态: ❌ 失败"
    else
        echo "状态: ✅ 通过"
    fi
} > "$TEST_LOG_FILE"

echo ""
echo "📝 测试日志: $TEST_LOG_FILE"

if [ "$TOTAL_FAILED" -gt 0 ]; then
    echo "❌ 有 ${TOTAL_FAILED} 个测试失败"
else
    echo "✅ 所有测试通过"
fi

# 测试全部通过后重启服务
if [ "$TOTAL_FAILED" -eq 0 ]; then
    echo ""
    echo "=== 重启服务以应用最新代码 ==="
    if [ -f "$PROJECT_ROOT/restart.sh" ]; then
        bash "$PROJECT_ROOT/restart.sh"
    else
        echo "未找到 restart.sh，跳过重启"
    fi
fi
