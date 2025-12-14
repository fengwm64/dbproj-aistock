import akshare as ak
import time
import random
import logging
from utils.model import Stocks
from utils.save import initialize_database
from utils.db import SessionLocal
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from datetime import datetime

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_stock_info(symbol, retries=3):
    """通过接口获取单个股票的详细信息，支持重试"""
    symbol = symbol[-6:]  # 确保只使用后6位作为股票代码
    for attempt in range(retries):
        try:
            # 获取股票信息
            stock_info = ak.stock_individual_info_em(symbol=symbol)
            # 成功获取数据后，将数据转换为字典格式
            result = {
                row["item"]: row["value"]  # 提取每一行的"item"作为键，"value"作为值
                for _, row in stock_info.iterrows()
            }

            return result
        except Exception as e:
            logger.warning(f"获取股票 {symbol} 信息失败 (尝试 {attempt + 1}/{retries}): {e}")
            if attempt < retries - 1:
                # 统一休眠时间为1-3秒
                sleep_time = random.randint(1, 3)
                logger.info(f"随机暂停 {sleep_time} 秒后重试...")
                time.sleep(sleep_time)
    return None

def cache_all_stocks():
    session = SessionLocal()
    cached_stocks = []
    try:
        all_stocks = session.query(Stocks).filter(
            Stocks.code.notin_(["cn", "hk_us", "top"]),
            func.length(Stocks.code) == 6,
            Stocks.code.regexp_match('^[0-9]{6}$')
        ).all()
        
        logger.info(f"开始缓存 {len(all_stocks)} 只股票信息")
        
        for stock in all_stocks:
            stock_info = fetch_stock_info(stock.code)
            if stock_info:
                formatted_stock_info = {
                    "code": stock_info.get("股票代码"),
                    "latest_price": stock_info.get("最新"),
                    "name": stock_info.get("股票简称"),
                    "total_shares": stock_info.get("总股本"),
                    "circulating_shares": stock_info.get("流通股"),
                    "total_market_value": stock_info.get("总市值"),
                    "circulating_market_value": stock_info.get("流通市值"),
                    "industry": stock_info.get("行业"),
                    "listing_date": stock_info.get("上市时间")
                }
                cached_stocks.append(formatted_stock_info)
                logger.info(f"成功缓存股票: {formatted_stock_info['code']} | {formatted_stock_info['name']} | {formatted_stock_info['industry']}")
        
        from utils.save import save_stock_info_batch
        save_stock_info_batch(cached_stocks)
        logger.info(f"股票信息缓存完成，共缓存 {len(cached_stocks)} 只股票")
        
    except SQLAlchemyError as e:
        logger.error(f"数据库操作失败: {e}", exc_info=True)
    finally:
        session.close()


if __name__ == "__main__":
    initialize_database()
    logger.info("开始缓存所有股票信息...")
    cache_all_stocks()