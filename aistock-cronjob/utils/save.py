# utils/save.py

from .db import engine, SessionLocal, Base
from .model import News, HotStock, StockInfo, StockRealtimeQuote, Stocks, Index, NewsEmbedding, Tag, NewsTagRelation, NewsSummary
from sqlalchemy.exc import SQLAlchemyError
import hashlib
from datetime import datetime
import numpy as np
import traceback
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

def initialize_database():
    try:
        print("开始初始化数据库表...")
        Base.metadata.create_all(bind=engine)  # 自动创建所有表
        print("✅ 数据库表初始化成功")
    except SQLAlchemyError as e:
        print(f"❌ 初始化失败: {e}")

def save_news(news_list):
    """
    保存新闻列表到数据库
    
    返回:
    - 字典，包含已保存新闻的信息，键为news_id，值为{content, is_new}
    """
    session = SessionLocal()
    result = {}
    
    try:
        new_count = 0
        update_count = 0
        skip_count = 0
        
        # 批量获取现有股票代码，避免外键约束错误
        existing_stocks_codes = {code for code, in session.query(Stocks.code).all()}
        
        for news in news_list:
            # 计算内容哈希值
            content_hash = hashlib.sha256(news['content'].encode('utf-8')).hexdigest()
            # 获取当前时间作为下载时间
            current_time = datetime.now()
            
            # 检查并创建股票代码记录（如果需要）
            news_code = news.get('code')
            if news_code and news_code not in existing_stocks_codes:
                # 为新闻类别创建对应的股票记录
                stock_name = {
                    'hk_us': '港美股',
                    'cn': 'A股',
                    'watch': 'A股',
                    'top': '头条'
                }.get(news_code, news_code)
                
                new_stock = Stocks(code=news_code, name=stock_name, market='NEWS')
                session.add(new_stock)
                session.flush()  # 确保立即插入
                existing_stocks_codes.add(news_code)
            
            # 检查是否存在ID，有ID表示更新现有新闻
            if 'id' in news and news['id']:
                # 在更新前检查是否有哈希冲突（相同哈希但不同ID的记录）
                existing_news_with_hash = session.query(News).filter(
                    News.content_hash == content_hash,
                    News.id != news['id']
                ).first()
                
                if existing_news_with_hash:
                    # 存在冲突，记录日志并跳过此条
                    print(f"⚠️ 哈希冲突: 新闻ID {news['id']} 的内容与ID {existing_news_with_hash.id} 重复，跳过更新")
                    skip_count += 1
                    # 仍然返回当前新闻ID
                    result[news['id']] = {'content': news['content'], 'is_new': False, 'skipped': True}
                    continue
                
                # 更新现有新闻
                session.query(News).filter(News.id == news['id']).update({
                    'title': news['title'],
                    'content': news['content'],
                    'content_hash': content_hash,
                    'ctime': news['ctime'],
                    'link': news.get('link'),
                    'code': news_code,
                    'download_time': current_time
                })
                result[news['id']] = {'content': news['content'], 'is_new': False}
                update_count += 1
            else:
                # 检查数据库中是否已存在相同的 content_hash
                exists = session.query(News).filter(News.content_hash == content_hash).first()
                if not exists:
                    # 如果不存在，则创建新记录
                    new_entry = News(
                        ctime=news['ctime'],
                        title=news['title'],
                        content=news['content'],
                        content_hash=content_hash,
                        link=news.get('link'),
                        code=news_code,
                        download_time=current_time
                    )
                    session.add(new_entry)
                    session.flush()  # 获取自动生成的ID
                    result[new_entry.id] = {'content': news['content'], 'is_new': True}
                    new_count += 1
                else:
                    # 已存在，记录日志
                    print(f"⚠️ 内容已存在: 发现重复新闻内容 (ID: {exists.id}): {news['title']}")
                    result[exists.id] = {'content': news['content'], 'is_new': False, 'existing': True}
                    skip_count += 1
                
        session.commit()
        print(f"✅ 成功保存 {new_count} 条新新闻，更新 {update_count} 条现有新闻，跳过 {skip_count} 条重复新闻")
        return result
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❗ 保存出错: {e}")
        return {}
    finally:
        session.close()

