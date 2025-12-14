import requests
import uuid
import json
import time as time_module
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from utils.db import get_db_session
from utils.model import User, PushRecord, News, UserStock, Stocks, StockInfo, PushNewsRelation, UserPushConfig
from pprint import pprint
from datetime import datetime, timedelta
from utils.ai_utils import analyze_stocks_news
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 从环境变量获取配置
APPID = os.getenv("WECHAT_SCAN_APPID")
APPSECRET = os.getenv("WECHAT_SCAN_SECRET")
# TEMPLATE_ID = "rCl1mTgMEv04E7SPHXtAA8Eh6vnBA9b-kfVveoj9mDM"
TEMPLATE_ID = "tBz_mygvn7tGjt7xQ7YrI7ApL1MaDiYAGrEZ2AA0zsw"

# 从数据库获取启用推送的用户，而不是硬编码
def get_users_with_stock_push_enabled():
    """获取开启了自选股推送的用户openid列表"""
    with get_db_session() as session:
        # 查询开启了自选股推送的用户配置
        enabled_configs = session.query(UserPushConfig).filter(
            UserPushConfig.push_type == 'stock_push',
            UserPushConfig.enabled == True
        ).all()
        
        # 如果没有用户开启推送，返回空列表
        if not enabled_configs:
            print("没有用户开启了自选股推送")
            return []
        
        # 获取这些用户的ID
        user_ids = [config.user_id for config in enabled_configs]
        
        # 查询这些用户的openid
        users = session.query(User).filter(User.id.in_(user_ids)).all()
        
        # 返回openid列表
        user_openids = [user.openid for user in users if user.openid]
        print(f"找到{len(user_openids)}个开启了自选股推送的用户")
        return user_openids

def get_access_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}"
    res = requests.get(url).json()
    return res["access_token"]

def get_stock_news(session, user_openid):
    """获取用户关注的股票及头条新闻的1小时内数据库记录"""
    from datetime import datetime, timedelta
    start_time = time_module.time()

    # 计算最近1小时的时间范围
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)

    # 获取用户对象
    user = session.query(User).filter(User.openid == user_openid).first()
    if not user:
        print(f"未找到用户: {user_openid}")
        return [], []

    # 获取用户关注的股票代码列表
    user_stocks = session.query(UserStock).filter(UserStock.user_id == user.id).all()
    stock_codes = [item.code for item in user_stocks]
    
    # 如果用户未关注股票，则只返回头条新闻
    if not stock_codes:
        print(f"用户未关注任何股票: {user_openid}")
        stock_codes = []

    # 查询头条新闻和用户关注股票新闻
    query_start = time_module.time()
    # 找到属于用户关注股票(code in stock_codes)
    all_news = session.query(News).filter(
        ((News.code.in_(stock_codes))) &
        (News.ctime >= one_hour_ago) &
        (News.ctime <= now)
    ).order_by(News.ctime.desc()).all()
    query_end = time_module.time()
    print(f"数据库新闻查询耗时: {query_end - query_start:.2f}秒, 获取{len(all_news)}条记录")

    if not all_news:
        print("没有找到相关新闻")
        return [], []

    # 构建股票名称列表
    from sqlalchemy.orm import joinedload
    stocks = session.query(Stocks).options(
        joinedload(Stocks.info)
    ).filter(Stocks.code.in_(stock_codes)).all() if stock_codes else []
    
    # 构建行业信息字典
    stock_info_dict = {info.code: info.industry for info in session.query(StockInfo).filter(StockInfo.code.in_(stock_codes)).all()}
    stock_name_list = []
    for stock in stocks:
        industry = stock_info_dict.get(stock.code) or (getattr(stock.info, 'industry', None) if stock.info else None) or '未知行业'
        stock_name_list.append(f"{stock.code} {stock.name or '未知'} {industry}")

    # 提取新闻文本
    text_start = time_module.time()
    news_text = "\n\n".join(
        f"{news.id}. [{news.title}]({news.link}) {news.content[:1000]}" 
        for news in all_news
    )
    text_end = time_module.time()
    print(f"新闻文本提取耗时: {text_end - text_start:.2f}秒")

    # 分析新闻
    ai_start = time_module.time()
    analysis_results = analyze_stocks_news(news_text, stock_name_list)
    ai_end = time_module.time()
    
    # 打印原始的AI分析结果，用于调试
    print("AI原始分析结果:")
    pprint(analysis_results)
    
    # 修改这里的处理逻辑
    good_news = []
    bad_news = []
    
    # 显式遍历AI返回的结果
    for item in analysis_results:
        # 打印每个结果项，便于调试
        print(f"处理AI结果项: {item}")
        
        # 获取评价字段，处理可能的大小写和空白问题
        evaluation = item.get('evaluation', '').strip()
        
        # 将AI返回的每个新闻项标准化
        news_item = {
            'title': item.get('title', ''),
            'content': item.get('content', item.get('title', '')),
            'evaluation': evaluation,
            'stock': item.get('stock', item.get('影响自选股', item.get('sector', '-'))),
            'time': item.get('time', '--:--'),
            'news_id': item.get('news_id', item.get('id', '0')),
            'reason': item.get('reason', item.get('理由', ''))
        }
        
        # 依据评价字段分类
        if '重大利好' in evaluation or '利好' in evaluation:
            good_news.append(news_item)
        elif '重大利空' in evaluation or '利空' in evaluation:
            bad_news.append(news_item)
    
    print(f"分析结果: 找到{len(good_news)}条利好新闻和{len(bad_news)}条利空新闻")
    
    end_time = time_module.time()
    print(f"新闻处理总耗时: {end_time - start_time:.2f}秒")
    return good_news[:2], bad_news[:2]


