# 任务 007: 语音消息处理功能实现

## 目标

添加语音消息处理功能，支持：
- 接收语音消息
- 下载语音文件
- 识别语音格式并重命名
- 传递给 AI 处理

## 修改文件清单

| 文件路径 | 修改内容 |
|---------|---------|
| `src/interfaces/im_platform.py` | 添加 `VOICE = "voice"` 到 MessageType 枚举 |
| `src/im_platforms/feishu/__init__.py` | 1. 更新 `parse_event()` 识别 `msg_type == "audio"`<br>2. 添加 `create_download_voice_card()` 方法 |
| `src/feishu/file_ops.py` | 添加语音格式检测和扩展名重命名逻辑 |
| `src/handlers/attachment_handler.py` | 添加 `handle_voice_attachment()` 和 `handle_voice_message()` 方法 |
| `src/handlers/event_parser.py` | 在 `_handle_normalized_message()` 和 `_handle_message_receive()` 中添加语音处理分支 |
| `src/card_manager.py` | 添加 `create_download_voice_card()` 函数和 CARD_CONFIG 配置 |

## 实现状态

- [x] 1. 添加 VOICE 消息类型
- [x] 2. 更新飞书平台解析器
- [x] 3. 添加语音格式识别和重命名
- [x] 4. 添加语音消息处理器
- [x] 5. 添加语音下载卡片
- [x] 6. 更新事件处理器

## 完成说明

所有修改已完成并通过测试验证：
- 389 个单元测试全部通过
- 音频格式检测功能测试通过（支持 AMR, MP3, WAV, OGG, M4A, FLAC, AAC）
- 代码导入验证通过

## 语音消息处理流程

1. 用户发送语音消息 → 飞书推送 `msg_type: "audio"` 事件
2. `parse_event()` 将消息类型识别为 `MessageType.VOICE`
3. `event_parser.py` 调用 `handle_voice_attachment()` 或 `handle_voice_message()`
4. 发送下载确认卡片给用户
5. `download_file()` 下载语音文件并自动识别格式（重命名为正确扩展名）
6. 将语音路径作为命令 `Listen to the audio at {path}` 传递给 AI 助手
