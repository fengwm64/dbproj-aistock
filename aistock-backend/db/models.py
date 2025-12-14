from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean, Date, BigInteger, UniqueConstraint, JSON, DECIMAL
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from datetime import datetime
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

load_dotenv(override=True)

# 初始化引擎和 session
db = SQLAlchemy()
engine = create_engine(os.getenv("DATABASE_URI"), echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = db.Model

class Stocks(Base):
    __tablename__ = 'stocks'

    code = Column(String(10), primary_key=True, comment='股票代码，主键')
    name = Column(String(255), nullable=False, comment='股票名称')
    market = Column(String(10), nullable=True, comment='市场类型代码')

    # 一对一实时行情
    realtime_quote = relationship('StockRealtimeQuote', back_populates='stocks', uselist=False, cascade='all, delete-orphan')

    # 一对一基本面信息
    info = relationship('StockInfo', back_populates='stocks', uselist=False, cascade='all, delete-orphan')

    # 收藏记录
    user_stocks = relationship('UserStock', back_populates='stocks', cascade='all, delete-orphan')

    # 热门股票记录
    hot_entries = relationship('HotStock', back_populates='stocks', cascade='all, delete-orphan')

    # 股票相关新闻
    news = relationship('News', back_populates='stocks', cascade='all, delete-orphan')

    # 历史记录
    stock_history = relationship('StockHistory', back_populates='stocks', cascade='all, delete-orphan')

    # 添加与 StockEvaluation 的关系
    evaluations = relationship('StockEvaluation', back_populates='stocks', cascade='all, delete-orphan')

    # 添加与标签的关系
    tags_relation = relationship('StockTagRelation', back_populates='stock', cascade='all, delete-orphan')
    
    # 添加与拼音信息的关系
    pinyin_info = relationship('StockPinyin', back_populates='stocks', uselist=False, cascade='all, delete-orphan')

    # 添加与业绩预测的关系
    forecasts = relationship('StockForecast', back_populates='stocks', cascade='all, delete-orphan')



class StockRealtimeQuote(Base):
    __tablename__ = 'stock_realtime_quotes'

    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码，主键 & 外键')
    latest_price = Column(Float, comment='最新价格')
    change_percent = Column(Float, comment='涨跌幅（百分比）')
    change_amount = Column(Float, comment='涨跌额')
    volume = Column(Float, comment='成交量')
    turnover = Column(Float, comment='成交额')
    amplitude = Column(Float, comment='振幅')
    high = Column(Float, comment='最高价')
    low = Column(Float, comment='最低价')
    open_price = Column(Float, comment='开盘价')
    previous_close = Column(Float, comment='昨日收盘价')
    volume_ratio = Column(Float, comment='量比')
    turnover_rate = Column(Float, comment='换手率')
    pe_ratio_dynamic = Column(Float, comment='动态市盈率')
    pb_ratio = Column(Float, comment='市净率')
    total_market_value = Column(Float, comment='总市值')
    circulating_market_value = Column(Float, comment='流通市值')
    speed = Column(Float, comment='当前上涨速度')
    change_5min = Column(Float, comment='5分钟涨跌幅')
    change_60d = Column(Float, comment='60日涨跌幅')
    change_ytd = Column(Float, comment='年初至今涨跌幅')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='最后更新时间')

    stocks = relationship('Stocks', back_populates='realtime_quote')


class StockInfo(Base):
    __tablename__ = 'stock_info'

    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码，主键 & 外键')
    total_shares = Column(BigInteger, nullable=True, comment='总股本（单位：股）')
    circulating_shares = Column(BigInteger, nullable=True, comment='流通股本（单位：股）')
    industry = Column(String(50), nullable=True, comment='所属行业')
    listing_date = Column(Date, nullable=True, comment='上市日期')  # 确保类型为 DateTime
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='最后更新时间')

    stocks = relationship('Stocks', back_populates='info')


class HotStock(Base):
    __tablename__ = 'hot_stock'

    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码，主键 & 外键')
    rank = Column(Integer, nullable=False, comment='榜单排名')
    remark = Column(String(50), nullable=False, comment='榜单备注')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='最后更新时间')

    stocks = relationship('Stocks', back_populates='hot_entries')


class Index(Base):
    """市场指数表：存储上证指数、深证成指等主要指数数据"""
    __tablename__ = 'market_indices'

    idx_code = Column(String(20), primary_key=True, comment='指数代码')
    name = Column(String(50), nullable=False, comment='指数名称')
    value = Column(Float, nullable=False, comment='指数当前值')
    change_amount = Column(Float, nullable=False, comment='变化值（正负表示涨跌）')
    change_percent = Column(Float, nullable=False, comment='变化百分比（如3.21表示上涨3.21%）')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='最后更新时间')


