import requests
import time
import random
from typing import Set, Dict, List, Tuple
from datetime import datetime
import re
import logging
import akshare as ak
import numpy as np
import hashlib
import pandas as pd
from functools import lru_cache
from model2vec import StaticModel
from semhash import SemHash

from utils.db import get_db_session
from utils.model import UserStock, Stocks, News
import utils.db as db
from utils.save import save_news

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("stock_page_cache")

# 自定义User-Agent用于识别缓存机器人访问
CACHE_BOT_USER_AGENT = "AIStockCacheBot/1.0 (Stock Detail Page Cache; +https://aistocklink.cn/bot) Mozilla/5.0 (Linux; Cache Bot) AppleWebKit/537.36"

def get_all_watched_stocks() -> Set[str]:
    """获取所有用户关注的股票代码集合，并加入前8热门股票（国内人气榜）"""
    watched_stocks = set()
    
    with get_db_session() as session:
        # 查询所有用户关注的股票
        stocks = session.query(UserStock.code).distinct().all()
        for stock in stocks:
            watched_stocks.add(stock.code)
        # 查询前8个热门股票（remark=国内人气榜）
        from utils.model import HotStock
        hot_stocks = session.query(HotStock.code).filter(HotStock.remark == '国内人气榜').order_by(HotStock.rank.asc()).limit(8).all()
        for hot in hot_stocks:
            watched_stocks.add(hot.code)
    
    print(f"获取到{len(watched_stocks)}支被关注的股票（含国内人气榜热门）")
    return watched_stocks


def fetch_stock_news():
    """访问所有用户关注股票的API接口进行缓存"""
    # 获取所有被关注的股票代码
    watched_stocks = get_all_watched_stocks()
    
    success_count = 0
    fail_count = 0
    
    # API接口模板
    api_urls = [
        "https://api.aistocklink.cn/api/news/get?code={code}&page=1&limit=5",
        "https://api.aistocklink.cn/api/stocks/detail?code={code}",
        "https://api.aistocklink.cn/api/stocks/history?code={code}&years=1"
    ]
    
    # 请求头
    headers = {
        'User-Agent': CACHE_BOT_USER_AGENT,
        'Accept': 'application/json',
        'Content-Type': 'application/json'
    }
    
    # 循环遍历每个股票代码
    for stock_code in watched_stocks:
        stock_success = 0
        stock_fail = 0
        
        # 访问每个API接口
        for api_template in api_urls:
            try:
                url = api_template.format(code=stock_code)
                logger.info(f"正在访问股票 {stock_code} 的API: {url}")
                
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"成功访问股票 {stock_code} API，状态码: {response.status_code}")
                    stock_success += 1
                else:
                    logger.warning(f"访问股票 {stock_code} API失败，状态码: {response.status_code}")
                    stock_fail += 1
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"访问股票 {stock_code} API时发生错误: {str(e)}")
                stock_fail += 1
            except Exception as e:
                logger.error(f"处理股票 {stock_code} API时发生未知错误: {str(e)}")
                stock_fail += 1
                
            # API之间的小延时
            time.sleep(0.2)
        
        # 统计该股票的结果
        if stock_success == len(api_urls):
            success_count += 1
        else:
            fail_count += 1
            
        logger.info(f"股票 {stock_code} 完成: 成功 {stock_success}/{len(api_urls)} 个API")
        
        # 添加延时，避免请求过于频繁
        time.sleep(random.uniform(1, 2))

    print(f"股票API请求完成：成功 {success_count} 个股票，失败 {fail_count} 个股票")
    return success_count, fail_count


if __name__ == "__main__":
    success_count, fail_count = fetch_stock_news()
    print(f"总共成功缓存 {success_count} 个股票详细页面，失败 {fail_count} 个")