# Roadmap

## 2026-07-05

- [未识别的 #xxx 命令转为 AI 执行](2026-07-05/feature-unknown-hash-cmd-to-ai.md)
  - 实现 PlatformCommands.handle_command 返回 bool，未识别返回 False
  - CommandExecutor 处理 False，临时切换 larkode 空间执行
  - open_id → union_id 自动转换（FeishuAPI）
  - Union ID 文档和测试