class News(Base):
    __tablename__ = 'news'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='新闻 ID')
    ctime = Column(DateTime, nullable=False, default=datetime.now, comment='发布时间')
    title = Column(String(255), nullable=False, comment='新闻标题')
    content = Column(Text, nullable=False, comment='新闻正文')
    content_hash = Column(CHAR(64), nullable=False, unique=True, index=True, comment='内容哈希')
    link = Column(String(255), comment='原始链接')
    code = Column(String(10), ForeignKey('stocks.code', ondelete='SET NULL'), nullable=True, index=True, comment='股票代码')
    is_important = Column(Integer, nullable=True, default=None, comment='是否重要：0=不重要，1=重要')
    download_time = Column(DateTime, nullable=True, comment='新闻下载时间')

    stocks = relationship('Stocks', back_populates='news')

    # 添加与嵌入的关系
    embedding = relationship('NewsEmbedding', back_populates='news', uselist=False, cascade='all, delete-orphan')
    
    # 添加与标签关系表的关联
    tags_relation = relationship('NewsTagRelation', back_populates='news', cascade='all, delete-orphan')
    
    # 添加与摘要的关系
    summary = relationship('NewsSummary', back_populates='news', uselist=False, cascade='all, delete-orphan')
    
    # 添加与推送记录的多对多关系
    push_records = relationship('PushRecord', secondary='push_news_relations', back_populates='news')


class NewsEmbedding(Base):
    """存储新闻内容的嵌入向量，用于相似度计算和去重"""
    __tablename__ = 'news_embeddings'

    news_id = Column(Integer, ForeignKey('news.id', ondelete='CASCADE'), primary_key=True, comment='关联的新闻ID')
    embedding_vector = Column(JSON, nullable=False, comment='嵌入向量JSON数据')
    model_name = Column(String(100), nullable=False, comment='使用的嵌入模型')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')

    news = relationship('News', back_populates='embedding')


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, comment='用户 ID')
    openid = Column(String(128), unique=True, nullable=False, index=True, comment='微信 openid')
    session_key = Column(String(255), nullable=True, comment='会话密钥')
    unionid = Column(String(128), nullable=True, index=True, comment='微信 unionid')
    nickname = Column(String(64), nullable=True, comment='昵称')
    avatar_url = Column(String(255), nullable=True, comment='头像链接')
    role = Column(String(20), default='user', comment='角色')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    subscribe = Column(Boolean, default=False, comment='是否关注公众号')
    subscribe_time = Column(DateTime, nullable=True, comment='关注时间')
    subscribe_scene = Column(String(50), nullable=True, comment='关注场景')

    stocks = relationship('UserStock', back_populates='user', cascade='all, delete-orphan')
    push_records = relationship('PushRecord', back_populates='user', cascade='all, delete-orphan')
    # 添加推送配置关系
    push_configs = relationship('UserPushConfig', back_populates='user', cascade='all, delete-orphan')


class PushRecord(Base):
    __tablename__ = 'push_records'

    msgid = Column(String(64), primary_key=True, comment='消息ID')
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, comment='用户ID')
    push_time = Column(DateTime, default=datetime.now, nullable=False, comment='推送时间')
    content = Column(JSON, nullable=False, comment='推送内容')
    result = Column(String(50), nullable=False, comment='推送结果')
    
    user = relationship('User', back_populates='push_records')
    # 添加与news的多对多关系
    news = relationship('News', secondary='push_news_relations', back_populates='push_records')


class UserStock(Base):
    __tablename__ = 'user_stocks'

    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), primary_key=True, comment='外键：用户')
    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码')
    added_at = Column(DateTime, default=datetime.now, comment='添加时间')

    user = relationship('User', back_populates='stocks')
    stocks = relationship('Stocks', back_populates='user_stocks')


class StockHistory(Base):
    __tablename__ = 'stock_history'

    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码，主键 & 外键')
    date = Column(Date, primary_key=True, comment='交易日期')
    open_price = Column(Float, nullable=True, comment='开盘价')
    close_price = Column(Float, nullable=True, comment='收盘价')
    high = Column(Float, nullable=True, comment='最高价')
    low = Column(Float, nullable=True, comment='最低价')
    volume = Column(Float, nullable=True, comment='成交量')
    turnover = Column(Float, nullable=True, comment='成交额')
    amplitude = Column(Float, nullable=True, comment='振幅')
    change_percent = Column(Float, nullable=True, comment='涨跌幅')
    change_amount = Column(Float, nullable=True, comment='涨跌额')
    turnover_rate = Column(Float, nullable=True, comment='换手率')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='记录更新时间')

    stocks = relationship('Stocks', back_populates='stock_history')


class Tag(Base):
    __tablename__ = 'tags'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='标签ID')
    name = Column(String(50), nullable=False, unique=True, comment='标签名称')
    tag_type = Column(Integer, nullable=False, default=1, comment='标签类型：1=正向(利好)，0=负向(利空)')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    
    # 与新闻的关系
    news = relationship('NewsTagRelation', back_populates='tag', cascade='all, delete-orphan')
    # 与股票的关系
    stocks = relationship('StockTagRelation', back_populates='tag', cascade='all, delete-orphan')


