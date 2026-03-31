"""
Claw Memory 测试套件
"""
import pytest
import warnings
import sys
import os

# 添加项目路径到sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

warnings.filterwarnings("ignore")


@pytest.fixture(scope="session")
def db():
    """提供数据库连接"""
    from memory_main import get_db
    return get_db()


@pytest.fixture(scope="function")
def clean_db(db):
    """每个测试前清理数据库（可选）"""
    # 注意：这里不清空，因为会影响测试速度
    yield db
