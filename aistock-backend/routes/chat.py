from flask import Blueprint, request, Response, stream_with_context, jsonify
from utils.ai_utils import LLMClient
from db.models import db
from sqlalchemy import text, create_engine
import json
import logging
import re
import os

chat_bp = Blueprint('chat', __name__)
llm_client = LLMClient()

def get_readonly_engine():
    """获取只读数据库连接引擎"""
    readonly_uri = os.getenv("DATABASE_URI_READONLY")
    if readonly_uri:
        return create_engine(readonly_uri)
    logging.warning("未配置 DATABASE_URI_READONLY，将使用默认数据库连接")
    return db.engine

# 数据库表结构描述
DB_SCHEMA = """
Table: stocks (股票基本信息表)
- code (VARCHAR(10), Primary Key): 股票代码，主键
- name (VARCHAR(255)): 股票名称
- market (VARCHAR(10)): 市场类型代码

Table: stock_realtime_quotes (股票实时行情表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码，主键 & 外键
- latest_price (FLOAT): 最新价格
- change_percent (FLOAT): 涨跌幅（百分比）
- change_amount (FLOAT): 涨跌额
- volume (FLOAT): 成交量
- turnover (FLOAT): 成交额
- amplitude (FLOAT): 振幅
- high (FLOAT): 最高价
- low (FLOAT): 最低价
- open_price (FLOAT): 开盘价
- previous_close (FLOAT): 昨日收盘价
- volume_ratio (FLOAT): 量比
- turnover_rate (FLOAT): 换手率
- pe_ratio_dynamic (FLOAT): 动态市盈率
- pb_ratio (FLOAT): 市净率
- total_market_value (FLOAT): 总市值
- circulating_market_value (FLOAT): 流通市值
- speed (FLOAT): 当前上涨速度
- change_5min (FLOAT): 5分钟涨跌幅
- change_60d (FLOAT): 60日涨跌幅
- change_ytd (FLOAT): 年初至今涨跌幅
- updated_at (DATETIME): 最后更新时间

Table: stock_info (股票基本面信息表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码，主键 & 外键
- total_shares (BIGINT): 总股本（单位：股）
- circulating_shares (BIGINT): 流通股本（单位：股）
- industry (VARCHAR(50)): 所属行业
- listing_date (DATE): 上市日期
- updated_at (DATETIME): 最后更新时间

Table: hot_stock (热门股票榜单表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码，主键 & 外键
- rank (INT): 榜单排名
- remark (VARCHAR(50)): 榜单备注
- updated_at (DATETIME): 最后更新时间

Table: market_indices (市场指数表)
- idx_code (VARCHAR(20), Primary Key): 指数代码
- name (VARCHAR(50)): 指数名称
- value (FLOAT): 指数当前值
- change_amount (FLOAT): 变化值（正负表示涨跌）
- change_percent (FLOAT): 变化百分比（如3.21表示上涨3.21%）
- updated_at (DATETIME): 最后更新时间

Table: news (新闻资讯表)
- id (INT, Primary Key): 新闻 ID
- ctime (DATETIME): 发布时间
- title (VARCHAR(255)): 新闻标题
- content (TEXT): 新闻正文
- content_hash (CHAR(64)): 内容哈希
- link (VARCHAR(255)): 原始链接
- code (VARCHAR(10), Foreign Key): 股票代码
- is_important (INT): 是否重要：0=不重要，1=重要
- download_time (DATETIME): 新闻下载时间

Table: stock_forecast (股票业绩预测汇总表)
- id (VARCHAR(10), Primary Key): 主键ID
- code (VARCHAR(20), Foreign Key): 股票代码
- report_period (VARCHAR(20)): 报告期 (如 2025Q3)
- announcement_date (DATE): 公告日期
- forecast_type (VARCHAR(50)): 预测类型 (如 预增)
- profit_forecast_median (DECIMAL(20,2)): 预计净利润中值
- profit_growth_median (DECIMAL(10,2)): 预计净利润增长中值(%)
- last_year_profit (DECIMAL(20,2)): 去年同期净利润
- forecast_summary (TEXT): 业绩变动摘要

Table: news_embeddings (新闻向量表)
- news_id (INT, Primary Key, Foreign Key): 关联的新闻ID
- embedding_vector (JSON): 嵌入向量JSON数据
- model_name (VARCHAR(100)): 使用的嵌入模型
- created_at (DATETIME): 创建时间
- updated_at (DATETIME): 更新时间

Table: users (用户信息表)
- id (INT, Primary Key): 用户 ID
- openid (VARCHAR(128)): 微信 openid
- session_key (VARCHAR(255)): 会话密钥
- unionid (VARCHAR(128)): 微信 unionid
- nickname (VARCHAR(64)): 昵称
- avatar_url (VARCHAR(255)): 头像链接
- role (VARCHAR(20)): 角色
- created_at (DATETIME): 创建时间
- updated_at (DATETIME): 更新时间
- subscribe (BOOL): 是否关注公众号
- subscribe_time (DATETIME): 关注时间
- subscribe_scene (VARCHAR(50)): 关注场景

Table: push_records (推送记录表)
- msgid (VARCHAR(64), Primary Key): 消息ID
- user_id (INT, Foreign Key): 用户ID
- push_time (DATETIME): 推送时间
- content (JSON): 推送内容
- result (VARCHAR(50)): 推送结果

Table: user_stocks (用户自选股关联表)
- user_id (INT, Primary Key, Foreign Key): 外键：用户
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码
- added_at (DATETIME): 添加时间

Table: stock_history (股票历史数据表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码，主键 & 外键
- date (DATE, Primary Key): 交易日期
- open_price (FLOAT): 开盘价
- close_price (FLOAT): 收盘价
- high (FLOAT): 最高价
- low (FLOAT): 最低价
- volume (FLOAT): 成交量
- turnover (FLOAT): 成交额
- amplitude (FLOAT): 振幅
- change_percent (FLOAT): 涨跌幅
- change_amount (FLOAT): 涨跌额
- turnover_rate (FLOAT): 换手率
- updated_at (DATETIME): 记录更新时间

Table: tags (标签表)
- id (INT, Primary Key): 标签ID
- name (VARCHAR(50)): 标签名称
- tag_type (INT): 标签类型：1=正向(利好)，0=负向(利空)
- created_at (DATETIME): 创建时间

Table: news_tag_relations (新闻标签关联表)
- news_id (INT, Primary Key, Foreign Key): 新闻ID
- tag_id (INT, Primary Key, Foreign Key): 标签ID
- created_at (DATETIME): 创建时间

Table: stock_tag_relations (股票标签关联表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码
- tag_id (INT, Primary Key, Foreign Key): 标签ID
- created_at (DATETIME): 创建时间
- reason (TEXT): 关联原因

Table: stock_evaluation (股票智能评价表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码，主键 & 外键
- evaluation_time (DATETIME, Primary Key): 评价时间，主键
- conclusion (VARCHAR(50)): 评价结论
- reason (TEXT): 评价理由
- news_list (JSON): 评估时的新闻列表，JSON 格式

Table: stock_pinyin (股票拼音表)
- code (VARCHAR(10), Primary Key, Foreign Key): 股票代码，主键 & 外键
- pinyin (VARCHAR(50)): 股票名称拼音首字母
- full_pinyin (VARCHAR(255)): 股票名称完整拼音
- created_at (DATETIME): 创建时间
- updated_at (DATETIME): 更新时间
"""