class NewsTagRelation(Base):
    __tablename__ = 'news_tag_relations'
    
    news_id = Column(Integer, ForeignKey('news.id', ondelete='CASCADE'), primary_key=True, comment='新闻ID')
    tag_id = Column(Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True, comment='标签ID')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    
    news = relationship('News', back_populates='tags_relation')
    tag = relationship('Tag', back_populates='news')
    
    __table_args__ = (UniqueConstraint('news_id', 'tag_id', name='uq_news_tag'),)


class StockTagRelation(Base):
    __tablename__ = 'stock_tag_relations'
    
    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码')
    tag_id = Column(Integer, ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True, comment='标签ID')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    reason = Column(Text, nullable=True, comment='关联原因')
    
    stock = relationship('Stocks', back_populates='tags_relation')
    tag = relationship('Tag', back_populates='stocks')
    
    __table_args__ = (UniqueConstraint('code', 'tag_id', name='uq_stock_tag'),)


class StockEvaluation(Base):
    __tablename__ = 'stock_evaluation'

    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码，主键 & 外键')
    evaluation_time = Column(DateTime, primary_key=True, default=datetime.now, comment='评价时间，主键')
    conclusion = Column(String(50), nullable=False, comment='评价结论')
    reason = Column(Text, nullable=True, comment='评价理由')
    news_list = Column(JSON, nullable=True, comment='评估时的新闻列表，JSON 格式')

    stocks = relationship('Stocks', back_populates='evaluations')


class UpdateRecord(Base):
    """更新记录表：记录各种数据的更新操作"""
    __tablename__ = 'update_records'

    id = Column(Integer, primary_key=True, autoincrement=True, comment='记录ID')
    update_type = Column(String(50), nullable=False, index=True, comment='更新类型')
    message = Column(Text, nullable=True, comment='更新内容描述')
    created_at = Column(DateTime, server_default=func.now(), comment='记录时间')


class NewsSummary(Base):
    """存储新闻摘要内容"""
    __tablename__ = 'news_summaries'

    news_id = Column(Integer, ForeignKey('news.id', ondelete='CASCADE'), primary_key=True, comment='关联的新闻ID')
    summary = Column(Text, nullable=False, comment='新闻摘要内容')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')

    news = relationship('News', back_populates='summary')


class PushNewsRelation(Base):
    __tablename__ = 'push_news_relations'
    
    msgid = Column(String(64), ForeignKey('push_records.msgid', ondelete='CASCADE'), primary_key=True, comment='消息ID')
    news_id = Column(Integer, ForeignKey('news.id', ondelete='CASCADE'), primary_key=True, comment='新闻ID')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    
    __table_args__ = (UniqueConstraint('msgid', 'news_id', name='uq_push_news'),)


class UserPushConfig(Base):
    """用户推送配置表：记录用户对不同类型推送的开关设置"""
    __tablename__ = 'user_push_configs'
    
    id = Column(Integer, primary_key=True, autoincrement=True, comment='配置ID')
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True, comment='用户ID')
    push_type = Column(String(50), nullable=False, comment='推送类型，如stock_push(自选股推送)、morning_report(早报推送)等')
    enabled = Column(Boolean, default=False, nullable=False, comment='是否启用该类型推送')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='配置更新时间')
    
    user = relationship('User', back_populates='push_configs')
    
    __table_args__ = (UniqueConstraint('user_id', 'push_type', name='uq_user_push_type'),)


class StockPinyin(Base):
    """股票拼音表：存储股票名称与拼音首字母的对应关系"""
    __tablename__ = 'stock_pinyin'
    
    code = Column(String(10), ForeignKey('stocks.code', ondelete='CASCADE'), primary_key=True, comment='股票代码，主键 & 外键')
    pinyin = Column(String(50), nullable=False, index=True, comment='股票名称拼音首字母')
    full_pinyin = Column(String(255), nullable=True, comment='股票名称完整拼音')
    created_at = Column(DateTime, default=datetime.now, comment='创建时间')
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, comment='更新时间')
    
    # 建立与Stocks表的关系
    stocks = relationship('Stocks', back_populates='pinyin_info')


class StockForecast(Base):
    """股票业绩预测汇总表"""
    __tablename__ = 'stock_forecast'

    id = Column(String(10), primary_key=True, comment='主键ID')
    code = Column(String(20), ForeignKey('stocks.code', ondelete='CASCADE'), nullable=False, index=True, comment='股票代码')
    report_period = Column(String(20), nullable=True, comment='报告期 (如 2025Q3)')
    announcement_date = Column(Date, nullable=True, comment='公告日期')
    forecast_type = Column(String(50), nullable=True, comment='预测类型 (如 预增)')
    profit_forecast_median = Column(DECIMAL(20, 2), nullable=True, comment='预计净利润中值')
    profit_growth_median = Column(DECIMAL(10, 2), nullable=True, comment='预计净利润增长中值(%)')
    last_year_profit = Column(DECIMAL(20, 2), nullable=True, comment='去年同期净利润')
    forecast_summary = Column(Text, nullable=True, comment='业绩变动摘要')

    stocks = relationship('Stocks', back_populates='forecasts')
