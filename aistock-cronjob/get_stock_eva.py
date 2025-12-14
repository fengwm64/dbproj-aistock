import requests
import time
import random
from typing import Set
from datetime import datetime

from utils.db import get_db_session
from utils.model import UserStock

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
    print(f"获取到{len(watched_stocks)}支被关注的股票（含国内人气榜前8热门）")
    return watched_stocks

def fetch_stock_eva():
    """获取所有用户关注股票和前8热门股票的评价"""
    watched_stocks = get_all_watched_stocks()
    for stock_code in watched_stocks:
        print(f"正在请求股票 {stock_code} 的评价API...")
        api_url = f"https://api.aistocklink.cn/api/eva?code={stock_code}&refresh=true"
        try:
            response = requests.get(api_url, timeout=200)
            print(f"股票 {stock_code} 返回状态码: {response.status_code}")
            print(f"返回内容: {response.text}")
        except Exception as e:
            print(f"请求股票 {stock_code} 评价API时出错: {e}")
        time.sleep(random.uniform(0.5, 1.5))  # 避免请求过快

if __name__ == "__main__":
    print(f"开始时间: {datetime.now()}")
    fetch_stock_eva()
    print(f"结束时间: {datetime.now()}")