def save_hot_stocks(hot_stocks_list):
    """
    优化版本：保存热门股票数据到数据库
    - 批量处理，减少数据库交互
    - 智能更新，避免不必要的删除重建
    - 详细统计和日志记录
    """
    if not hot_stocks_list:
        print("⚠️ 热门股票列表为空，跳过保存")
        return
    
    session = SessionLocal()
    try:
        current_time = datetime.now()
        
        # 1. 批量获取现有的股票代码，避免重复查询
        existing_stocks_codes = {code for code, in session.query(Stocks.code).all()}
        
        # 2. 批量获取现有的热门股票数据
        existing_hot_stocks = {hot.code: hot for hot in session.query(HotStock).all()}
        
        # 3. 准备新增的股票记录
        new_stocks_to_add = []
        hot_stocks_to_add = []
        hot_stocks_to_update = []
        
        # 4. 处理每个热门股票
        for stock in hot_stocks_list:
            code = stock['code']
            name = stock.get('name', '')
            market = 'HK' if len(code) == 5 else 'CN'  # 优化市场判断逻辑
            
            # 检查是否需要添加到 Stocks 表
            if code not in existing_stocks_codes:
                new_stocks_to_add.append(Stocks(code=code, name=name, market=market))
                existing_stocks_codes.add(code)  # 避免重复添加
            
            # 检查是否需要更新或新增热门股票记录
            if code in existing_hot_stocks:
                # 更新现有记录
                existing_hot = existing_hot_stocks[code]
                if (existing_hot.rank != stock['rank'] or 
                    existing_hot.remark != stock['remark']):
                    existing_hot.rank = stock['rank']
                    existing_hot.remark = stock['remark']
                    existing_hot.updated_at = current_time
                    hot_stocks_to_update.append(existing_hot)
            else:
                # 新增记录
                hot_stocks_to_add.append(HotStock(
                    code=code,
                    rank=stock['rank'],
                    remark=stock['remark'],
                    updated_at=current_time
                ))
        
        # 5. 找出需要删除的热门股票（不在新列表中的）
        new_codes = {stock['code'] for stock in hot_stocks_list}
        hot_stocks_to_delete = [code for code in existing_hot_stocks.keys() if code not in new_codes]
        
        # 6. 执行数据库操作
        operation_count = 0
        
        # 批量添加新股票
        if new_stocks_to_add:
            session.add_all(new_stocks_to_add)
            operation_count += len(new_stocks_to_add)
        
        # 批量添加新热门股票
        if hot_stocks_to_add:
            session.add_all(hot_stocks_to_add)
            operation_count += len(hot_stocks_to_add)
        
        # 批量删除过期的热门股票
        if hot_stocks_to_delete:
            session.query(HotStock).filter(HotStock.code.in_(hot_stocks_to_delete)).delete(synchronize_session=False)
            operation_count += len(hot_stocks_to_delete)
        
        # 提交所有更改
        session.commit()
        
        # 7. 输出详细统计信息
        print(f"✅ 热门股票数据保存完成:")
        print(f"   - 新增股票基础信息: {len(new_stocks_to_add)} 条")
        print(f"   - 新增热门股票: {len(hot_stocks_to_add)} 条")
        print(f"   - 更新热门股票: {len(hot_stocks_to_update)} 条")
        print(f"   - 删除过期热门股票: {len(hot_stocks_to_delete)} 条")
        print(f"   - 总计处理: {len(hot_stocks_list)} 条热门股票数据")
        
        return True
        
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❗ 保存热门股票数据出错: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def save_stock_info_batch(stock_info_list):
    session = SessionLocal()
    try:
        # 1) 取已有的 Stocks.code
        existing_stocks_codes = {code for code, in session.query(Stocks.code).all()}

        # —— 一次性取出 StockInfo.code，避免同批次重复插入 —— 
        existing_info_codes = {code for code, in session.query(StockInfo.code).all()}

        for stock_info in stock_info_list:
            # 辅助转换函数：转 int
            def to_int(v):
                try:
                    return int(v)
                except (ValueError, TypeError):
                    return None

            # 辅助转换函数：转 date（不是 datetime）
            def to_data(v):
                try:
                    s = str(v).strip()
                    # 1) 13 位时间戳（毫秒）
                    if v and isinstance(v, (int, float)) and len(s) == 13 and s.isdigit():
                        return datetime.fromtimestamp(v / 1000).date()
                    
                    # 2) 8 位纯数字（YYYYMMDD），支持数字或字符串
                    if len(s) == 8 and s.isdigit():
                        return datetime.strptime(s, "%Y%m%d").date()
                    
                    # 3) 标准短横线日期（'YYYY-MM-DD'）
                    if isinstance(v, str) and len(s) == 10 and s[4] == '-' and s[7] == '-':
                        return datetime.strptime(s, "%Y-%m-%d").date()
                    
                    # 其它情况一律视为无效
                    return None
                except (ValueError, TypeError):
                    return None

            code = stock_info['code']
            name = stock_info.get('name', '')

            # 确保 Stocks 表有该 code
            if code not in existing_stocks_codes:
                session.add(Stocks(code=code, name=name))
                existing_stocks_codes.add(code)

            # 字段转换
            total_shares       = to_int(stock_info.get('total_shares'))
            circulating_shares = to_int(stock_info.get('circulating_shares'))
            industry           = stock_info.get('industry')
            listing_date       = to_data(stock_info.get('listing_date'))
            now                = datetime.now()

            # 插入或更新 StockInfo
            if code in existing_info_codes:
                session.query(StockInfo).filter_by(code=code).update({
                    'total_shares':       total_shares,
                    'circulating_shares': circulating_shares,
                    'industry':           industry,
                    'listing_date':       listing_date,
                    'updated_at':         now,
                })
            else:
                session.add(StockInfo(
                    code=code,
                    total_shares=total_shares,
                    circulating_shares=circulating_shares,
                    industry=industry,
                    listing_date=listing_date,
                    updated_at=now
                ))
                existing_info_codes.add(code)

        session.commit()
        print(f"✅ 批量保存或更新 {len(stock_info_list)} 条股票信息")
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❗ 批量保存股票信息出错: {e}")
    finally:
        session.close()

