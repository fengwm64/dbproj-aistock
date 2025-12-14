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
logger = logging.getLogger("stock_news")

# 用于检测中文字符的正则表达式
chinese_pattern = re.compile(r'[\u4e00-\u9fff]')

def get_all_watched_stocks() -> Set[str]:
    """获取所有用户关注的股票代码集合，并加入前20热门股票（国内人气榜）"""
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

@lru_cache(maxsize=1000)
def get_stock_name(stock_code: str) -> str:
    """根据股票代码获取股票名称，使用缓存避免重复查询"""
    with get_db_session() as session:
        stock = session.query(Stocks.name).filter(Stocks.code == stock_code).first()
        if stock:
            return stock.name
    return ""

def count_chinese_chars(text: str) -> int:
    """计算文本中中文字符的数量"""
    if not text:
        return 0
    return len(chinese_pattern.findall(text))

def _update_news_in_db(stock_code, news_data):
    """
    更新数据库中的新闻数据
    :param stock_code: 股票代码
    :param news_data: 新闻数据(可以是DataFrame或列表)
    """
    logger.debug(f"[news/update] 开始更新新闻，stock_code={stock_code}")
    now = datetime.now()  # 获取当前时间作为下载时间
    
    added_count = 0
    skipped_count = 0
    duplicate_count = 0
    
    # 使用no_autoflush避免自动刷新导致的问题
    with db.session.no_autoflush:
        # 检查输入类型并相应处理
        if hasattr(news_data, 'iterrows'):  # 如果是DataFrame
            items = news_data.iterrows()
        else:  # 如果是列表
            items = enumerate(news_data)
            
        for _, item in items:
            try:
                # 根据输入类型获取数据
                if hasattr(news_data, 'iterrows'):  # DataFrame行
                    title = item.get("新闻标题", "").strip()
                    content = item.get("新闻内容", "").strip()
                    tstr = item.get("发布时间", "").strip()
                    source = item.get("文章来源", "").strip()
                    url = item.get("新闻链接", "").strip()
                else:  # 字典
                    title = item.get("title", "").strip()
                    content = item.get("content", "").strip()
                    tstr = ""
                    publish_time = item.get("ctime", datetime.now())
                    source = ""
                    url = item.get("link", "").strip()

                # 如果是DataFrame行处理时间字符串，否则直接使用datetime对象
                if hasattr(news_data, 'iterrows') and tstr:
                    try:
                        t = tstr.replace("年", "-").replace("月", "-").replace("日", " ")
                        if len(t) == 10:
                            t += " 00:00:00"
                        publish_time = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        publish_time = datetime.now()

                if not (title and content and len(content) >= 20):
                    logger.debug("[news/update] 跳过无效或过短新闻")
                    skipped_count += 1
                    continue

                # 计算内容哈希值，用于去重
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # 检查是否已存在
                existing_news = db.session.query(News).filter_by(content_hash=content_hash).first()
                if existing_news:
                    skipped_count += 1
                    continue

                # 插入新新闻
                new_news = News(
                    title=title,
                    content=content,
                    ctime=publish_time,
                    link=url,
                    code=stock_code,
                    content_hash=content_hash,
                    download_time=now
                )
                
                try:
                    db.session.add(new_news)
                    db.session.flush()  # 尝试立即执行插入操作，可能触发唯一键错误
                    added_count += 1
                except Exception as e:
                    # 检查是否是唯一键冲突
                    if isinstance(e, (db.exc.IntegrityError, db.exc.SQLAlchemyError)) and "Duplicate entry" in str(e):
                        logger.debug(f"[news/update] 忽略重复内容: {content_hash[:10]}...")
                        duplicate_count += 1
                        db.session.rollback()  # 回滚当前事务
                        continue
                    else:
                        # 其他类型错误，重新抛出
                        raise
                
                # 定期提交以避免事务过大
                if added_count % 10 == 0:
                    db.session.commit()
                    
            except Exception as e:
                # 捕获每条新闻处理中的错误，记录但不中断流程
                logger.warning(f"[news/update] 处理单条新闻时出错: {e}")
                # 回滚当前新闻的处理，但继续下一条
                db.session.rollback()
    
    try:
        # 最终提交所有更改
        db.session.commit()
        logger.debug(f"[news/update] 新闻更新完成，添加: {added_count}，跳过: {skipped_count}，重复: {duplicate_count}")
    except Exception as e:
        # 如果提交失败，回滚并记录错误
        db.session.rollback()
        logger.error(f"[news/update] 提交更改失败: {e}", exc_info=True)

