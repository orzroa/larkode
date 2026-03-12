"""
卡片编号管理器单元测试
"""
import pytest
import os
import tempfile
import shutil
from pathlib import Path

# 添加项目根目录到路径
import sys
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.card_id import CardIdManager, get_card_id_manager


class MockDatabase:
    """模拟数据库，用于测试"""

    def __init__(self):
        self.seq_value = 0
        self.calls = []

    def get_next_card_id(self):
        """模拟数据库的 get_next_card_id 方法"""
        self.calls.append('get_next_card_id')
        self.seq_value += 1
        return self.seq_value


class TestCardIdManager:
    """测试卡片编号管理器"""

    def setup_method(self):
        """设置测试环境"""
        self.mock_db = MockDatabase()
        self.manager = CardIdManager(db=self.mock_db)

    def test_get_next_id_first(self):
        """测试获取第一个编号"""
        card_id = self.manager.get_next_id()
        assert card_id is not None
        # 验证是纯数字
        assert card_id.isdigit()
        assert int(card_id) > 0

    def test_get_next_id_increments(self):
        """测试编号递增"""
        ids = [self.manager.get_next_id() for _ in range(5)]

        # 验证是纯数字
        num_parts = [int(n) for n in ids]

        # 验证递增
        for i in range(1, len(num_parts)):
            assert num_parts[i] == num_parts[i - 1] + 1

    def test_uses_mock_database(self):
        """测试使用模拟数据库"""
        self.manager.get_next_id()
        self.manager.get_next_id()
        # 验证调用了数据库方法
        assert 'get_next_card_id' in self.mock_db.calls
        assert len(self.mock_db.calls) == 2

    def test_id_format(self):
        """测试编号格式"""
        card_id = self.manager.get_next_id()
        # 验证是纯数字
        assert card_id.isdigit()
        # 验证是正整数
        assert int(card_id) > 0

    def test_multiple_managers_share_database(self):
        """测试多个管理器共享同一个数据库"""
        manager1 = CardIdManager(db=self.mock_db)
        manager2 = CardIdManager(db=self.mock_db)

        id1 = manager1.get_next_id()
        id2 = manager2.get_next_id()

        # 两个实例应该使用同一个计数器
        id1_int = int(id1)
        id2_int = int(id2)
        assert id2_int == id1_int + 1


class TestCardIdManagerWithNoneDB:
    """测试卡片编号管理器在没有数据库时的降级行为"""

    def test_fallback_to_timestamp(self):
        """测试降级到时间戳"""
        manager = CardIdManager(db=None)
        # 由于 db=None 且没有全局数据库，会降级到时间戳
        card_id = manager.get_next_id()
        # 验证是纯数字
        assert card_id.isdigit()
        # 时间戳应该小于 240000（24小时内的秒数）
        assert int(card_id) < 240000


class TestGetCardIdManager:
    """测试全局卡片编号管理器获取函数"""

    def test_get_card_id_manager_returns_manager(self):
        """测试获取全局管理器"""
        manager = get_card_id_manager()
        assert manager is not None
        assert isinstance(manager, CardIdManager)