def build_message_data(date, news_item):
    """根据新模板格式构建消息数据"""
    return {
        "Date": {"value": date, "color": "#173177"},
        "news_title": {"value": news_item['title'], "color": "#173177"},
        "stock_name": {"value": news_item.get('stock', '无'), "color": "#173177"},
        "ai_eva": {"value": news_item['evaluation'], "color": "#173177"},
        "ai_sum": {"value": news_item.get('reason', '无'), "color": "#173177"},
        "news_time": {"value": news_item['time'], "color": "#173177"}
    }

def get_user_id_by_openid(session, openid):
    """通过OpenID获取用户ID"""
    user = session.query(User).filter(User.openid == openid).first()
    return user.id if user else None

def send_template_message(openid, data, news_id="0"):
    # 生成唯一的消息ID - 使用UUID的hex格式（32字符，不带破折号）
    msg_uuid = uuid.uuid4().hex
    
    token = get_access_token()
    url = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"
    payload = {
        "touser": openid,
        "template_id": TEMPLATE_ID,
        "url": f"https://aistocklink.cn/wechat/{msg_uuid}",  # 使用UUID作为URL参数
        "topcolor": "#FF9900",
        "data": data
    }
    pprint(payload)
    
    # 发送请求
    res = requests.post(url, json=payload)
    result = res.json()
    
    # 存储推送记录
    with get_db_session() as session:
        user_id = get_user_id_by_openid(session, openid)
        if user_id:
            # 直接使用字典对象
            content_data = {
                "date": data["Date"]["value"],
                "news_title": data["news_title"]["value"],
                "stock_name": data["stock_name"]["value"],
                "ai_eva": data["ai_eva"]["value"],
                "ai_sum": data["ai_sum"]["value"],
                "news_time": data["news_time"]["value"]
            }
            
            # 创建推送记录
            push_record = PushRecord(
                msgid=msg_uuid,
                user_id=user_id,
                push_time=datetime.now(),
                content=content_data,
                result="success" if result.get("errcode") == 0 else f"failed: {result}"
            )
            session.add(push_record)
            session.commit()
    
    # 如果有对应的新闻ID，创建关联记录
    if news_id != "0":
        try:
            news_id_int = int(news_id)
            with get_db_session() as session:
                # 验证新闻是否存在
                news_exists = session.query(News).filter(News.id == news_id_int).first() is not None
                if news_exists:
                    relation = PushNewsRelation(
                        msgid=msg_uuid,
                        news_id=news_id_int,
                        created_at=datetime.now()
                    )
                    session.add(relation)
                    # 提交关联记录
                    session.commit()
        except (ValueError, TypeError):
            pass
    
    return result