def save_realtime_quotes(quotes_list):
    session = SessionLocal()
    try:
        # 预处理：将NaN统一转为None（提前在DataFrame处理更好）
        processed_quotes = [
            {k: (None if isinstance(v, float) and np.isnan(v) else v) for k, v in q.items()}
            for q in quotes_list
        ]

        # 1. 批量查询已存在的code（减少循环内查询）
        existing_stocks_codes = {code for code, in session.query(Stocks.code).all()}
        existing_quote_codes = {code for code, in session.query(StockRealtimeQuote.code).all()}

        # 2. 分桶收集数据
        new_stocks = []
        new_quotes = []
        update_quotes = []

        for quote in processed_quotes:
            code = quote['代码']
            # 处理Stocks表
            if code not in existing_stocks_codes:
                new_stocks.append(Stocks(code=code, name=quote['名称']))
                existing_stocks_codes.add(code)  # 避免重复添加

            # 处理实时行情表
            quote_data = {
                'code': code,
                'latest_price': quote['最新价'],
                'change_percent': quote['涨跌幅'],
                'change_amount': quote['涨跌额'],
                'volume': quote['成交量'],
                'turnover': quote['成交额'],
                'amplitude': quote['振幅'],
                'high': quote['最高'],
                'low': quote['最低'],
                'open_price': quote['今开'],
                'previous_close': quote['昨收'],
                'volume_ratio': quote['量比'],
                'turnover_rate': quote['换手率'],
                'pe_ratio_dynamic': quote['市盈率-动态'],
                'pb_ratio': quote['市净率'],
                'total_market_value': quote['总市值'],
                'circulating_market_value': quote['流通市值'],
                'speed': quote['涨速'],
                'change_5min': quote['5分钟涨跌'],
                'change_60d': quote['60日涨跌幅'],
                'change_ytd': quote['年初至今涨跌幅'],
                'updated_at': datetime.now()
            }

            if code in existing_quote_codes:
                update_quotes.append(quote_data)
            else:
                new_quotes.append(StockRealtimeQuote(**quote_data))

        # 3. 批量插入Stocks（单次提交）
        if new_stocks:
            session.bulk_save_objects(new_stocks)

        # 4. 批量插入新行情数据
        if new_quotes:
            session.bulk_save_objects(new_quotes)

        # 5. 批量更新已有行情数据（修复参数错误）
        if update_quotes:
            session.bulk_update_mappings(StockRealtimeQuote, update_quotes)
  
        session.commit()
        print(f"✅ 批量处理完成：新增Stocks {len(new_stocks)}条，新增行情{len(new_quotes)}条，更新行情{len(update_quotes)}条")

    except Exception as e:
        session.rollback()
        print(f"❌ 批量处理失败：{str(e)}")
    finally:
        session.close()

