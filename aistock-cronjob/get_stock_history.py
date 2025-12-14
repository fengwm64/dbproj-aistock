import akshare as ak
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import func
from utils.db import SessionLocal
from utils.model import HotStock, UserStock, StockHistory, Stocks

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fetch_and_save_stock_history():
    session = SessionLocal()
    try:
        # 获取当前日期和3年前的日期
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=3*365)).strftime('%Y%m%d')

        # 获取 HotStock 和 UserStock 表中的股票代码
        hot_stock_codes = session.query(HotStock.code).filter(func.length(HotStock.code) == 6).all()
        user_stock_codes = session.query(UserStock.code).filter(func.length(UserStock.code) == 6).all()
        existing_codes = session.query(StockHistory.code).filter(func.length(StockHistory.code) == 6).all()

        # 从 Stocks 表中随机挑选 50 个 6 位股票代码
        random_stock_codes = session.query(Stocks.code).filter(func.length(Stocks.code) == 6).order_by(func.rand()).limit(50).all()

        # 合并并去重股票代码
        all_codes = {code for code, in hot_stock_codes + user_stock_codes + existing_codes + random_stock_codes if len(code) == 6}

        logger.info(f"开始处理 {len(all_codes)} 只股票的历史数据")

        for code in all_codes:
            try:
                # 检查最近更新时间是否超过 24 小时
                latest_update = session.query(StockHistory.updated_at).filter(StockHistory.code == code).order_by(StockHistory.updated_at.desc()).first()
                if latest_update and (datetime.now() - latest_update[0]).total_seconds() < 86400:
                    logger.info(f"跳过 {code}，最近更新时间在 24 小时内")
                    continue

                # 调用 akshare 接口获取后复权数据
                stock_data = ak.stock_zh_a_hist(symbol=code, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
                for _, row in stock_data.iterrows():
                    # 检查是否已存在记录
                    existing_record = session.query(StockHistory).filter_by(code=code, date=row['日期']).first()
                    if existing_record:
                        # 更新已有记录
                        existing_record.open_price = row['开盘']
                        existing_record.close_price = row['收盘']
                        existing_record.high = row['最高']
                        existing_record.low = row['最低']
                        existing_record.volume = row['成交量']
                        existing_record.turnover = row['成交额']
                        existing_record.amplitude = row['振幅']
                        existing_record.change_percent = row['涨跌幅']
                        existing_record.change_amount = row['涨跌额']
                        existing_record.turnover_rate = row['换手率']
                        existing_record.updated_at = datetime.now()
                    else:
                        # 插入新记录
                        history = StockHistory(
                            code=code,
                            date=row['日期'],
                            open_price=row['开盘'],
                            close_price=row['收盘'],
                            high=row['最高'],
                            low=row['最低'],
                            volume=row['成交量'],
                            turnover=row['成交额'],
                            amplitude=row['振幅'],
                            change_percent=row['涨跌幅'],
                            change_amount=row['涨跌额'],
                            turnover_rate=row['换手率'],
                            updated_at=datetime.now()
                        )
                        session.add(history)
                session.commit()
                logger.info(f"成功保存或更新 {code} 的历史数据")
            except Exception as e:
                session.rollback()
                logger.error(f"获取或保存 {code} 的历史数据失败: {e}", exc_info=True)
    finally:
        session.close()

if __name__ == "__main__":
    fetch_and_save_stock_history()
