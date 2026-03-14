"""
卡片编号管理器 - 使用数据库实现线程和进程安全的顺序号跟踪
"""
import datetime
import os
from pathlib import Path

logger = __import__("logging").getLogger(__name__)


class CardIdManager:
    """卡片编号管理器 - 使用数据库实现线程和进程安全的顺序号跟踪"""

    def __init__(self, db=None):
        """初始化卡片编号管理器

        Args:
            db: Database 实例，如果为 None 则使用全局数据库
        """
        self._db = db

    def _get_db(self):
        """获取数据库实例"""
        if self._db is not None:
            return self._db
        # 延迟导入，避免循环依赖
        from src.storage import db as storage_db
        return storage_db

    def get_next_id(self) -> str:
        """获取下一个卡片编号

        Returns:
            卡片编号: XXX（完整数字，不补零）
        """
        try:
            db = self._get_db()
            # _LazyDB 代理需要实际调用来验证数据库是否可用
            # 不能仅用 hasattr 判断，因为 LazyDB 会转发所有属性访问
            try:
                # 尝试调用方法，如果返回 None 说明数据库实际不可用
                result = db.get_next_card_id()
                if result is None:
                    raise Exception("数据库方法返回 None")
                return str(result)
            except (TypeError, AttributeError, Exception) as e:
                # LazyDB 转发调用但实际返回 None 时会抛出 TypeError
                # 或者 result 为 None
                raise Exception(f"数据库不可用: {e}")

        except Exception as e:
            logger.warning(f"卡片编号: {e}，使用时间戳方案")
            # 降级方案: 使用时间戳（完整数字）
            return str(int(datetime.datetime.now().strftime('%H%M%S')))


# 全局卡片编号管理器实例
_card_id_manager: CardIdManager = None


def get_card_id_manager() -> CardIdManager:
    """获取全局卡片编号管理器"""
    global _card_id_manager
    if _card_id_manager is None:
        # 延迟导入，避免循环依赖
        from src.storage import db as storage_db
        _card_id_manager = CardIdManager(db=storage_db)
    return _card_id_manager