def save_market_indices(indices_list):
    """
    保存或更新市场指数数据
    参数: 
    - indices_list: 包含指数数据的字典列表
    """
    if not indices_list:
        print("⚠️ 指数列表为空，跳过保存")
        return False
        
    session = SessionLocal()
    try:
        # 批量获取已存在的指数代码，不再查询不存在的id字段
        existing_indices = {idx_code for idx_code, in 
                          session.query(Index.idx_code).all()}
        
        new_indices = []
        updates = []
        current_time = datetime.now()
        
        for index_data in indices_list:
            idx_code = index_data['idx_code']
            
            # 数据验证
            try:
                value = float(index_data['value'])
                change_amount = float(index_data['change_amount'])
                change_percent = float(index_data['change_percent'])
            except (ValueError, TypeError) as e:
                print(f"⚠️ 指数 {idx_code} 数据格式错误: {e}")
                continue
            
            index_record = {
                'idx_code': idx_code,
                'name': index_data['name'],
                'value': value,
                'change_amount': change_amount,
                'change_percent': change_percent,
                'updated_at': current_time
            }
            
            if idx_code in existing_indices:
                # 准备更新数据
                updates.append(index_record)
            else:
                # 准备新增数据
                new_indices.append(Index(**index_record))
                existing_indices.add(idx_code)  # 防止重复添加
        
        # 批量更新现有记录
        if updates:
            for update in updates:
                session.query(Index).filter_by(idx_code=update['idx_code']).update({
                    'name': update['name'],
                    'value': update['value'],
                    'change_amount': update['change_amount'],
                    'change_percent': update['change_percent'],
                    'updated_at': update['updated_at']
                })
        
        # 批量添加新记录
        if new_indices:
            session.bulk_save_objects(new_indices)
            
        session.commit()
        
        print(f"✅ 成功保存指数数据: 新增 {len(new_indices)} 条，更新 {len(updates)} 条")
        return True
        
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❗ 保存指数数据失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        session.close()

def save_news_embeddings(embeddings_data):
    """
    保存新闻嵌入向量到数据库
    
    参数:
    - embeddings_data: 包含新闻嵌入的字典列表，每个字典包含 news_id, embedding_vector, model_name
    """
    session = SessionLocal()
    try:
        # 预处理
        existing_embeddings = {news_id for news_id, in session.query(NewsEmbedding.news_id).all()}
        
        new_embeddings = []
        update_count = 0
        
        for data in embeddings_data:
            news_id = data['news_id']
            vector = data['embedding_vector']
            model = data['model_name']
            
            # 转换为Python列表，数据库会自动处理JSON序列化
            if isinstance(vector, np.ndarray):
                vector = vector.tolist()
            
            if news_id in existing_embeddings:
                # 更新现有记录
                session.query(NewsEmbedding).filter_by(news_id=news_id).update({
                    'embedding_vector': vector,
                    'model_name': model,
                    'updated_at': datetime.now()
                })
                update_count += 1
            else:
                # 添加新记录
                new_embedding = NewsEmbedding(
                    news_id=news_id,
                    embedding_vector=vector,
                    model_name=model
                )
                new_embeddings.append(new_embedding)
        
        # 保存新记录
        if new_embeddings:
            session.add_all(new_embeddings)
            
        session.commit()
        print(f"✅ 成功保存 {len(new_embeddings)} 条新嵌入数据，更新 {update_count} 条嵌入数据")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❗ 保存嵌入数据失败: {e}")
        return False
    finally:
        session.close()

