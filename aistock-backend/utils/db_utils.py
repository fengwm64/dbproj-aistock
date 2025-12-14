from flask import current_app as app
from sqlalchemy import inspect
from sqlalchemy.exc import ProgrammingError, OperationalError
from db.models import db

def initialize_database():
    """
    初始化数据库，创建所有表
    
    Returns:
        bool: 初始化是否成功
    """
    try:
        app.logger.info("开始初始化数据库表...")
        db.create_all()
        app.logger.info("数据库表初始化成功")
        return True
    except Exception as e:
        app.logger.error(f"数据库表初始化失败: {str(e)}")
        return False
        
def check_table_exists(model_class):
    """
    检查指定模型对应的表是否存在
    
    Args:
        model_class: SQLAlchemy模型类
        
    Returns:
        bool: 表是否存在
    """
    try:
        inspector = inspect(db.engine)
        table_name = model_class.__tablename__
        exists = inspector.has_table(table_name)
        if exists:
            app.logger.debug(f"数据库表 '{table_name}' 已存在")
        else:
            app.logger.warning(f"数据库表 '{table_name}' 不存在")
        return exists
    except Exception as e:
        app.logger.error(f"检查表 '{model_class.__tablename__}' 是否存在时出错: {str(e)}")
        return False
        
def ensure_tables_exist():
    """
    确保所有必要的数据库表存在，如不存在则创建
    
    Returns:
        bool: 所有表是否都存在或成功创建
    """
    try:
        # 获取元数据中声明的所有表模型
        tables_missing = False
        for table in db.metadata.tables.values():
            if not inspect(db.engine).has_table(table.name):
                app.logger.warning(f"数据库表 '{table.name}' 不存在")
                tables_missing = True
                break
        
        # 如果有表缺失，尝试创建所有表
        if tables_missing:
            app.logger.info("检测到缺少表，尝试创建所有表...")
            db.create_all()
            app.logger.info("数据库表创建成功")
        else:
            app.logger.info("所有数据库表已存在")
        
        return True
    except Exception as e:
        app.logger.error(f"确保表存在时出错: {str(e)}")
        return False
