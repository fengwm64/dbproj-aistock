import pandas as pd
import json
from datetime import datetime, timedelta
import akshare as ak
import requests
import time
import logging
from utils.save import save_market_indices
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import random
from typing import List, Dict, Optional

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置常量
MAX_RETRIES = 3
TIMEOUT = 10
CONCURRENT_THREADS = 3

def get_market_indices():
    """获取市场指数数据并保存到数据库"""
    try:
        # 获取指数数据
        indices_data = _fetch_all_indices_data()
        
        # 验证数据完整性
        if not indices_data:
            logger.error("没有获取到有效的指数数据")
            return False
            
        # 过滤无效数据
        valid_indices = [idx for idx in indices_data if _validate_index_data(idx)]
        
        if not valid_indices:
            logger.error("所有指数数据都无效")
            return False
        
        # 保存到数据库
        save_market_indices(valid_indices)
        logger.info(f"成功获取并保存 {len(valid_indices)} 个指数的数据")
        return True
        
    except Exception as e:
        logger.error(f"获取和保存指数数据时发生错误: {e}", exc_info=True)
        return False

def _validate_index_data(index_data: dict) -> bool:
    """验证指数数据的有效性"""
    required_fields = ['idx_code', 'name', 'value', 'change_amount', 'change_percent']
    
    # 检查必需字段
    for field in required_fields:
        if field not in index_data or index_data[field] is None:
            logger.warning(f"指数数据缺少必需字段 {field}: {index_data}")
            return False
    
    # 检查数值字段的有效性
    try:
        float(index_data['value'])
        float(index_data['change_amount'])
        float(index_data['change_percent'])
    except (ValueError, TypeError):
        logger.warning(f"指数数据包含无效数值: {index_data}")
        return False
    
    return True

def _fetch_all_indices_data():
    """获取所有指数的实时数据 - 优化版本"""
    result = []
    
    # 1. 获取A股主要指数
    a_share_data = _fetch_a_share_indices()
    if a_share_data:
        result.extend(a_share_data)
    
    # 2. 并发获取海外指数
    overseas_data = _fetch_overseas_indices_concurrent()
    if overseas_data:
        result.extend(overseas_data)
    
    return result

def _fetch_a_share_indices() -> List[Dict]:
    """获取A股指数数据"""
    try:
        # 定义目标指数
        target_indices = {
            "sh000001": "上证指数",
            "sz399001": "深证成指", 
            "sz399006": "创业板指"
        }
        
        # 使用重试机制获取数据
        for attempt in range(MAX_RETRIES):
            try:
                df = ak.stock_zh_index_spot_sina()
                break
            except Exception as e:
                if attempt == MAX_RETRIES - 1:
                    raise e
                logger.warning(f"获取A股指数第{attempt + 1}次尝试失败: {e}")
                time.sleep(2 ** attempt)  # 指数退避
        
        result = []
        for code, name in target_indices.items():
            try:
                # 筛选单条数据
                filtered_df = df[df['代码'] == code]
                if filtered_df.empty:
                    logger.warning(f"未找到指数 {code} 的数据")
                    continue
                    
                row = filtered_df.iloc[0]
                result.append({
                    "idx_code": code,
                    "name": name,
                    "value": float(row['最新价']),
                    "change_amount": float(row['涨跌额']),
                    "change_percent": float(row['涨跌幅']),
                    "updated_at": datetime.now()
                })
            except Exception as e:
                logger.error(f"处理A股指数 {code} 数据失败: {e}")
                continue
        
        logger.info(f"成功获取 {len(result)} 个A股指数数据")
        return result
        
    except Exception as e:
        logger.error(f"获取A股指数数据失败: {e}")
        return []

def _fetch_overseas_indices_concurrent() -> List[Dict]:
    """并发获取海外指数数据"""
    overseas_indices = ['nasdaq_china', 'ftse_china_a50', 'hangseng_tech']
    result = []
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_THREADS) as executor:
        # 提交任务
        future_to_index = {
            executor.submit(_fetch_single_overseas_index, index_key): index_key 
            for index_key in overseas_indices
        }
        
        # 处理结果
        for future in as_completed(future_to_index):
            index_key = future_to_index[future]
            try:
                index_data = future.result()
                if index_data:
                    result.append(index_data)
            except Exception as e:
                logger.error(f"获取海外指数 {index_key} 失败: {e}")
    
    return result

def _fetch_single_overseas_index(index_key: str) -> Optional[Dict]:
    """获取单个海外指数数据"""
    try:
        index_data = get_index_data(index_key)
        if not index_data:
            return None
        
        # 解析数据
        current_value = _parse_number(index_data['current'])
        change_amount = _parse_number(index_data['change_amount'])
        change_percent = _parse_number(index_data['change_percent'].replace('%', ''))
        
        # 验证数据有效性
        if any(x is None for x in [current_value, change_amount, change_percent]):
            logger.warning(f"指数 {index_key} 数据解析失败")
            return None
        
        result = {
            "idx_code": f"{index_data['code']}",
            "name": index_data['name'],
            "value": current_value,
            "change_amount": change_amount,
            "change_percent": change_percent,
            "updated_at": datetime.now()
        }
        
        logger.info(f"成功获取 {index_data['name']} 数据")
        return result
        
    except Exception as e:
        logger.error(f"获取海外指数 {index_key} 失败: {e}")
        return None

