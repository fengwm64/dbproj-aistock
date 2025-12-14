# utils/db.py

from sqlalchemy import create_engine, exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager
from dotenv import load_dotenv
import os

# 加载环境变量
load_dotenv(override=True)

# --------------------------------------------------------------------
# 数据库连接配置
# --------------------------------------------------------------------
# 从环境变量中获取数据库连接字符串
DATABASE_URI = os.getenv("DATABASE_URI")

# 创建数据库引擎
engine = create_engine(DATABASE_URI)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

# 创建一个全局session对象供直接访问
# 注意: 在生产环境中建议使用get_db_session上下文管理器而非全局session
session = SessionLocal()

@contextmanager
def get_db_session():
    """获取数据库会话的上下文管理器"""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        raise
    finally:
        session.close()
