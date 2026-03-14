# Claude Code Hook 交互场景测试指南

## 测试目的

通过触发各种 Claude Code 交互场景，记录 hook 事件的类型和结构，确定：
1. 哪些 hook 会触发交互请求
2. 交互数据的结构（options、title 等）
3. 是否支持单选、多选等不同类型

---

## 测试场景

### 场景1：权限确认（permission_prompt）

**测试步骤：**
1. 在 Claude Code 中执行一个需要权限的操作
   - 例如：修改系统文件、访问敏感信息等
2. 观察 hook 是否触发
3. 查看日志输出

**预期结果：**
- Hook 事件类型：`Notification`
- Notification 类型：`permission_prompt`
- Stdin 中包含交互数据（title、options）

---

### 场景2：选项选择（单选）（elicitation_dialog）

**测试步骤：**
1. 让 Claude Code 需要从多个选项中选择一个
   - 例如：询问选择代码风格、部署环境等
2. 观察 hook 是否触发
3. 查看日志输出

**预期结果：**
- Hook 事件类型：`Notification`
- Notification 类型：`elicitation_dialog`
- Stdin 中包含单选选项列表

---

### 场景3：Yes/No 确认

**测试步骤：**
1. 让 Claude Code 执行一个需要确认的操作
2. 观察 hook 是否触发
3. 查看日志输出

**预期结果：**
- 可能是 `Notification` 事件
- 可能包含简单的 Yes/No 选项

---

### 场景4：空闲提示（idle_prompt）

**测试步骤：**
1. 让 Claude Code 等待一段时间不操作
2. 触发空闲提示
3. 查看日志输出

**预期结果：**
- Hook 事件类型：`Notification`
- Notification 类型：`idle_prompt`
- 可能包含"继续"选项

---

## 测试设置

### 1. 配置 Hook 脚本

编辑 `~/.claude/settings.json`，添加或修改 hook 配置：

```json
{
  "hooks": [
    {
      "type": "UserPromptSubmit",
      "command": ["python3", "/path/to/larkode/tests/test_hook_interaction_scenarios.py"]
    },
    {
      "type": "Stop",
      "command": ["python3", "/path/to/larkode/tests/test_hook_interaction_scenarios.py"]
    },
    {
      "type": "Notification",
      "command": ["python3", "/path/to/larkode/tests/test_hook_interaction_scenarios.py"]
    }
  ]
}
```

### 2. 获取项目路径

确保路径正确，可以先用 `pwd` 获取完整路径：

```bash
cd /path/to/larkode
pwd  # 获取完整路径，如 /path/to/larkode
```

然后更新 settings.json 中的路径。

---

## 运行测试

### 方法1：自动触发（推荐）

1. 在 Claude Code 中执行各种交互场景
2. Hook 脚本会自动记录事件
3. 查看日志文件：`./logs/hook_test/interaction_test_*.log`

### 方法2：手动测试 Hook 脚本

```bash
# 测试 Stop hook
echo '{"last_assistant_message": "测试消息"}' | python3 tests/test_hook_interaction_scenarios.py Stop

# 测试 Notification hook
echo '{"notification_type": "permission_prompt", "title": "测试标题", "message": "选项1\\n选项2\\n选项3"}' | python3 tests/test_hook_interaction_scenarios.py Notification

# 测试 UserPromptSubmit hook
echo '{"prompt": "测试用户输入"}' | python3 tests/test_hook_interaction_scenarios.py UserPromptSubmit
```

---

## 日志分析

### 日志文件位置
```
./logs/hook_test/interaction_test_YYYYMMDD_HHMMSS.log
```

### 日志格式示例

```
================================================================================
12:30:15 - Stop Hook 触发
================================================================================
{
  "hook_type": "Stop",
  "stdin_parsed": {...},
  "last_assistant_message": "...",
  "has_interaction": false
}

================================================================================
12:35:22 - Notification Hook 触发 - Type: permission_prompt
================================================================================
{
  "hook_type": "Notification",
  "notification_type": "permission_prompt",
  "stdin_parsed": {...},
  "session_id": "...",
  "has_interaction": true
}
```

### 关键关注点

1. **交互数据结构**：
   - `options` 字段是否存在
   - `title` 字段是否存在
   - `message` 或 `question` 字段的格式

2. **Hook 事件类型**：
   - `Stop` - 是否包含交互数据
   - `Notification` - 哪些 notification_type 有交互
   - `UserPromptSubmit` - 是否有交互请求

3. **Tool 调用**：
   - `AskUserQuestion` 工具的参数结构
   - `askUserQuestion` 工具的参数结构

---

## 测试记录表

| 场景 | Hook 事件 | Notification 类型 | 有交互数据 | 选项格式 | 测试日期 |
|--------|----------|----------------|------------|----------|----------|
| 权限确认 | 待测试 | permission_prompt | 待测试 | 待测试 | |
| 选项单选 | 待测试 | elicitation_dialog | 待测试 | 待测试 | |
| Yes/No | 待测试 | ? | 待测试 | 待测试 | |
| 空闲提示 | 待测试 | idle_prompt | 待测试 | 待测试 | |

---

## 注意事项

1. **路径问题**：确保使用绝对路径，否则 hook 可能找不到脚本
2. **权限问题**：确保脚本有执行权限 `chmod +x`
3. **日志查看**：日志会追加，测试完成后记得清空或查看最新
4. **Hook 重载**：修改 settings.json 后，Claude Code 可能需要重载
