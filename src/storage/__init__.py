"""
数据存储层
"""
import logging
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from src.config.settings import get_settings
from src.models import Message, MessageType, MessageDirection, MessageSource

# 获取日志记录器
logger = logging.getLogger(__name__)


class Database:
    """数据库管理类"""

    def __init__(self, db_path: Path = get_settings().db_path):
        self.db_path = db_path
        self._init_db()

    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 消息表 - 使用 id INTEGER PRIMARY KEY AUTOINCREMENT 实现自增编号
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    direction TEXT,
                    is_test INTEGER DEFAULT 0,
                    message_source TEXT,
                    feishu_message_id TEXT NOT NULL,
                    card_id INTEGER
                )
            """)

            # 检查并添加新列（用于迁移旧数据库）
            cursor.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]

            if "direction" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN direction TEXT")
            if "is_test" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN is_test INTEGER DEFAULT 0")
            if "message_source" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN message_source TEXT")
            if "feishu_message_id" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN feishu_message_id TEXT")
            if "card_id" not in columns:
                cursor.execute("ALTER TABLE messages ADD COLUMN card_id INTEGER")

            # 检查是否需要迁移（旧表使用 seq_id 或 message_number 列）
            cursor.execute("PRAGMA table_info(messages)")
            columns = [row[1] for row in cursor.fetchall()]

            needs_migration = "seq_id" in columns or "message_number" in columns

            if needs_migration:
                logger.info("开始数据库迁移：将 seq_id 重命名为 id")
                # 备份旧表
                cursor.execute("ALTER TABLE messages RENAME TO messages_old")

                # 创建新表（使用 id）
                cursor.execute("""
                    CREATE TABLE messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id TEXT NOT NULL,
                        message_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TIMESTAMP NOT NULL,
                        direction TEXT,
                        is_test INTEGER DEFAULT 0,
                        message_source TEXT,
                        feishu_message_id TEXT NOT NULL,
                        card_id INTEGER
                    )
                """)

                # 复制数据（seq_id → id）
                cursor.execute("""
                    INSERT INTO messages (id, user_id, message_type, content, created_at,
                                          direction, is_test, message_source, feishu_message_id)
                    SELECT seq_id, user_id, message_type, content, created_at,
                           direction, is_test, message_source,
                           COALESCE(feishu_message_id, '') as feishu_message_id
                    FROM messages_old
                """)

                # 删除旧表
                cursor.execute("DROP TABLE messages_old")

                logger.info("数据库迁移完成")

            # 创建索引
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_user_id ON messages(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_direction ON messages(direction)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_source ON messages(message_source)")

            # 卡片编号序列表 - 用于替代文件存储的消息计数器
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS card_id_seq (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    seq_value INTEGER NOT NULL DEFAULT 0
                )
            """)

            # 检查并添加 seq_value 列（如果列不存在）
            cursor.execute("PRAGMA table_info(card_id_seq)")
            columns = [row[1] for row in cursor.fetchall()]
            if "seq_value" not in columns:
                logger.info("添加 seq_value 列到 card_id_seq 表")
                cursor.execute("ALTER TABLE card_id_seq ADD COLUMN seq_value INTEGER NOT NULL DEFAULT 0")

            # 初始化序列值（如果不存在）
            cursor.execute("SELECT seq_value FROM card_id_seq WHERE id = 1")
            if cursor.fetchone() is None:
                cursor.execute("INSERT INTO card_id_seq (id, seq_value) VALUES (1, 0)")

            # 保留旧表（不删除历史数据），但不创建索引
            # tasks 表保留但不再使用

    def save_message(self, message: Message) -> int:
        """保存消息 - 使用 SQLite AUTOINCREMENT 生成消息编号，返回 id"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 如果消息未明确设置 is_test（为 None），使用环境变量判断测试模式
            is_test = message.is_test
            if is_test is None:
                # 只检查环境变量
                is_test = os.getenv("TEST_MODE_ENABLED") == "true"

            # 插入数据，seq_id 会自动生成
            cursor.execute("""
                INSERT INTO messages
                (user_id, message_type, content, created_at,
                 direction, is_test, message_source, feishu_message_id, card_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.user_id,
                message.message_type.value,
                message.content,
                message.created_at.isoformat(),
                message.direction.value if message.direction else None,
                1 if is_test else 0,
                message.message_source.value if message.message_source else None,
                message.feishu_message_id,
                message.card_id
            ))

            return cursor.lastrowid

    def get_user_messages(self, user_id: str, limit: int = 50) -> List[Message]:
        """获取用户的消息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM messages
                WHERE user_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (user_id, limit))
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]

    def _row_to_message(self, row) -> Message:
        """将数据库行转换为 Message 对象"""
        return Message(
            id=row["id"],
            user_id=row["user_id"],
            message_type=MessageType(row["message_type"]),
            content=row["content"],
            created_at=datetime.fromisoformat(row["created_at"]),
            direction=MessageDirection(row["direction"]) if row["direction"] else None,
            is_test=bool(row["is_test"]) if row["is_test"] is not None else False,
            message_source=MessageSource(row["message_source"]) if row["message_source"] else None,
            feishu_message_id=row["feishu_message_id"] if row["feishu_message_id"] else "",
            card_id=row["card_id"] if row["card_id"] else None
        )

    def get_messages_by_direction(
        self,
        direction: MessageDirection,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Message]:
        """根据消息方向获取消息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE direction = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (direction.value, user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE direction = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (direction.value, limit))
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]

    def get_messages_by_source(
        self,
        source: MessageSource,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Message]:
        """根据消息来源获取消息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE message_source = ? AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (source.value, user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE message_source = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (source.value, limit))
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]

    def get_test_messages(self, user_id: Optional[str] = None, limit: int = 50) -> List[Message]:
        """获取测试消息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if user_id:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE is_test = 1 AND user_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM messages
                    WHERE is_test = 1
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [self._row_to_message(row) for row in rows]

    def get_message_statistics(self) -> List[dict]:
        """获取消息统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    direction,
                    message_source,
                    is_test,
                    COUNT(*) as count
                FROM messages
                GROUP BY direction, message_source, is_test
                ORDER BY direction, message_source, is_test
            """)
            rows = cursor.fetchall()
            return [
                {
                    "direction": row["direction"],
                    "message_source": row["message_source"],
                    "is_test": bool(row["is_test"]),
                    "count": row["count"]
                }
                for row in rows
            ]

    def get_next_card_id(self) -> int:
        """获取下一个卡片编号 - 使用数据库事务保证原子性"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # SQLite 使用 BEGIN IMMEDIATE 获取写锁，保证原子性
            cursor.execute("BEGIN IMMEDIATE")
            cursor.execute("SELECT seq_value FROM card_id_seq WHERE id = 1")
            row = cursor.fetchone()
            current_value = row["seq_value"] if row else 0
            new_value = current_value + 1
            cursor.execute("UPDATE card_id_seq SET seq_value = ? WHERE id = 1", (new_value,))
            conn.commit()
            return new_value

# 全局数据库实例 - 延迟初始化
# 在 standalone 模式下（从非项目目录调用），跳过数据库初始化
import os
import sys

def _get_db():
    """延迟获取数据库实例"""
    if not hasattr(_get_db, '_instance'):
        try:
            _get_db._instance = Database()
        except Exception as e:
            # 在 standalone 模式下，数据库可能不存在，跳过初始化
            print(f"Warning: Database initialization skipped: {e}", file=sys.stderr)
            _get_db._instance = None
    return _get_db._instance

class _LazyDB:
    """延迟加载的数据库代理"""
    def __getattr__(self, name):
        db = _get_db()
        if db is None:
            # 返回一个空操作函数
            return lambda *args, **kwargs: None
        return getattr(db, name)

db = _LazyDB()