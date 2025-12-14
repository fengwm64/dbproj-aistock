import redis
import logging
import os
from flask import current_app as app
import pickle
from functools import wraps

logger = logging.getLogger(__name__)

def get_redis_connection():
    """
    获取Redis连接，如果失败则返回None
    """
    try:
        # 从环境变量或配置获取Redis连接URL
        redis_url = app.config.get("REDIS_BROKER_URL") or os.getenv("REDIS_BROKER_URL")
        if not redis_url:
            logger.error("Redis连接配置缺失")
            return None
            
        # 创建Redis连接并测试
        redis_conn = redis.Redis.from_url(redis_url)
        redis_conn.ping()  # 测试连接是否正常
        return redis_conn
    except redis.ConnectionError as e:
        logger.error(f"无法连接到Redis: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Redis连接异常: {str(e)}")
        return None

def cache_data(key, data, expire_seconds=3600):
    """
    将数据缓存到Redis
    
    Args:
        key: Redis键
        data: 要缓存的数据(将被pickle序列化)
        expire_seconds: 过期时间(秒)
        
    Returns:
        bool: 缓存是否成功
    """
    try:
        redis_conn = get_redis_connection()
        if not redis_conn:
            logger.warning("Redis连接失败，无法缓存数据")
            return False
            
        # 使用pickle序列化数据(支持任意Python对象)
        pickled_data = pickle.dumps(data)
        redis_conn.setex(key, expire_seconds, pickled_data)
        
        # 新增：验证缓存是否成功写入
        verify_data = redis_conn.get(key)
        if not verify_data:
            logger.warning(f"数据缓存看似成功但立即检索失败: {key}")
            return False
        
        logger.debug(f"数据成功缓存到Redis: {key}, 过期时间{expire_seconds}秒, 数据大小约{len(pickled_data)/1024:.2f}KB")
        return True
    except Exception as e:
        logger.error(f"缓存数据失败: {str(e)}")
        return False

def get_cached_data(key):
    """
    从Redis获取缓存的数据
    
    Args:
        key: Redis键
        
    Returns:
        data: 缓存的数据，如果没有找到或出错则返回None
    """
    try:
        redis_conn = get_redis_connection()
        if not redis_conn:
            logger.warning("Redis连接失败，无法获取缓存数据")
            return None
            
        cached_data = redis_conn.get(key)
        if cached_data:
            try:
                # 反序列化
                data = pickle.loads(cached_data)
                logger.debug(f"缓存命中: {key}, 数据大小约{len(cached_data)/1024:.2f}KB")
                return data
            except Exception as unpickle_error:
                logger.error(f"反序列化缓存数据失败: {str(unpickle_error)}")
                # 数据可能已损坏，删除它
                redis_conn.delete(key)
                return None
        else:
            logger.debug(f"缓存未命中: {key}")
            return None
    except Exception as e:
        logger.error(f"获取缓存数据失败: {str(e)}")
        return None

def clear_cache_pattern(pattern):
    """
    清除匹配指定模式的所有缓存
    
    Args:
        pattern: 键模式，例如"stock:*"
        
    Returns:
        int: 删除的键数量
    """
    try:
        redis_conn = get_redis_connection()
        if not redis_conn:
            return 0
            
        # 获取匹配的键
        keys = redis_conn.keys(pattern)
        if not keys:
            return 0
            
        # 删除这些键
        deleted = redis_conn.delete(*keys)
        logger.info(f"已清除{deleted}个匹配'{pattern}'的缓存键")
        return deleted
    except Exception as e:
        logger.error(f"清除缓存模式'{pattern}'失败: {str(e)}")
        return 0

def redis_cache(prefix, expire_seconds=3600):
    """
    Redis缓存装饰器
    
    Args:
        prefix: 缓存键前缀
        expire_seconds: 缓存过期时间(秒)
    
    Returns:
        装饰器函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            key_parts = [prefix]
            
            # 添加位置参数
            for arg in args:
                if isinstance(arg, (str, int, float, bool)):
                    key_parts.append(str(arg))
                else:
                    # 复杂对象使用其ID或哈希
                    key_parts.append(str(id(arg)))
                    
            # 添加关键字参数(按字母排序确保一致性)
            for k in sorted(kwargs.keys()):
                v = kwargs[k]
                if isinstance(v, (str, int, float, bool)):
                    key_parts.append(f"{k}={v}")
                else:
                    # 复杂对象使用其ID或哈希
                    key_parts.append(f"{k}={id(v)}")
                
            cache_key = ":".join(key_parts)
            
            # 尝试从缓存获取
            logger.debug(f"检查缓存: {cache_key}")
            cached_result = get_cached_data(cache_key)
            if cached_result is not None:
                return cached_result
                
            # 缓存未命中，调用原始函数
            logger.debug(f"缓存未命中，执行原始函数: {cache_key}")
            result = func(*args, **kwargs)
            
            # 缓存结果
            if result is not None:  # 只缓存非None结果
                success = cache_data(cache_key, result, expire_seconds)
                if success:
                    logger.debug(f"结果已缓存: {cache_key}, 过期时间: {expire_seconds}秒")
                else:
                    logger.warning(f"结果缓存失败: {cache_key}")
                
            return result
        return wrapper
    return decorator

def save_scan_login_state(scan_id, state_data, expire_seconds=300):
    """
    保存扫码登录状态到Redis
    
    Args:
        scan_id: 扫码ID，作为Redis键的一部分
        state_data: 状态数据
        expire_seconds: 过期时间(秒)，默认5分钟
        
    Returns:
        bool: 操作是否成功
    """
    try:
        key = f"scan_login:{scan_id}"
        return cache_data(key, state_data, expire_seconds)
    except Exception as e:
        logger.error(f"保存扫码登录状态失败: {str(e)}")
        return False

def get_scan_login_state(scan_id):
    """
    获取扫码登录状态
    
    Args:
        scan_id: 扫码ID
        
    Returns:
        dict: 状态数据，如果不存在则返回None
    """
    try:
        key = f"scan_login:{scan_id}"
        return get_cached_data(key)
    except Exception as e:
        logger.error(f"获取扫码登录状态失败: {str(e)}")
        return None

def update_scan_login_state(scan_id, state_data, expire_seconds=300):
    """
    更新扫码登录状态
    
    Args:
        scan_id: 扫码ID
        state_data: 新的状态数据
        expire_seconds: 新的过期时间(秒)
        
    Returns:
        bool: 操作是否成功
    """
    return save_scan_login_state(scan_id, state_data, expire_seconds)

def delete_scan_login_state(scan_id):
    """
    删除扫码登录状态
    
    Args:
        scan_id: 扫码ID
        
    Returns:
        bool: 操作是否成功
    """
    try:
        redis_conn = get_redis_connection()
        if not redis_conn:
            return False
            
        key = f"scan_login:{scan_id}"
        deleted = redis_conn.delete(key)
        return deleted > 0
    except Exception as e:
        logger.error(f"删除扫码登录状态失败: {str(e)}")
        return False

def list_all_scan_states():
    """
    列出所有当前有效的扫码登录状态
    
    Returns:
        dict: 扫码ID到状态数据的映射
    """
    try:
        redis_conn = get_redis_connection()
        if not redis_conn:
            return {}
            
        pattern = "scan_login:*"
        keys = redis_conn.keys(pattern)
        
        result = {}
        for key in keys:
            scan_id = key.decode('utf-8').split(':', 1)[1]
            state = get_scan_login_state(scan_id)
            if state:
                result[scan_id] = state
                
        return result
    except Exception as e:
        logger.error(f"列出扫码登录状态失败: {str(e)}")
        return {}