def _parse_number(value_str: str) -> Optional[float]:
    """解析数值字符串"""
    try:
        if not value_str:
            return None
        cleaned = str(value_str).replace(',', '').replace('%', '').strip()
        return float(cleaned) if cleaned else None
    except (ValueError, TypeError):
        return None

# 指数配置信息
INDEX_CONFIG = {
    'nasdaq_china': {
        'secid': '251.HXC',
        'name': '纳斯达克中国金龙指数',
        'scale_factors': {
            'f43': 0.01,   # 当前值
            'f170': 0.01,  # 涨跌额
            'f169': 0.01   # 涨跌幅百分比
        }
    },
    'ftse_china_a50': {
        'secid': '100.XIN9',
        'name': '富时中国A50指数',
        'scale_factors': {
            'f43': 0.01,   # 当前值
            'f170': 0.01,  # 涨跌幅百分比
            'f169': 0.01   # 涨跌额
        }
    },
    'hangseng_tech': {
        'secid': '124.HSTECH',
        'name': '恒生科技指数',
        'scale_factors': {
            'f43': 0.01,   # 当前值
            'f170': 0.01,  # 涨跌幅百分比
            'f169': 0.01   # 涨跌额
        }
    }
}

def get_index_data(index_key):
    """通用函数，根据指数键获取对应指数数据 - 优化版本"""
    config = INDEX_CONFIG.get(index_key)
    if not config:
        logger.error(f"未知的指数类型: {index_key}")
        return None
    
    url = "https://push2.eastmoney.com/api/qt/stock/get"
    
    # 请求参数
    params = {
        "invt": 2,
        "fltt": 1,
        "fields": "f43,f46,f44,f58,f57,f292,f169,f170,f86",
        "secid": config['secid'],
        "ut": "fa5fd1943c7b386f172d6893dbfba10b",
        "wbp2u": "%7C0%7C0%7C0%7Cweb",
        "dect": 1,
        "_": int(time.time() * 1000)
    }
    
    # 请求头
    headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
        "Referer": f"https://quote.eastmoney.com/bk/{config['secid']}.html",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36 Edg/136.0.0.0",
        "sec-ch-ua": '"Chromium";v="136", "Microsoft Edge";v="136", "Not.A/Brand";v="99"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }
    
    # 重试机制
    for attempt in range(MAX_RETRIES):
        try:
            # 添加随机延迟避免请求过于频繁
            if attempt > 0:
                time.sleep(random.uniform(1, 3))
            
            response = requests.get(url, params=params, headers=headers, timeout=TIMEOUT)
            response.raise_for_status()
            
            json_data = response.json()
            
            if json_data.get('data'):
                data = json_data['data']
                
                # 验证关键字段
                if not data.get('f43') or not data.get('f169') or not data.get('f170'):
                    logger.warning(f"{config['name']} 返回数据不完整")
                    continue
                
                # 缩放并格式化数据
                result = {
                    'name': data.get('f58', config['name']),
                    'code': data.get('f57', config['secid'].split('.')[1]),
                    'current': format_number(data.get('f43') * config['scale_factors']['f43'], 2),
                    'change_amount': format_number(data.get('f169') * config['scale_factors']['f169'], 2),
                    'change_percent': f"{format_number(data.get('f170') * config['scale_factors']['f170'], 2)}%",
                    'update_time': get_actual_update_time(data)
                }
                
                return result
            else:
                logger.warning(f"{config['name']} API返回数据为空")
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"请求 {config['name']} 第{attempt + 1}次失败: {e}")
            if attempt == MAX_RETRIES - 1:
                logger.error(f"获取 {config['name']} 数据最终失败")
        except Exception as e:
            logger.error(f"获取 {config['name']} 数据异常: {e}")
            break
    
    return None

def format_number(value, decimal_places=2):
    """格式化数值，添加千位分隔符并保留指定小数位数"""
    if value is None:
        return "N/A"
    try:
        return f"{float(value):,.{decimal_places}f}"
    except (ValueError, TypeError):
        return value

def get_actual_update_time(data):
    """尝试从API响应中获取真实的更新时间"""
    # 检查可能包含时间的字段
    possible_time_fields = ['f86', 'f20', 'f21']
    
    for field in possible_time_fields:
        if field in data and data[field]:
            time_str = str(data[field])
            if len(time_str) == 14:  # 格式如: 20250511153000
                try:
                    return datetime.strptime(time_str, '%Y%m%d%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                except ValueError:
                    continue
    
    # 如果没有找到，使用当前时间
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

if __name__ == "__main__":
    # 执行获取指数数据并保存
    start_time = time.time()
    success = get_market_indices()
    end_time = time.time()
    
    if success:
        logger.info(f"指数数据更新完成，耗时: {end_time - start_time:.2f}秒")
    else:
        logger.error(f"指数数据更新失败，耗时: {end_time - start_time:.2f}秒")
