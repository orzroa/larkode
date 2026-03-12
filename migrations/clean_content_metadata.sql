-- 数据迁移脚本：清理 messages 表 content 字段中的元数据
-- 执行此脚本后，content 字段将只存储纯内容，不包含卡片编号和时间戳
--
-- 使用方法：
--   sqlite3 data/larkode.db < migrations/clean_content_metadata.sql
--
-- 备份建议：
--   在执行前请先备份数据库：cp data/larkode.db data/larkode.db.backup

-- 第一步：备份数据（创建备份表）
CREATE TABLE IF NOT EXISTS messages_backup AS
SELECT * FROM messages;

-- 第二步：清理 content 字段中的元数据
-- 元数据格式：📨 **卡片编号**: 4455\n🕒 `2026-03-11 22:46:31`\n
-- 我们需要移除前两行，只保留纯内容

-- SQLite 不直接支持正则替换，使用以下逻辑：
-- 找到第一个换行后的第二个换行位置，然后从该位置开始截取

-- 方法：使用 substr 和 instr 组合
-- 1. 找到第一个换行符
-- 2. 从第一个换行符后找第二个换行符
-- 3. 从第二个换行符后开始截取

UPDATE messages
SET content = CASE
    -- 如果 content 以 📨 **卡片编号**: 开头
    WHEN content LIKE '📨 **卡片编号**:%' THEN
        substr(
            content,
            -- 找到第一个换行符的位置
            instr(content, char(10)) + 1,
            -- 从第一个换行符后开始找第二个换行符
            instr(substr(content, instr(content, char(10)) + 1), char(10)) + 1
        )
    -- 如果 content 以 📨 **消息编号**: 开头（旧格式）
    WHEN content LIKE '📨 **消息编号**:%' THEN
        substr(
            content,
            instr(content, char(10)) + 1,
            instr(substr(content, instr(content, char(10)) + 1), char(10)) + 1
        )
    -- 否则保持不变
    ELSE content
END
WHERE content LIKE '📨 **卡片编号**:%' OR content LIKE '📨 **消息编号**:%';

-- 第三步：验证迁移结果
-- 运行以下查询验证：
-- SELECT id, card_id, substr(content, 1, 50) as content_preview FROM messages WHERE content LIKE '%📨%' LIMIT 10;
--
-- 如果结果仍然包含 📨，说明迁移可能失败，请检查并手动修复。

-- 第四步：更新 card_id 字段（如果之前未设置）
-- 从 content 中提取卡片编号并更新到 card_id 字段
-- 注意：这个步骤比较复杂，需要根据实际情况处理

-- 五、迁移完成提示
SELECT '迁移完成！' as status;
SELECT '备份数据保存在 messages_backup 表中' as backup_info;
SELECT '可以运行 DROP TABLE messages_backup; 来删除备份表' as cleanup_hint;