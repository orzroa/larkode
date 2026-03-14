# IM 消息全量记录方案实施说明

## 概述

本次实施完成了将所有通过飞书/IM 上行下发的消息全部存储到 messages 表中的功能。

## 实施内容

### 1. 数据库模型改造

**文件：** `src/models/__init__.py`

新增枚举类：
- `MessageDirection` - 消息方向枚举（UPSTREAM/DOWNSTREAM）
- `MessageSource` - 消息来源枚举（FEISHU/HOOK/API_TEST）

扩展 `Message` 模型：
- `direction: Optional[MessageDirection]` - 消息方向
- `is_test: bool` - 是否为测试消息
- `message_source: Optional[MessageSource]` - 消息来源
- `feishu_message_id: Optional[str]` - 飞书原始消息 ID

### 2. 存储层改造

**文件：** `src/storage/__init__.py`

数据库表结构变更：
- 添加 `direction` 列（TEXT）
- 添加 `is_test` 列（INTEGER，默认 0）
- 添加 `message_source` 列（TEXT）
- 添加 `feishu_message_id` 列（TEXT）
- 添加新索引：`idx_messages_direction`, `idx_messages_source`

新增查询方法：
- `get_messages_by_direction()` - 根据消息方向获取
- `get_messages_by_source()` - 根据消息来源获取
- `get_test_messages()` - 获取测试消息
- `get_message_statistics()` - 获取消息统计信息

### 3. 消息发送拦截

**文件：** `src/handlers/message_sender.py`

更新内容：
- `send()` 方法现在会自动记录所有下发的消息到数据库
- 添加 `set_current_task_id()` 方法设置当前任务 ID
- 添加 `set_test_mode()` 方法设置测试模式
- 支持传入 `task_id` 和 `message_type` 参数

### 4. 命令执行器更新

**文件：** `src/handlers/command_executor.py`

更新内容：
- `_is_test_user()` 方法检测测试用户（user_id 包含"test"字样）
- `process_command()` 现在记录上行消息，包含方向、来源、测试标记
- `execute_command()` 设置任务 ID 到消息发送器

### 5. Hook 消息记录

**文件：** `src/hook_handler.py`

新增功能：
- `_is_test_user()` 函数检测测试用户
- `record_hook_message()` 函数记录 Hook 消息到数据库
- `send_feishu_notification()` 调用 `record_hook_message()` 记录发送的消息

## 消息记录范围

| 消息类型 | 方向 | 来源 | 测试标记 | 实现位置 |
|---------|------|------|---------|---------|
| 用户命令消息 | UPSTREAM | FEISHU | 自动检测 | command_executor.py |
| AI 回复消息 | DOWNSTREAM | FEISHU | 自动检测 | message_sender.py |
| 卡片消息 | DOWNSTREAM | FEISHU | 自动检测 | message_sender.py |
| Hook 通知消息 | DOWNSTREAM | HOOK | 自动检测 | hook_handler.py |
| 测试消息 | 任意 | API_TEST | is_test=1 | 测试专用 |

## 测试标记逻辑

测试用户通过 `user_id` 自动检测：
- 包含 "test" 字样（不区分大小写）的 `user_id` 被视为测试用户
- 测试用户的消息 `is_test` 字段自动设置为 `True`

示例：
- `test_user_123` → is_test=True
- `user_test` → is_test=True
- `TEST_USER` → is_test=True
- `ou_123456` → is_test=False

## 查询示例

### 统计消息
```python
from src.storage import db

stats = db.get_message_statistics()
for stat in stats:
    print(f"方向：{stat['direction']}, 来源：{stat['message_source']}, "
          f"测试：{stat['is_test']}, 数量：{stat['count']}")
```

### 获取上行消息
```python
from src.models import MessageDirection

upstream_msgs = db.get_messages_by_direction(
    MessageDirection.UPSTREAM,
    user_id="ou_xxxxx",
    limit=50
)
```

### 获取 Hook 消息
```python
from src.models import MessageSource

hook_msgs = db.get_messages_by_source(
    MessageSource.HOOK,
    limit=50
)
```

### 获取测试消息
```python
test_msgs = db.get_test_messages(user_id="test_user", limit=50)
```

## 新增测试

**文件：** `tests/test_im_message_recording.py`

包含 17 个测试用例：
- 模型字段测试
- 枚举类测试
- 数据库操作测试
- 测试用户检测测试
- Hook 消息记录测试

## 验证方式

1. 运行集成测试，检查 messages 表是否有 `is_test=1` 的记录
2. 发送真实飞书消息，检查 `direction='upstream'` 和 `'downstream'`
3. 检查 Hook 通知是否被记录（message_source='hook'）
4. 查询统计：
```sql
SELECT direction, message_source, is_test, COUNT(*) as count
FROM messages
GROUP BY direction, message_source, is_test;
```

## 向后兼容性

- 所有新字段均为可选字段（Optional 或带默认值）
- 数据库迁移自动执行（检测列不存在时自动添加）
- 现有代码无需修改即可运行

## 相关文件

| 文件 | 修改内容 |
|------|---------|
| `src/models/__init__.py` | 新增枚举类，扩展 Message 模型 |
| `src/storage/__init__.py` | 扩展表结构，新增查询方法 |
| `src/handlers/message_sender.py` | 添加消息记录逻辑 |
| `src/handlers/command_executor.py` | 添加上行消息记录和测试用户检测 |
| `src/hook_handler.py` | 添加 Hook 消息记录功能 |
| `tests/test_im_message_recording.py` | 新增集成测试 |

## 测试结果

- 所有 317 个测试通过（包括新增的 17 个测试）
- 无破坏性变更