def process_news_for_stock(stock_code: str) -> Tuple[int, int]:
    """获取单个股票的相关新闻，返回成功和失败数"""
    stock_name = get_stock_name(stock_code)
    # 如果未找到股票名称，直接返回失败
    if not stock_name:
        logger.warning(f"未找到股票代码 {stock_code} 对应的股票名称，跳过")
        return 0, 1
    
    logger.info(f"==="*25)

    if not stock_name:
        logger.warning(f"未找到股票代码 {stock_code} 对应的股票名称，跳过")
        return 0, 1
    
    try:
        logger.info(f"正在获取股票 {stock_code}({stock_name}) 的新闻...")
        df = ak.stock_news_em(symbol=stock_name)
        
        if df is None or df.empty:
            logger.warning(f"股票 {stock_code}({stock_name}) 没有获取到任何新闻")
            return 0, 1
        
        # 过滤新闻，确保包含股票名称或股票代码，且中文字符不少于20个
        filtered_news = []
        for _, row in df.iterrows():
            title = str(row.get("新闻标题", ""))
            content = str(row.get("新闻内容", ""))
            
            # 检查标题或内容是否包含股票名称或代码
            name_match = stock_name in title or stock_name in content
            code_match = stock_code in title or stock_code in content
            
            # 检查中文字符数量
            chinese_count = count_chinese_chars(content)
            
            if (name_match or code_match) and chinese_count >= 20:
                # 构建新闻字典
                news_item = {
                    'title': title,
                    'content': content,
                    'ctime': datetime.now() if not row.get("发布时间") else datetime.strptime(str(row.get("发布时间")), "%Y-%m-%d %H:%M:%S"),
                    'link': row.get("新闻链接", ""),
                    'code': stock_code
                }
                filtered_news.append(news_item)
        
        logger.info(f"股票 {stock_code}({stock_name}) 原始新闻数量: {len(df)}，过滤后数量: {len(filtered_news)}")
        
        # 如果过滤后没有新闻，返回失败
        if not filtered_news:
            return 0, 1
        
        # 使用SemHash进行语义去重
        try:
            # 将新闻列表转换为DataFrame
            filtered_df = pd.DataFrame(filtered_news)
            
            # 加载预训练模型
            logger.info(f"加载SemHash进行语义去重...")
            
            # 直接传入DataFrame，并指定content列作为去重依据
            semhash = SemHash.from_records(records=filtered_df.to_dict(orient="records"), columns=["content"], use_ann=False)

            # 执行去重操作，设置相似度阈值为0.8
            dedup_result = semhash.self_deduplicate(threshold=0.8)
            
            # 根据去重后的索引获取唯一新闻
            unique_news = dedup_result.selected

            logger.info(f"股票 {stock_code}({stock_name}) 语义去重后新闻数量: {len(unique_news)}")
        except Exception as e:
            # SemHash失败时，直接返回失败，不处理新闻
            logger.error(f"使用SemHash去重时出错，放弃处理此股票新闻: {str(e)}")
            return 0, 1
        
        # 只保留最新的20条新闻
        unique_news = sorted(unique_news, key=lambda x: x['ctime'], reverse=True)[:20]
        
        # 更新到数据库
        _update_news_in_db(stock_code, unique_news)

        return 1, 0
        
    except Exception as e:
        logger.error(f"获取股票 {stock_code}({stock_name}) 新闻时出错: {str(e)}", exc_info=True)
        return 0, 1

def fetch_stock_news():
    """获取所有用户关注股票的新闻"""
    # 获取所有被关注的股票代码
    watched_stocks = get_all_watched_stocks()
    
    success_count = 0
    fail_count = 0
    
    # 循环遍历每个股票代码
    for stock_code in watched_stocks:
        # 处理每个股票的新闻
        s_count, f_count = process_news_for_stock(stock_code)
        success_count += s_count
        fail_count += f_count
            
        # 添加延时，避免请求过于频繁
        time.sleep(random.uniform(0.5, 1.5))
    
    print(f"新闻请求完成：成功 {success_count} 个，失败 {fail_count} 个")
    return success_count, fail_count

if __name__ == "__main__":
    print(f"开始时间: {datetime.now()}")
    success_count, fail_count = fetch_stock_news()
    print(f"结束时间: {datetime.now()}")