def get_user_stocks_news(session, user_openid):
    """获取用户自选股的最近三小时内每个股票的2条最新未推送新闻并进行AI分析"""
    start_time = time_module.time()
    
    # 计算最近3小时的时间范围
    now = datetime.now()
    three_hours_ago = now - timedelta(hours=3)
    
    # 获取用户对象
    user = session.query(User).filter(User.openid == user_openid).first()
    if not user:
        print(f"未找到用户: {user_openid}")
        return []
    
    # 获取用户关注的股票代码列表
    user_stocks = session.query(UserStock).filter(UserStock.user_id == user.id).all()
    stock_codes = [item.code for item in user_stocks]
    print(f"用户 {user_openid} 关注的股票代码: {stock_codes}")
    
    if not stock_codes:
        print(f"用户未关注任何股票: {user_openid}")
        return []
    
    # 使用join同时获取Stocks和StockInfo的信息
    from sqlalchemy.orm import joinedload
    stocks_info = session.query(Stocks).options(
        joinedload(Stocks.info)
    ).filter(Stocks.code.in_(stock_codes)).all()
    
    # 创建stock_info_dict和stock_name_dict
    stock_info_dict = {}
    stock_name_dict = {}
    
    for stock in stocks_info:
        stock_info_dict[stock.code] = stock
        # 股票名称和股票代码一起显示
        stock_name_dict[stock.code] = f"{stock.name}"
    
    # 获取行业信息作为补充
    industry_info = {info.code: info.industry for info in 
                   session.query(StockInfo).filter(StockInfo.code.in_(stock_codes)).all()}
    
    # 获取用户已经推送过的新闻ID列表
    pushed_news_ids_query = session.query(PushNewsRelation.news_id).join(
        PushRecord, PushRecord.msgid == PushNewsRelation.msgid
    ).filter(
        PushRecord.user_id == user.id
    )
    pushed_news_ids = [item[0] for item in pushed_news_ids_query.all()]
    print(f"用户已推送过的新闻数量: {len(pushed_news_ids)}")
    
    # 按要求的格式组织股票和新闻数据
    stocks_with_news = []
    all_news_dict = {}  # 用于存储所有新闻的字典，key为news_id
    has_news = False
    
    for code in stock_codes:
        # 查询条件
        stock_news = session.query(News).filter(
            News.code == code,
            News.ctime >= three_hours_ago,
            News.ctime <= now,
            or_(News.is_important.is_(None), News.is_important == 1),  # 修正OR条件语法
            ~News.id.in_(pushed_news_ids) if pushed_news_ids else True
        ).order_by(News.ctime.desc()).limit(2).all()
        
        if stock_news:
            has_news = True
            stock_info = stock_info_dict.get(code)
            
            news_list = []
            for news in stock_news:
                # 存储到全局字典中，方便后续通过ID查找
                all_news_dict[str(news.id)] = {
                    "title": news.title,
                    "content": news.content,
                    "publish_time": news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
                    "stock_code": code,
                    "stock_name": stock_name_dict.get(code, "未知")
                }
                
                news_list.append({
                    "id": str(news.id),
                    "title": news.title,
                    "publish_time": news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
                    "content": news.content
                })
            
            stocks_with_news.append({
                "stock_code": code,
                "stock_name": stock_name_dict.get(code, "未知"),
                "industry": industry_info.get(code, "未知行业"),
                "news": news_list
            })

    if not has_news:
        print(f"用户 {user_openid} 的自选股在最近3小时内没有未推送的新闻")
        return []
    
    # 分析新闻
    try:
        # 打印调试信息
        print("传递给AI分析的数据结构:")
        print(json.dumps(stocks_with_news, ensure_ascii=False, indent=2)[:200] + "...")
        
        analysis_results = analyze_stocks_news(stocks_with_news)
        print("AI分析结果:")
        pprint(analysis_results)
    except Exception as e:
        print(f"分析股票新闻时发生错误: {e}")
        import logging
        logging.error(f"分析股票新闻时发生错误: {e}", exc_info=True)
        return []
    
    # 创建所有新闻ID的集合，用于跟踪哪些新闻已经在分析结果中
    all_news_ids = set(all_news_dict.keys())
    analyzed_news_ids = set()
    
    # 更新新闻重要性标记 - 标记重要新闻
    for item in analysis_results:
        news_id_str = str(item.get('news_id', item.get('id', '0')))
        if news_id_str.isdigit() and news_id_str != '0':
            news_id = int(news_id_str)
            analyzed_news_ids.add(news_id_str)
            is_important = 1 if ('重大利好' in item.get('evaluation', '') or 
                               '重大利空' in item.get('evaluation', '')) else 0
            
            # 更新数据库
            news = session.query(News).filter(News.id == news_id).first()
            if news:
                news.is_important = is_important
    
    # 标记未出现在分析结果中的新闻为不重要(0)
    for news_id_str in all_news_ids - analyzed_news_ids:
        if news_id_str.isdigit() and news_id_str != '0':
            try:
                news_id = int(news_id_str)
                news = session.query(News).filter(News.id == news_id).first()
                if news and news.is_important is None:  # 只更新尚未标记的新闻
                    news.is_important = 0
                    print(f"新闻 ID {news_id} 未出现在AI分析结果中，标记为不重要")
            except Exception as e:
                print(f"标记新闻ID {news_id_str} 时出错: {e}")
    
    session.commit()
    
    # 不再分类新闻为利好和利空，仅过滤保留重大新闻
    important_news = []
    
    for item in analysis_results:
        evaluation = item.get('evaluation', '').strip()
        news_id_str = str(item.get('news_id', item.get('id', '0')))
        
        # 只保留"重大利好"或"重大利空"的新闻
        if '重大利好' in evaluation or '重大利空' in evaluation:
            # 从all_news_dict获取原始新闻信息
            original_news = all_news_dict.get(news_id_str, {})

            
            news_item = {
                'title': original_news.get('title', item.get('title', '无标题')),
                'content': original_news.get('content', item.get('content', item.get('title', '无内容'))),
                'evaluation': evaluation,
                'stock': original_news.get('stock_name', item.get('stock', '未知股票')),
                'time': original_news.get('publish_time', item.get('time', '--:--')),
                'news_id': news_id_str,
                'reason': item.get('reason', item.get('理由', ''))
            }

            important_news.append(news_item)
    
    print(f"分析结果: 找到{len(important_news)}条重大新闻")
    
    # 打印调试信息
    if important_news:
        print("第一条重大新闻示例:")
        pprint(important_news[0])
    
    end_time = time_module.time()
    print(f"新闻处理总耗时: {end_time - start_time:.2f}秒")
    return important_news