def clean_sql(sql_text):
    """清理 LLM 返回的 SQL，去除 markdown 标记"""
    # 移除 ```sql 和 ```
    pattern = r"```sql\s*(.*?)\s*```"
    match = re.search(pattern, sql_text, re.DOTALL)
    if match:
        return match.group(1).strip()
    
    pattern_plain = r"```\s*(.*?)\s*```"
    match_plain = re.search(pattern_plain, sql_text, re.DOTALL)
    if match_plain:
        return match_plain.group(1).strip()
        
    return sql_text.strip()

@chat_bp.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    data = request.json
    messages = data.get('messages', [])
    
    if not messages:
        return jsonify({"error": "No messages provided"}), 400

    # 获取用户最后一个问题
    user_query = messages[-1]['content']
    
    # 1. 构造 SQL 生成提示词
    system_prompt = f"""
    你是一个专业的数据库助手。请根据以下数据库表结构和用户问题，生成一个可执行的 MySQL SQL 查询语句。
    
    {DB_SCHEMA}
    
    要求：
    1. 只返回 SQL 语句，不要包含任何解释或 markdown 标记。
    2. 确保 SQL 语法正确，兼容 MySQL。
    3. 如果涉及模糊查询，请使用 LIKE。
    4. 关联查询时请使用 JOIN。
    5. 这是一个只读操作，绝对禁止使用 INSERT, UPDATE, DELETE, DROP 等修改数据的语句。
    
    用户问题：{user_query}
    """
    
    sql_generation_messages = [{"role": "system", "content": system_prompt}]
    
    generated_sql = ""
    query_result = None
    error_message = None
    
    # 2. 循环尝试生成并执行 SQL (最多3次)
    for attempt in range(3):
        try:
            # 调用 LLM 生成 SQL
            logging.info(f"Attempt {attempt+1}: Generating SQL for query: {user_query}")
            generated_sql_response = llm_client.chat(sql_generation_messages, temperature=0.1)
            generated_sql = clean_sql(generated_sql_response)
            
            logging.info(f"Generated SQL: {generated_sql}")
            
            # 简单的安全检查
            if not generated_sql.lower().startswith("select"):
                raise ValueError("只允许执行 SELECT 查询")
            
            # 执行 SQL
            # 使用独立的连接执行查询
            engine = get_readonly_engine()
            with engine.connect() as connection:
                result_proxy = connection.execute(text(generated_sql))
                keys = result_proxy.keys()
                query_result = [dict(zip(keys, row)) for row in result_proxy.fetchall()]
            
            # 如果成功，跳出循环
            error_message = None
            break
            
        except Exception as e:
            error_message = str(e)
            logging.error(f"SQL Execution failed: {error_message}")
            # 将错误信息反馈给 LLM
            sql_generation_messages.append({"role": "assistant", "content": generated_sql})
            sql_generation_messages.append({"role": "user", "content": f"SQL执行错误: {error_message}。请修正SQL。"})
    
    # 3. 根据查询结果生成最终回答
    def generate_response():
        if error_message:
            # 如果最终还是失败，告知用户
            yield f"抱歉，我无法查询到相关数据。错误信息: {error_message}"
            return

        # 构造最终回答的上下文
        final_context_messages = [
            {"role": "system", "content": "你是一个智能股票助手。请根据用户的问题和数据库查询结果，用自然、专业的语言回答用户。如果查询结果为空，请礼貌告知用户未找到相关信息。"},
            {"role": "user", "content": f"用户问题：{user_query}\n\n数据库查询结果：{json.dumps(query_result, ensure_ascii=False, default=str)}"}
        ]
        
        # 流式返回 LLM 的回答
        for chunk in llm_client.chat_stream(final_context_messages):
            yield chunk

    return Response(stream_with_context(generate_response()), mimetype='text/event-stream')
