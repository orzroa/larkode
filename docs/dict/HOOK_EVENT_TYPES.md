# Hook 报文类型完全梳理

## 统计信息

基于 `logs/hook_events.jsonl` 中的 **3795** 个事件分析：

| 事件类型 | 数量 | 说明 |
|---------|------|------|
| UserPromptSubmit | 1287 | 用户提交问题 |
| Stop | 1057 | AI 完成响应 |
| PreToolUse | 656 | 工具使用前（权限请求） |
| Notification | 313 | 通知事件 |
| PermissionRequest | 220 | 权限请求 |
| PostToolUse | 205 | 工具使用后 |
| SubagentStop | 33 | 子代理完成 |
| SessionStart | 7 | 会话开始 |
| SessionEnd | 6 | 会话结束 |
| PostToolUseFailure | 5 | 工具使用失败 |
| TestEvent | 2 | 测试事件 |
| AskUserQuestion | 2 | 用户问答（独立事件） |
| ConfigChange | 1 | 配置变更 |
| Unknown | 1 | 未知事件 |

## Tool 类型分布

| Tool 名称 | 数量 | 说明 |
|----------|------|------|
| Bash | 555 | 执行 shell 命令 |
| Read | 207 | 读取文件 |
| Edit | 108 | 编辑文件 |
| Grep | 93 | 搜索文本 |
| ExitPlanMode | 59 | 退出计划模式 |
| AskUserQuestion | 32 | 向用户提问 |
| Write | 18 | 写入文件 |
| Glob | 11 | 文件匹配 |
| TaskOutput | 3 | 任务输出 |

---

## 各类型报文结构

### 1. UserPromptSubmit

用户提交问题时的报文。

```json
{
  "hook_event": "UserPromptSubmit",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "bypassPermissions",
    "hook_event_name": "UserPromptSubmit",
    "prompt": "用户输入的问题内容"
  }
}
```

**处理逻辑**: 发送用户提问通知到飞书

---

### 2. Stop

AI 完成响应时的报文。

```json
{
  "hook_event": "Stop",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "bypassPermissions",
    "hook_event_name": "Stop",
    "stop_hook_active": false,
    "last_assistant_message": "AI 的最后一条回复内容"
  }
}
```

**处理逻辑**: 发送完成通知到飞书

---

### 3. PreToolUse

工具使用前的报文（新的权限请求格式）。

```json
{
  "hook_event": "PreToolUse",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "bypassPermissions",
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {
      "command": "ls -la",
      "description": "列出文件"
    }
  }
}
```

**处理逻辑**: 需要发送权限请求通知

---

### 4. PermissionRequest

权限请求报文（旧格式，与 PreToolUse 类似）。

```json
{
  "hook_event": "PermissionRequest",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "plan",
    "hook_event_name": "PermissionRequest",
    "tool_name": "ExitPlanMode",
    "tool_input": {
      "plan": "# 计划内容...\n\n## 步骤\n1. 第一步\n2. 第二步"
    }
  }
}
```

**处理逻辑**: 根据 tool_name 发送不同的交互请求

---

### 5. PostToolUse

工具使用后的报文。

```json
{
  "hook_event": "PostToolUse",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "bypassPermissions",
    "hook_event_name": "PostToolUse",
    "tool_name": "Bash",
    "tool_result": {
      "stdout": "命令输出",
      "stderr": "",
      "exit_code": 0
    }
  }
}
```

**处理逻辑**: 可以记录工具执行结果

---

### 6. Notification

通知事件报文。

```json
{
  "hook_event": "Notification",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "bypassPermissions",
    "hook_event_name": "Notification",
    "notification_message": "通知内容"
  }
}
```

**处理逻辑**: 发送通知到飞书

---

### 7. SubagentStop

子代理完成时的报文。

```json
{
  "hook_event": "SubagentStop",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "permission_mode": "bypassPermissions",
    "hook_event_name": "SubagentStop",
    "last_assistant_message": "子代理的最后一条消息"
  }
}
```

---

### 8. SessionStart

会话开始时的报文。

```json
{
  "hook_event": "SessionStart",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "hook_event_name": "SessionStart"
  }
}
```

---

### 9. SessionEnd

会话结束时的报文。

```json
{
  "hook_event": "SessionEnd",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "hook_event_name": "SessionEnd"
  }
}
```

---

### 10. AskUserQuestion（独立事件）

独立的问答事件。

```json
{
  "hook_event": "AskUserQuestion",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "hook_event_name": "AskUserQuestion",
    "tool_name": "AskUserQuestion",
    "tool_input": {
      "questions": [
        {
          "question": "您想选择哪个？",
          "header": "选择",
          "options": [
            {"label": "选项 A", "description": "描述 A"},
            {"label": "选项 B", "description": "描述 B"}
          ],
          "multiSelect": false
        }
      ]
    }
  }
}
```

---

### 11. ConfigChange

配置变更事件。

```json
{
  "hook_event": "ConfigChange",
  "stdin_parsed": {
    "session_id": "xxxxx",
    "transcript_path": "/path/to/transcript.jsonl",
    "cwd": "/path/to/working/dir",
    "hook_event_name": "ConfigChange",
    "changes": {
      "old": {},
      "new": {}
    }
  }
}
```

---

## 当前处理逻辑覆盖情况

| 事件类型 | 是否处理 | 说明 |
|---------|---------|------|
| UserPromptSubmit | ✅ | 已处理 - 发送用户提问通知 |
| Stop | ✅ | 已处理 - 发送完成通知 |
| PreToolUse | ❌ | 待添加 - 新格式的权限请求 |
| Notification | ✅ | 已处理 - 发送通知 |
| PermissionRequest | ✅ | 已处理 - 根据 tool_name 处理 |
| PostToolUse | ❌ | 可选 - 可记录工具执行结果 |
| SubagentStop | ❌ | 可选 - 可发送子代理完成通知 |
| SessionStart | ❌ | 可选 - 可记录会话开始 |
| SessionEnd | ❌ | 可选 - 可记录会话结束 |
| PostToolUseFailure | ❌ | 可选 - 可发送失败通知 |
| AskUserQuestion | ❌ | 待处理 - 独立问答事件 |
| ConfigChange | ❌ | 可选 - 可记录配置变更 |

---

## 后续工作

1. **添加 PreToolUse 处理** - 新的权限请求格式
2. **添加 PostToolUse 处理** - 记录工具执行结果
3. **完善测试覆盖** - 为每种类型添加测试用例
