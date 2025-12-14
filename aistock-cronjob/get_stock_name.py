import akshare as ak
import logging
from pypinyin import lazy_pinyin, Style
from sqlalchemy.exc import SQLAlchemyError
from utils.db import SessionLocal
from utils.model import Stocks, StockPinyin
from utils.save import initialize_database

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_pinyin(name):
    """
    生成股票名称的拼音首字母和完整拼音
    """
    # 提取首字母
    pinyin_initials = ''.join(lazy_pinyin(name, style=Style.FIRST_LETTER)).upper()
    
    # 生成完整拼音
    full_pinyin = ''.join(lazy_pinyin(name, style=Style.NORMAL))
    
    return pinyin_initials, full_pinyin

def fetch_and_save_stock_names():
    """
    从 akshare 拉取 A 股代码和名称，然后保存或更新到数据库。
    同时为 len(code)=6 的股票生成拼音信息。
    """
    # 1. 拉取数据
    try:
        df = ak.stock_info_a_code_name()
    except Exception as e:
        logger.error(f"获取股票名单失败: {e}", exc_info=True)
        return

    # 转为字典列表
    records = df.to_dict(orient='records')

    # 2. 保存到数据库
    session = SessionLocal()
    try:
        updated_stocks = 0
        updated_pinyin = 0
        
        for rec in records:
            code = rec.get('code')
            name = rec.get('name')
            if not code or not name:
                continue

            # 去除股票名称中的所有空格
            name = name.replace(' ', '')
            
            # 查询已有记录
            existing = session.query(Stocks).filter(Stocks.code == code).first()
            if existing:
                # 更新名称
                existing.name = name
            else:
                # 插入新记录
                new_stock = Stocks(code=code, name=name)
                session.add(new_stock)
            
            updated_stocks += 1
            
            # 只为 len(code)=6 的股票处理拼音
            if len(code) == 6:
                try:
                    # 生成拼音
                    pinyin_initials, full_pinyin = generate_pinyin(name)
                    
                    # 查询已有的拼音记录
                    existing_pinyin = session.query(StockPinyin).filter(StockPinyin.code == code).first()
                    if existing_pinyin:
                        # 更新拼音
                        existing_pinyin.pinyin = pinyin_initials
                        existing_pinyin.full_pinyin = full_pinyin
                    else:
                        # 插入新的拼音记录
                        new_pinyin = StockPinyin(
                            code=code,
                            pinyin=pinyin_initials,
                            full_pinyin=full_pinyin
                        )
                        session.add(new_pinyin)
                    
                    updated_pinyin += 1
                    
                except Exception as e:
                    logger.warning(f"为股票 {code}({name}) 生成拼音失败: {e}")
                    continue

        session.commit()
        logger.info(f"成功保存或更新 {updated_stocks} 支股票信息（代码+名称）")
        logger.info(f"成功处理 {updated_pinyin} 支股票的拼音信息（仅处理6位代码）")
    except SQLAlchemyError as e:
        session.rollback()
        logger.error(f"保存股票信息出错: {e}", exc_info=True)
    finally:
        session.close()


if __name__ == '__main__':
    initialize_database()
    fetch_and_save_stock_names()
