# 未识别的 #xxx 命令转为 AI 执行（固定在 larkode 空间）

## 背景

用户在飞书发送 `#xxx` 格式的命令时：
- 已知命令（#help/#cancel/#history 等）由 PlatformCommands 处理
- 未知命令之前会报错"未知命令"
- 用户希望未知的 `#xxx` 命令也能作为 AI 命令执行

同时希望：
- 固定在 larkode 空间执行（不影响用户当前工作空间）
- 跨应用可配置（用 Union ID）

## 任务

实现未识别的 `#xxx` 命令自动转为 AI 命令，固定在 larkode 空间执行。

## 设计

### CommandExecutor 负责调度

PlatformCommands 只处理已知命令，未识别返回 False。
CommandExecutor 看到 False 后，去掉 # 前缀，临时切换到 larkode 空间执行 AI 命令。

```python
# CommandExecutor.process_command
if is_platform_command:
    handled = await self._platform_commands.handle_command(user_id, command)
    if not handled:
        # 未识别 → 转为 AI 命令在 larkode 空间执行
        ai_command = command[1:].strip()
        if ai_command:
            await self._execute_in_larkode_space(user_id, ai_command)
```

### 临时切换空间

```python
# CommandExecutor._execute_in_larkode_space
async def _execute_in_larkode_space(self, user_id, command):
    original_workspace = workspace_manager.get_current_workspace()

    try:
        # 如果原本不是 larkode，才切换
        if original_workspace != larkode_path:
            workspace_manager.switch_workspace(larkode_path)
        # 复用 execute_command 逻辑
        await self.execute_command(user_id, command)
    finally:
        # 如果原本不是 larkode，再切回
        if original_workspace and original_workspace != larkode_path:
            workspace_manager.switch_workspace(original_workspace)
```

### FEISHU_MESSAGE_RECEIVE_ID_TYPE 重构

之前：默认 open_id
现在：union_id（跨应用通用）

新增自动转换：open_id → union_id（FeishuAPI.send_message 中实现）

```python
# FeishuAPI.send_message
if receive_id_type == "union_id" and user_id.startswith("ou_"):
    union_id = await self.open_id_to_union_id(user_id)
    receive_id = union_id
```

## 修改文件

1. `src/handlers/platform_commands.py` - `handle_command` 返回 bool
2. `src/handlers/command_executor.py` - 增加 `_execute_in_larkode_space`
3. `src/feishu/api.py` - 增加 `open_id_to_union_id` 和 `send_message` 自动转换
4. `tests/handlers/test_platform_commands.py` - 更新测试
5. `.env` - 使用 union_id
6. `.env.example` - 更新注释
7. `README.md` - 更新命令说明和用户 ID 获取方法

## 测试结果

49 个测试全部通过。

## 飞书测试

- 已知命令（#help/#cancel/#ws 等）正常工作
- 未识别的 #xxx 命令 → 去掉 # → 在 larkode 空间执行
- open_id → union_id 自动转换成功
- Stop hook 通知成功

## 反思

1. 一开始写得太复杂：直接发送命令到 tmux，后来改成复用 execute_command 逻辑
2. workspace 切换逻辑：原空间 == larkode 时不需要切换
3. match/case 比 if/elif 链更清晰
4. handle_command 返回 bool 让上下游职责分明

## 后续 TODO

- [ ] 加 daily 文档到 roadmap
- [ ] 考虑缓存 union_id 减少 API 调用