# 构造内容
now = datetime.now()
formatted_datetime = now.strftime("%Y年%m月%d日 %H时%M分")

# 获取开启了推送的用户列表
USERS = get_users_with_stock_push_enabled()

# 如果没有开启推送的用户，直接退出
if not USERS:
    print("没有用户开启了推送功能，结束执行")
    exit(0)

# 执行推送
for user_openid in USERS:
    with get_db_session() as session:
        user = session.query(User).filter(User.openid == user_openid).first()
        if not user:
            print(f"未找到用户: {user_openid}")
            continue
        
        # 获取用户自选股新闻
        important_news = get_user_stocks_news(session, user_openid)

        # 如果没有获取到重大新闻，则跳过此用户
        if not important_news:
            print(f"跳过用户 {user_openid} 的推送，因为没有重大新闻")
            continue
        
        # 限制最多推送4条新闻
        important_news = important_news[:4]
        print(f"用户 {user_openid} 将接收 {len(important_news)} 条重大新闻推送(最多4条)")
        
        # 为每条实际新闻发送单独的推送
        for news_item in important_news:
            message_data = build_message_data(formatted_datetime.strip(), news_item)
            send_template_message(user_openid, message_data, news_item['news_id'])
            # 避免微信接口限流，每次发送后稍微延迟
            time_module.sleep(0.5)
