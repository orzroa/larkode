# N008 - 长内容文件发送功能

## 任务描述

当机器人通过飞书发出的消息内容超过 `CARD_MAX_LENGTH` 时，改用文件方式发送完整内容，避免内容被截断。

## 实现内容

### 1. 配置更新 (config/settings.py)

- 新增 `USE_FILE_FOR_LONG_CONTENT`: 是否启用文件发送模式，默认 `true`
- 新增 `UPLOAD_DIR`: 上传文件存储目录，默认 `./uploads`（与图片下载共用）
- 在 `init_directories()` 中确保 `UPLOAD_DIR` 目录被创建

### 2. FeishuAPI 新增方法 (src/feishu/__init__.py)

- `upload_file(file_path, file_type)`: 上传文件到飞书，返回 file_key
- `send_file_message(user_id, file_key, message_number)`: 发送文件类型消息
- `send_result_with_file(...)`: 发送结果卡片和文件消息的组合

### 3. CardBuilder 截断逻辑更新 (src/feishu/__init__.py)

- `create_result_card()`: 返回 `(card_json, need_file, file_content)` 元组
- `create_tmux_card()`: 返回 `(card_json, need_file, file_content)` 元组
- 当 `USE_FILE_FOR_LONG_CONTENT=true` 且内容超长时：
  - `need_file=True`
  - `file_content` 包含完整内容
  - 卡片只显示摘要并提示"完整内容已保存为文件"

### 4. TaskManager 更新 (src/task_manager.py)

- `_send_result()` 方法处理新的返回值
- 当 `need_file=True` 时：
  - 将完整内容写入 `UPLOAD_DIR` 下的文件
  - 文件名格式：`result_{task_id_short}_{timestamp}.txt`
  - 上传文件获取 file_key
  - 发送文件消息和提示卡片
  - 上传失败时回退到截断卡片

### 5. MessageHandler 更新 (src/message_handler.py)

- `_cmd_shot()` 方法处理 tmux 输出卡片的新返回值
- 实现类似的文件发送逻辑

### 6. 接口定义更新 (src/interfaces/card_builder.py)

- `create_tmux_card()` 返回类型更新为 `Tuple[str, bool, str]`

### 7. 测试更新 (tests/test_card_builder.py)

- 更新测试用例适配新的返回值格式
- 添加长内容触发文件模式的测试

### 8. .env.example 更新

- 添加 `USE_FILE_FOR_LONG_CONTENT=true`
- 添加 `UPLOAD_DIR=./uploads`

## 技术细节

### 文件上传 API

使用飞书 `lark_oapi` SDK 的 `client.im.v1.file.create()` 上传文件，流程：
1. 打开文件（二进制模式）
2. 构建请求，指定 file_type、file_name 和 file
3. 调用 API 获取 file_key
4. 使用 `client.im.v1.message.create()` 发送 `msg_type="file"` 消息

### 文件命名规则

- 结果文件：`result_{task_id前8位}_{时间戳}.txt`
- tmux 输出文件：`tmux_output_{时间戳}.txt`

### 错误处理

- 文件上传失败时回退到截断卡片发送
- 确保不会因为文件上传失败而导致任务结果丢失

## 配置项

| 环境变量 | 说明 | 默认值 |
|----------|------|--------|
| `USE_FILE_FOR_LONG_CONTENT` | 是否启用文件发送模式 | `true` |
| `UPLOAD_DIR` | 上传文件存储目录 | `./uploads` |


- `USE_FILE_FOR_LONG_CONTENT` 默认为 `true`，可设置为 `false` 回退到截断模式
- 现有功能不受影响

## 待优化

- [ ] 定期清理过期临时文件（如超过 7 天的文件）
- [ ] 支持更多文件类型（json、md 等）

## 测试验证

### 测试结果
- ✅ 卡片构建测试通过 (9 passed)
- ✅ 任务管理器测试通过 (9 passed)
- ✅ 文件上传成功（使用 file_type='stream'）
- ✅ 消息发送验证：1 条文件消息 + 1 条卡片消息

### 文件上传 API 修正
- 问题：初始使用 `file_type="txt"` 导致上传失败（错误码 234001）
- 解决：改用 `file_type="stream"` 成功上传

### 修复重复发送问题
- 问题：测试脚本中错误地调用了两次 `send_file_message`
  - 第一次：直接调用 `send_file_message`
  - 第二次：`send_result_with_file` 内部再次调用
- 解决：删除测试脚本中的第一次调用，只使用 `send_result_with_file`
