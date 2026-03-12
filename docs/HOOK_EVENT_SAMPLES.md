# Hook 报文完整样本（14 种类型）

基于 `logs/hook_events.jsonl` 的分析，我们共有 **14 种** 不同的 Hook 事件类型。

## 样本数据提取

运行以下命令提取每种类型的样本：

```bash
python3 tests/generate_hook_fixtures.py --count 100 --skip-test-gen
```

## 事件类型总览

| 序号 | 事件类型 | 说明 | 处理优先级 |
|-----|---------|------|----------|
| 1 | UserPromptSubmit | 用户提交问题 | 高 - 已处理 |
| 2 | Stop | AI 完成响应 | 高 - 已处理 |
| 3 | PreToolUse | 工具使用前（新权限请求） | 高 - 已处理 |
| 4 | PermissionRequest | 权限请求（旧格式） | 高 - 已处理 |
| 5 | Notification | 通知事件 | 中 - 已处理 |
| 6 | PostToolUse | 工具使用后 | 中 - 已记录 |
| 7 | PostToolUseFailure | 工具使用失败 | 中 - 已处理 |
| 8 | SubagentStop | 子代理完成 | 中 - 已处理 |
| 9 | SessionStart | 会话开始 | 低 - 已定义 |
| 10 | SessionEnd | 会话结束 | 低 - 已定义 |
| 11 | AskUserQuestion | 独立问答事件 | 低 - 已定义 |
| 12 | ConfigChange | 配置变更 | 低 - 已定义 |

## 处理逻辑覆盖

### 高优先级（已实现）

1. **UserPromptSubmit** - 发送用户提问通知到飞书
2. **Stop** - 发送完成通知到飞书
3. **PreToolUse** - 发送工具使用前权限请求
4. **PermissionRequest** - 发送权限请求（旧格式兼容）
5. **Notification** - 发送通知卡片
6. **PostToolUseFailure** - 发送工具使用失败通知
7. **SubagentStop** - 发送子代理完成通知

### 中优先级（已记录）

8. **PostToolUse** - 记录日志（可选发送通知）

### 低优先级（已定义，待实现）

9. **SessionStart** - 已定义事件类型
10. **SessionEnd** - 已定义事件类型
11. **AskUserQuestion** - 已定义事件类型
12. **ConfigChange** - 已定义事件类型

## 数据结构

### 通用字段

所有事件都包含以下基本字段：

```json
{
  "timestamp": "ISO8601 时间戳",
  "hook_event": "事件类型名称",
  "handler": "处理器名称 (default/iflow)",
  "hostname": "主机名",
  "stdin_parsed": {
    "session_id": "会话 ID",
    "transcript_path": "transcript 文件路径",
    "cwd": "工作目录",
    "permission_mode": "权限模式",
    "hook_event_name": "事件名称"
    // 其他字段根据事件类型不同而不同
  }
}
```

### 各类型特有字段

| 事件类型 | 特有字段 |
|---------|---------|
| UserPromptSubmit | `prompt`: 用户问题 |
| Stop | `last_assistant_message`: AI 最后消息 |
| PreToolUse | `tool_name`, `tool_input` |
| PermissionRequest | `tool_name`, `tool_input` |
| Notification | `notification_message` |
| PostToolUse | `tool_name`, `tool_result` |
| PostToolUseFailure | `tool_name`, `tool_result` |
| SubagentStop | `last_assistant_message` |
| AskUserQuestion | `tool_name`, `tool_input.questions` |

## 测试覆盖

```bash
# 运行所有 Hook 测试
python3 -m pytest tests/test_hook_from_log.py -v

# 生成包含所有类型的 fixture
python3 tests/generate_hook_fixtures.py --count 200
```

## 历史数据

所有历史 Hook 事件都保存在 `logs/hook_events.jsonl` 中，可以用于：
- 回归测试
- 数据分析
- 问题排查