def save_news_tags(tags_data):
    """
    保存新闻标签信息到数据库
    
    参数:
    - tags_data: 包含新闻标签的字典列表，每个字典包含:
      - news_id: 新闻ID
      - positive_tags: 正向标签列表
      - negative_tags: 负向标签列表 
      - is_important: 是否重要新闻
      - summary: 新闻摘要
    """
    session = SessionLocal()
    try:
        # 获取所有已存在的标签
        existing_tags = {name.lower(): (id, type) for id, name, type in 
                        session.query(Tag.id, Tag.name, Tag.tag_type).all()}
        
        # 获取已有的新闻-标签关系
        existing_relations = {(news_id, tag_id) for news_id, tag_id in 
                             session.query(NewsTagRelation.news_id, NewsTagRelation.tag_id).all()}
        
        # 获取已有摘要的新闻ID
        existing_summaries = {news_id for news_id, in 
                             session.query(NewsSummary.news_id).all()}
        
        new_tags = []  # 需要新增的标签
        new_relations = []  # 需要新增的新闻-标签关系
        new_summaries = []  # 需要新增的摘要
        updated_summaries = 0  # 已更新的摘要计数
        updated_news = 0  # 已更新新闻重要性标记计数
        
        # 处理每条传入的标签数据
        for data in tags_data:
            news_id = data['news_id']
            is_important = data.get('is_important', False)
            summary = data.get('summary')
            
            # 1. 更新新闻重要性
            session.query(News).filter(News.id == news_id).update({
                'is_important': 1 if is_important else 0
            })
            updated_news += 1
            
            # 2. 处理摘要
            if summary:
                if news_id in existing_summaries:
                    # 更新已有摘要
                    session.query(NewsSummary).filter(NewsSummary.news_id == news_id).update({
                        'summary': summary
                    })
                    updated_summaries += 1
                else:
                    # 添加新摘要
                    new_summaries.append(NewsSummary(
                        news_id=news_id,
                        summary=summary
                    ))
                    existing_summaries.add(news_id)  # 防止批处理中重复
            
            # 3. 处理标签
            # 处理正向标签
            for tag_name in data.get('positive_tags', []):
                if not tag_name or not tag_name.strip():
                    continue
                    
                tag_name_lower = tag_name.lower()
                # 检查标签是否存在
                if tag_name_lower in existing_tags:
                    tag_id, tag_type = existing_tags[tag_name_lower]
                else:
                    # 创建新标签
                    tag = Tag(
                        name=tag_name.strip(),
                        tag_type=1  # 正向标签
                    )
                    session.add(tag)
                    session.flush()  # 获取新标签的ID
                    tag_id = tag.id
                    existing_tags[tag_name_lower] = (tag_id, 1)
                
                # 创建新闻-标签关系
                if (news_id, tag_id) not in existing_relations:
                    new_relations.append(NewsTagRelation(
                        news_id=news_id,
                        tag_id=tag_id
                    ))
                    existing_relations.add((news_id, tag_id))
            
            # 处理负向标签
            for tag_name in data.get('negative_tags', []):
                if not tag_name or not tag_name.strip():
                    continue
                    
                tag_name_lower = tag_name.lower()
                # 检查标签是否存在
                if tag_name_lower in existing_tags:
                    tag_id, tag_type = existing_tags[tag_name_lower]
                else:
                    # 创建新标签
                    tag = Tag(
                        name=tag_name.strip(),
                        tag_type=0  # 负向标签
                    )
                    session.add(tag)
                    session.flush()
                    tag_id = tag.id
                    existing_tags[tag_name_lower] = (tag_id, 0)
                
                # 创建新闻-标签关系
                if (news_id, tag_id) not in existing_relations:
                    new_relations.append(NewsTagRelation(
                        news_id=news_id,
                        tag_id=tag_id
                    ))
                    existing_relations.add((news_id, tag_id))
        
        # 批量添加新的摘要
        if new_summaries:
            session.add_all(new_summaries)
        
        # 批量添加新的新闻-标签关系
        if new_relations:
            session.add_all(new_relations)
        
        session.commit()
        print(f"✅ 成功处理新闻标签数据: 更新{updated_news}条新闻重要性, {len(new_relations)}条新标签关系, {len(new_summaries)}条新摘要, 更新{updated_summaries}条现有摘要")
        return True
    except SQLAlchemyError as e:
        session.rollback()
        print(f"❗ 保存新闻标签数据失败: {e}")
        return False
    finally:
        session.close()

def get_news_from_db(limit=5000, code=None):
    """
    从数据库获取新闻记录
    
    参数:
    - limit: 最大返回记录数
    - code: 股票代码过滤器
    
    返回:
    - 新闻记录列表，每条记录包含 id, title, content, ctime, link, code 等字段
    """
    session = SessionLocal()
    try:
        query = session.query(News)
        
        # 根据股票代码过滤
        if code:
            query = query.filter(News.code == code)
            
        # 按时间倒序并限制返回数量
        news_records = query.order_by(News.ctime.desc()).limit(limit).all()
        
        # 转换为字典列表
        news_list = [
            {
                'id': news.id,
                'title': news.title,
                'content': news.content,
                'content_hash': news.content_hash,
                'ctime': news.ctime,
                'link': news.link,
                'code': news.code
            }
            for news in news_records
        ]
        
        return news_list
    except SQLAlchemyError as e:
        print(f"❗ 获取新闻数据出错: {e}")
        return []
    finally:
        session.close()

