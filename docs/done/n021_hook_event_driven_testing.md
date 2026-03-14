# Hook 事件驱动的自动化测试方案

## 背景

在 Hook 场景下调试和测试非常困难，因为：
1. Hook 事件是被动触发的，难以主动模拟
2. 每次测试都需要实际触发 AI 交互
3. 无法进行批量回归测试
4. 测试覆盖率低

## 解决方案

通过分析 Hook 日志文件 (`logs/hook_events.jsonl`) 中记录的真实事件，实现：
1. **自动捕获** - 每次 Hook 触发都会自动记录 stdin 数据
2. **离线测试** - 使用记录的报文进行离线测试
3. **批量测试** - 可以一次性测试多个历史事件
4. **回归测试** - 使用真实数据作为回归测试基准

## 使用方法

### 方案 1：直接从日志文件测试

```bash
# 运行测试（自动从日志读取最新事件）
python3 -m pytest tests/test_hook_from_log.py -v

# 查看详细输出
python3 -m pytest tests/test_hook_from_log.py -v -s
```

### 方案 2：生成 Fixture 文件

```bash
# 生成 fixture 文件（包含最新的 10 个事件）
python3 tests/generate_hook_fixtures.py --count 10

# 指定日志文件路径
HOOK_LOG_PATH=/path/to/hook_events.jsonl python3 tests/generate_hook_fixtures.py

# 生成的文件位于 tests/hook_fixtures/
```

### 方案 3：手动添加模拟事件

在 `tests/test_hook_from_log.py` 的 `TestHookSimulatedEvents` 类中添加测试用例：

```python
def test_my_custom_scenario(self):
    """自定义测试场景"""
    tool_input = {
        "questions": [
            {
                "question": "您的问题",
                "options": [{"label": "选项 1", "description": "描述"}],
                "multiSelect": False
            }
        ]
    }
    message = _build_permission_content("AskUserQuestion", tool_input)
    assert "选项 1" in message
```

## 日志文件格式

`logs/hook_events.jsonl` 是 JSONL 格式（每行一个 JSON 对象）：

```json
{
  "timestamp": "2026-03-07T16:20:23.293999",
  "handler": "default",
  "hook_event": "UserPromptSubmit",
  "stdin_parsed": {
    "session_id": "2994d096-2063-4d9c-876d-8de1cfd9dc27",
    "cwd": "/home/ubuntu/Workspaces/github/larkode",
    "hook_event_name": "UserPromptSubmit",
    "prompt": "用户输入的问题内容"
  }
}
```

## 支持的事件类型

| 事件类型 | 说明 | 测试内容 |
|---------|------|---------|
| UserPromptSubmit | 用户提交问题 | 验证 prompt 内容记录 |
| Stop | AI 完成响应 | 验证最后一条消息 |
| PermissionRequest | 权限请求 | 验证交互消息构建（AskUserQuestion/ExitPlanMode/Bash） |
| Notification | 通知事件 | 验证通知消息 |

## 示例输出

```
tests/test_hook_from_log.py::TestHookFromLogs::test_user_prompt_submit_from_log
UserPromptSubmit prompt: 到 plan mode 下面触发一个问题给我...
PASSED

tests/test_hook_from_log.py::TestHookFromLogs::test_permission_request_exit_plan_mode_from_log
ExitPlanMode: plan length=4642
生成的消息：**退出 Plan Mode 确认**

当前 Plan 内容：
# Hook ID 生成收敛方案（终稿）
...
PASSED
```

## 高级用法

### 从 CI/CD 集成

```bash
# 在 CI 中运行 Hook 测试
python3 -m pytest tests/test_hook_from_log.py -v --tb=short

# 生成覆盖率报告
python3 -m pytest tests/test_hook_from_log.py -v --cov=src/hook_handler.py
```

### 性能测试

```bash
# 测试大量历史事件
python3 tests/generate_hook_fixtures.py --count 100 --skip-test-gen

# 批量处理性能
python3 -m pytest tests/hook_fixtures/test_hook_events_*.py -v
```

## 文件结构

```
tests/
├── test_hook_from_log.py          # 日志驱动的测试（动态读取）
├── generate_hook_fixtures.py      # Fixture 生成工具
└── hook_fixtures/                 # 生成的 fixture 文件
    ├── hook_events_20260307_162308.json
    └── test_hook_events_*.py      # 自动生成的测试文件
```

## 维护建议

1. **定期清理日志** - 日志文件可能很大，定期归档旧数据
2. **选择代表性事件** - 生成 fixture 时选择有代表性的事件
3. **更新回归测试集** - 当 Hook 格式变化时更新测试用例
4. **监控失败事件** - 失败的 Hook 事件应该单独保存用于调试

## 未来改进

- [ ] 支持录制/回放模式
- [ ] 添加性能基准测试
- [ ] 支持不同 AI 助手（iFlow）的 Hook 格式
- [ ] 添加可视化测试报告
