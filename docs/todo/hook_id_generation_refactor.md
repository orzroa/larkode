# Hook ID 生成收敛方案

## 问题现状

当前消息编号在卡片显示时出现**重复**：

```
📨 **消息编号**: sh-580
🕒 `2026-03-07 14:37:52`

📨 **消息编号**: sh-580
🕒 `2026-03-07 14:37:52`
```

### 根本原因

编号添加逻辑分散在两处：

1. **`src/card_manager.py` - `BaseCard.build()`** (第 66-72 行)
2. **`src/card_manager.py` - `NotificationCard.build_content()`** (第 180-186 行)

**问题：** `NotificationCard` 被 `BaseCard.build()` 调用，导致编号被添加了**两次**！

---

## 用户要求

> "保留 message_number 这个类，在 normalized card 里面统一调用。发送的时候调用它，接收的时候也要调用它。"

**理解：**
1. **保留** `src/utils/message_number.py` - 作为统一的编号生成器
2. **在 `NormalizedCard` 内部统一调用** - 发送和接收消息时都通过 `NormalizedCard` 来添加编号
3. **编号逻辑收敛** - 外部调用方不需要关心编号生成细节

---

## 设计方案

### 核心思想

将编号生成逻辑**完全收敛到 `NormalizedCard` 内部**：

```
┌─────────────────────────────────────────────────────────┐
│                   NormalizedCard                        │
│  ┌─────────────────────────────────────────────────┐   │
│  │  __init__() 中统一调用 message_number 管理器     │   │
│  │  - 如果是通知类卡片 (stop/prompt/permission)      │   │
│  │    自动生成 message_number 和 timestamp          │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
         ↓                        ↓
  发送消息时调用           接收消息时调用
  NormalizedCard(...)     NormalizedCard(...)
```

### 修改内容

#### 1. `src/interfaces/im_platform.py` - `NormalizedCard.__init__()`

在当前代码中（第 89-109 行），已经有导入 `message_number`，但**未实际使用**。需要修改为：

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
        auto_generate_header: bool = True,  # 新增参数
    ):
        from datetime import datetime
        from src.utils.message_number import get_message_number_manager

        self.card_type = card_type
        self.title = title
        self.template_color = template_color

        # 通知类卡片自动生成编号和时间戳
        if auto_generate_header and card_type in ("stop", "prompt", "permission"):
            if message_number is None:
                manager = get_message_number_manager()
                message_number = manager.get_next_number()
            if timestamp is None:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 将编号和时间戳添加到内容前面
            self.content = f"📨 **消息编号**: {message_number}\n🕒 `{timestamp}`\n\n{content}"
        else:
            self.content = content

        self.message_number = message_number
        self.timestamp = timestamp
```

#### 2. `src/card_manager.py` - `BaseCard.build()`

**移除**编号添加逻辑（第 65-72 行），因为 `NormalizedCard` 内部已经处理：

```python
def build(self) -> str | Tuple[str, bool, str]:
    raw_content = self.build_content()

    # 处理内容长度（保持不变）
    need_file = False
    file_content = ""
    display_content = raw_content

    if self.card_type in ("stop", "prompt", "permission"):
        max_length = int(os.getenv("CARD_MAX_LENGTH", str(get_settings().CARD_MAX_LENGTH)))
        use_file = os.getenv("USE_FILE_FOR_LONG_CONTENT", "true").lower() == "true"
        need_file = use_file and len(raw_content) > max_length

        if need_file:
            file_content = raw_content
            display_content = raw_content[:max_length] + "\n... (完整内容已保存为文件)"
        elif len(raw_content) > max_length:
            display_content = raw_content[:max_length] + "\n... (内容过长，已截断)"

    # ❌ 移除：不再在这里添加编号和时间戳
    # ✅ NormalizedCard 内部会自动处理

    normalized_card = NormalizedCard(
        card_type=self.card_type,
        title=self.config["title"],
        content=display_content,  # 直接传入内容，不需要手动添加编号
        template_color=self.config.get("template", "grey")
    )
    # ...
```

#### 3. `src/card_manager.py` - `NotificationCard.build_content()`

**移除**编号添加逻辑（第 180-186 行）：

```python
class NotificationCard(BaseCard):
    def build_content(self) -> str:
        # ✅ 直接返回消息内容，编号由 NormalizedCard 统一添加
        return self.message
```

#### 4. 接收消息时使用 `NormalizedCard`

在 `FeishuPlatform.parse_event()` 中，如果需要为接收的消息添加编号：

```python
def parse_event(self, event_data: Dict[str, Any]) -> Optional[NormalizedMessage]:
    # 接收消息时，也可以通过 NormalizedCard 来添加编号
    # 例如：创建接收消息的卡片记录
    card = NormalizedCard(
        card_type="received",
        title="收到消息",
        content=content,
        auto_generate_header=True  # 同样自动生成编号
    )
```

---

## 调用流程

### 发送消息流程

```
MessageSender.send_card(user_id, NormalizedCard(...))
                              ↓
                   NormalizedCard.__init__()
                              ↓
            检测 card_type ∈ (stop/prompt/permission)
                              ↓
            调用 message_number_manager.get_next_number()
                              ↓
            自动生成：message_number + timestamp
                              ↓
            添加到 content 前面
                              ↓
            发送到平台
```

### 接收消息流程

```
FeishuPlatform.parse_event(event_data)
                              ↓
              NormalizedMessage(...)  ← 接收消息
              或
              NormalizedCard(...)     ← 如果需要记录接收的卡片
                              ↓
            同样可以调用 message_number_manager
            生成统一的编号
```

---

## 修改清单

### 1. `src/interfaces/im_platform.py:78-120`
- **修改** `NormalizedCard.__init__()`：添加 `auto_generate_header` 参数
- **在** `__init__()` 中直接调用 `message_number_manager.get_next_number()` 生成编号

### 2. `src/card_manager.py:65-72`
- **移除** `BaseCard.build()` 中的编号添加逻辑

### 3. `src/card_manager.py:172-186`
- **移除** `NotificationCard.build_content()` 中的编号获取逻辑

### 4. `src/utils/message_number.py`
- **保留**作为统一的编号生成器

---

## 验收标准

1. 通知卡片（prompt/stop/permission）只显示**一次**消息编号
2. 编号通过 `NormalizedCard` 内部自动生成
3. `message_number.py` 保留并作为统一编号管理器
4. 接收消息时也可以通过 `NormalizedCard` 添加编号
5. 所有 UT 通过
6. 端到端测试验证 Hook 通知正常

---

## 实施步骤

1. 修改 `NormalizedCard.__init__()` 添加编号生成逻辑
2. 修改 `BaseCard.build()` 移除编号添加
3. 修改 `NotificationCard.build_content()` 移除编号获取
4. 运行 UT 验证
5. 端到端测试
