import akshare as ak
import time
import random
import logging
from utils.save import save_hot_stocks

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def log_hot_stocks(hot_stocks_list):
    """使用logger打印热门股票信息"""
    logger.info(f"获取到 {len(hot_stocks_list)} 只热门股票")
    for stock in hot_stocks_list:
        logger.info(f"排名: {stock['rank']} | 代码: {stock['code']} | 类型: {stock['remark']}")

def fetch_hot_stocks():
    try:
        # 爬取国内人气榜数据
        domestic_data = ak.stock_hot_rank_em()
        domestic_stocks = [
            {
                "code": row["代码"][-6:],  # 取后6位作为代码
                "rank": row["当前排名"],
                "remark": "国内人气榜"
            }
            for _, row in domestic_data.iterrows()
        ]

        # 爬取港股人气榜数据
        hk_data = ak.stock_hk_hot_rank_em()
        hk_stocks = [
            {
                "rank": row["当前排名"],
                "code": row["代码"],
                "name": row["股票名称"],
                "remark": "港股人气榜"
            }
            for _, row in hk_data.iterrows()
        ]

        # 保存或更新数据
        all_stocks = domestic_stocks + hk_stocks
        log_hot_stocks(all_stocks)  # 使用logger打印
        
        # 保存到数据库并检查结果
        if save_hot_stocks(all_stocks):
            logger.info("热门股票数据已成功保存到数据库")
        else:
            logger.error("热门股票数据保存失败")
            
    except Exception as e:
        logger.error(f"爬取热门股票数据出错: {e}", exc_info=True)

if __name__ == "__main__":
    fetch_hot_stocks()
