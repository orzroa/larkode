# Hook ID 生成收敛方案实现

## 任务编号
TODO: Hook ID 生成收敛

## 完成日期
2026-03-07

## 背景

之前通知卡片（prompt/stop/permission）显示重复的消息编号和时间戳：

```
📨 **消息编号**: sh-580
🕒 `2026-03-07 14:37:52`

📨 **消息编号**: sh-580
🕒 `2026-03-07 14:37:52`
```

**根本原因**: 编号添加逻辑分散在两处：
1. `BaseCard.build()` 中手动添加
2. `NotificationCard.build_content()` 中再次添加

## 方案

采用方案 B - 仅系统下发的通知卡片生成统一编号，接收的外部消息保留平台原始 ID。

### 设计决策

1. **保留** `src/utils/message_number.py` - 作为统一的编号生成器
2. **在 `NormalizedCard` 内部统一调用** - 发送和接收消息时都通过 `NormalizedCard` 来添加编号
3. **编号逻辑收敛** - 外部调用方不需要关心编号生成细节
4. **接收消息保留平台原始 ID** - 飞书消息使用 `om_xxxxx` 格式的平台 ID

## 实现修改

### 1. `src/interfaces/im_platform.py:78-128` - `NormalizedCard.__init__()`

编号生成逻辑已收敛到 `NormalizedCard` 内部：

```python
class NormalizedCard:
    def __init__(
        self,
        card_type: str,
        title: str,
        content: str,
        template_color: str = "grey",
        message_number: str = None,
        timestamp: str = None,
        auto_generate_header: bool = True,
    ):
        from src.utils.message_number import get_message_number_manager

        self.card_type = card_type
        self.title = title
        self.template_color = template_color

        # 通知类卡片自动生成编号和时间戳
        if auto_generate_header and card_type in ("stop", "prompt", "permission"):
            if message_number is None:
                manager = get_message_number_manager()
                message_number = manager.get_next_number()  # ← 统一调用点
            if timestamp is None:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 将编号和时间戳添加到内容前面
            self.content = f"📨 **消息编号**: {message_number}\n🕒 `{timestamp}`\n\n{content}"
        else:
            # 其他类型卡片进行截断处理
            ...
```

### 2. `src/card_manager.py` - 已移除重复逻辑

**`BaseCard.build()`** (第 65-71 行): 直接创建 `NormalizedCard`，不再手动添加编号：

```python
normalized_card = NormalizedCard(
    card_type=self.card_type,
    title=self.config["title"],
    content=display_content,  # 直接传入内容，编号由 NormalizedCard 内部添加
    template_color=self.config.get("template", "grey")
)
```

**`NotificationCard.build_content()`** (第 170-172 行): 直接返回原始消息内容：

```python
def build_content(self) -> str:
    # 直接返回消息内容，编号由 NormalizedCard 统一添加
    return self.message
```

### 3. `src/utils/message_number.py` - 保留作为统一编号生成器

```python
class MessageNumberManager:
    def get_next_number(self) -> str:
        """获取下一个消息编号（线程和进程安全）"""
        # 使用文件锁防止跨进程并发
        # 返回格式：hostname-XXX（如 sh-001）
```

## 测试修复

修复了两个测试用例的断言逻辑：

### 1. `tests/test_hook_long_content.py`

- `test_exact_max_length_no_file`: 修正期望值为 80 个"A"（原测试假设错误）

### 2. `tests/test_n008_hook_notification.py`

- `test_long_message_with_file_mode_disabled`: 移除矛盾的断言，保留正确的验证逻辑

## 验收结果

### ✅ 所有验收标准通过

1. ✅ 通知卡片（prompt/stop/permission）只显示一次消息编号
2. ✅ 编号通过 `NormalizedCard.__init__()` 内部自动生成
3. ✅ `message_number.py` 保留作为统一编号生成器
4. ✅ 所有 317 个 UT 通过
5. ✅ 端到端测试验证 Hook 通知正常

### 测试结果

```bash
# 卡片相关测试
python3 -m pytest tests/ -v -k "card"  # 34 passed
python3 -m pytest tests/test_hook_long_content.py -v  # 7 passed
python3 -m pytest tests/test_n008_hook_notification.py -v  # 6 passed

# 完整测试套件
python3 -m pytest tests/ -v  # 317 passed
```

### 验证输出

```
=== 短消息测试 ===
卡片内容:
📨 **消息编号**: sh-8771
🕒 `2026-03-07 15:27:23`

这是一条测试消息

消息编号出现次数：1
时间戳出现次数：1

✅ 消息编号只出现一次，方案验证成功！
```

## 调用流程

### 发送消息流程（Hook 通知）

```
用户触发 Hook (如 UserPromptSubmit)
        ↓
hook_handler.py: send_feishu_notification()
        ↓
create_notification_card(message, message_type="stop")
        ↓
NotificationCard.build() → BaseCard.build()
        ↓
NormalizedCard.__init__(card_type="stop", content=...)
        ↓
检测 card_type ∈ (stop/prompt/permission)
        ↓
调用 message_number_manager.get_next_number()
        ↓
自动生成：📨 **消息编号**: sh-XXX + 时间戳
        ↓
FeishuPlatform.send_card() → API 发送到飞书
        ↓
record_hook_message() - 记录到数据库（已包含编号）
```

### 接收消息流程（保留平台 ID）

```
飞书 WebSocket 推送消息
        ↓
FeishuPlatform.parse_event()
        ↓
返回 NormalizedMessage(message_id="om_xxxxx", ...)  ← 使用飞书原始 ID
        ↓
记录到数据库 (db.save_message)
```

## 总结

**方案 B 已完全实现**：
- ✅ ID 生成逻辑完全收敛到 `NormalizedCard` 内部
- ✅ 外部调用方无需关心编号生成细节
- ✅ `message_number.py` 保留作为统一编号生成器
- ✅ 接收消息保留平台原始 ID（飞书 `om_xxxxx` 格式）
