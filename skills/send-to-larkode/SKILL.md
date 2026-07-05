# Send to Larkode

将文件发送到飞书。

## 重要提醒

用户说"发给我"、"发送xxx"、"把xxx发给我"时，完成文件准备后**必须立即调用此skill**，不要停在中间步骤。

## 触发词

- 发给我、发给
- 把 xxx 发给我
- 发送 xxx、发送给
- 发 APK / 发 IPA
- 发文件

## 流程

1. 识别目标文件（如果需要先构建/打包，先完成构建）
2. 复制到 ~/.larkode/queue/pending/
3. 告知用户"已放入发送队列"

## 目录结构

```
~/.larkode/queue/
├── pending/   # 待发送
└── sent/     # 已发送
```

## 文件命名

同名文件加时间戳： `app.apk` → `app_20260607135500.apk`

## 自动检测

"发送最新的 APP" → 找最新修改时间的 APK/IPA：
- Android: `build/app/outputs/apk/*.apk`, `app/build/outputs/apk/*.apk`
- iOS: `*.ipa`

## 执行

```bash
mkdir -p ~/.larkode/queue/pending ~/.larkode/queue/sent
cp <FILE> ~/.larkode/queue/pending/
```