def get_news_embeddings(model_name, news_ids=None):
    """
    从数据库获取新闻嵌入向量
    
    参数:
    - model_name: 嵌入模型名称
    - news_ids: 可选，要获取的特定新闻ID列表
    
    返回:
    - 字典，键为news_id，值为对应的嵌入向量numpy数组
    """
    session = SessionLocal()
    try:
        query = session.query(NewsEmbedding.news_id, NewsEmbedding.embedding_vector)
        query = query.filter(NewsEmbedding.model_name == model_name)
        
        if news_ids:
            query = query.filter(NewsEmbedding.news_id.in_(news_ids))
        
        result = {}
        for news_id, vector in query.all():
            # 将JSON数据转换回numpy数组
            vector_np = np.array(vector)
            result[news_id] = vector_np
            
        return result
    except SQLAlchemyError as e:
        print(f"❗ 获取嵌入数据出错: {e}")
        return {}
    finally:
        session.close()

def get_all_news_with_embeddings(model_name, code=None, limit=5000):
    """
    获取带有嵌入向量的新闻列表
    
    参数:
    - model_name: 嵌入模型名称
    - code: 可选，股票代码过滤
    - limit: 最大返回记录数
    
    返回:
    - 新闻记录列表，每条包含嵌入向量
    """
    session = SessionLocal()
    try:
        query = session.query(
            News.id, News.title, News.content, News.content_hash,
            News.ctime, News.link, News.code,
            NewsEmbedding.embedding_vector
        ).outerjoin(
            NewsEmbedding, 
            (News.id == NewsEmbedding.news_id) & 
            (NewsEmbedding.model_name == model_name)
        )
        
        if code:
            query = query.filter(News.code == code)
            
        # 按时间倒序并限制返回数量
        results = query.order_by(News.ctime.desc()).limit(limit).all()
        
        news_list = []
        for row in results:
            news_dict = {
                'id': row.id,
                'title': row.title,
                'content': row.content,
                'content_hash': row.content_hash,
                'ctime': row.ctime,
                'link': row.link,
                'code': row.code,
                'embedding': np.array(row.embedding_vector) if row.embedding_vector else None
            }
            news_list.append(news_dict)
            
        return news_list
    except SQLAlchemyError as e:
        print(f"❗ 获取新闻及嵌入数据出错: {e}")
        return []
    finally:
        session.close()

def get_recent_news_with_embeddings(model_name, code, limit=25):
    """
    获取特定类别的最近几条新闻及其嵌入向量
    
    参数:
    - model_name: 嵌入模型名称
    - code: 股票代码/新闻类别
    - limit: 获取的记录数量
    
    返回:
    - 新闻记录列表，每条包含嵌入向量
    """
    session = SessionLocal()
    try:
        query = session.query(
            News.id, News.title, News.content, News.content_hash,
            News.ctime, News.link, News.code,
            NewsEmbedding.embedding_vector
        ).outerjoin(
            NewsEmbedding, 
            (News.id == NewsEmbedding.news_id) & 
            (NewsEmbedding.model_name == model_name)
        ).filter(News.code == code)
        
        # 按时间倒序并限制返回数量
        results = query.order_by(News.ctime.desc()).limit(limit).all()
        
        news_list = []
        for row in results:
            news_dict = {
                'id': row.id,
                'title': row.title,
                'content': row.content,
                'content_hash': row.content_hash,
                'ctime': row.ctime,
                'link': row.link,
                'code': row.code,
                'embedding': np.array(row.embedding_vector) if row.embedding_vector else None
            }
            news_list.append(news_dict)
            
        return news_list
    except SQLAlchemyError as e:
        print(f"❗ 获取最近新闻及嵌入数据出错: {e}")
        return []
    finally:
        session.close()

def check_content_hashes(hash_list):
    """
    检查哪些内容哈希已存在于数据库
    
    参数:
    - hash_list: 需要检查的哈希值列表
    
    返回:
    - 已存在哈希值的集合
    """
    if not hash_list:
        return set()
        
    session = SessionLocal()
    try:
        # 批量查询哈希值是否存在
        results = session.query(News.content_hash).filter(
            News.content_hash.in_(hash_list)
        ).all()
        
        # 返回已存在的哈希值集合
        return {row[0] for row in results}
    except SQLAlchemyError as e:
        print(f"❗ 检查内容哈希失败: {e}")
        return set()
    finally:
        session.close()