"""
推送配置相关的辅助函数
"""
from db.models import UserPushConfig, SessionLocal
from sqlalchemy.exc import SQLAlchemyError

# 定义标准的推送类型常量，方便代码中统一引用
PUSH_TYPE_STOCK = 'stock_push'       # 自选股推送
PUSH_TYPE_MORNING = 'morning_report' # 早报推送

def get_user_push_config(user_id, push_type):
    """
    获取用户特定推送类型的配置
    
    参数:
    - user_id: 用户ID
    - push_type: 推送类型，如'stock_push'、'morning_report'
    
    返回:
    - 布尔值，表示该推送类型是否启用，默认为False
    """
    session = SessionLocal()
    try:
        config = session.query(UserPushConfig).filter(
            UserPushConfig.user_id == user_id,
            UserPushConfig.push_type == push_type
        ).first()
        
        # 如果没有配置记录，默认为不启用
        if not config:
            return False
            
        return config.enabled
    except SQLAlchemyError as e:
        print(f"获取用户推送配置出错: {e}")
        # 出错时默认为不启用
        return False
    finally:
        session.close()

def set_user_push_config(user_id, push_type, enabled):
    """
    设置用户特定推送类型的配置
    
    参数:
    - user_id: 用户ID
    - push_type: 推送类型，如'stock_push'、'morning_report'
    - enabled: 布尔值，是否启用该推送
    
    返回:
    - 布尔值，表示操作是否成功
    """
    session = SessionLocal()
    try:
        # 尝试查找已有配置
        config = session.query(UserPushConfig).filter(
            UserPushConfig.user_id == user_id,
            UserPushConfig.push_type == push_type
        ).first()
        
        if config:
            # 更新已有配置
            config.enabled = enabled
        else:
            # 创建新配置
            config = UserPushConfig(
                user_id=user_id,
                push_type=push_type,
                enabled=enabled
            )
            session.add(config)
            
        session.commit()
        return True
    except SQLAlchemyError as e:
        session.rollback()
        print(f"设置用户推送配置出错: {e}")
        return False
    finally:
        session.close()

def should_push_to_user(user_id, push_type):
    """
    判断是否应该向用户发送特定类型的推送
    
    参数:
    - user_id: 用户ID
    - push_type: 推送类型
    
    返回:
    - 布尔值，表示是否应该推送
    """
    return get_user_push_config(user_id, push_type)
