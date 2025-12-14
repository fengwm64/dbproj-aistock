import requests
import uuid
import json
import time as time_module  # 重命名time模块以避免命名冲突
import os
from sqlalchemy.orm import Session
from sqlalchemy import or_
from utils.db import get_db_session
from utils.model import User, PushRecord, News, Tag, NewsTagRelation, UserPushConfig, PushNewsRelation
from pprint import pprint
from datetime import datetime
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(override=True)

# 从环境变量获取配置
APPID = os.getenv("WECHAT_SCAN_APPID")
APPSECRET = os.getenv("WECHAT_SCAN_SECRET")
TEMPLATE_ID = "RL9bd_C6Sc_ZF2TIMfT5Ug0d4hBOOfOr3zPH9CZRxdk"

# 从数据库获取开启早报推送的用户，而不是硬编码
def get_users_with_morning_report_enabled():
    """获取开启了早报推送的用户openid列表"""
    with get_db_session() as session:
        # 查询开启了早报推送的用户配置
        enabled_configs = session.query(UserPushConfig).filter(
            UserPushConfig.push_type == 'morning_report',
            UserPushConfig.enabled == True
        ).all()
        
        # 如果没有用户开启推送，返回空列表
        if not enabled_configs:
            print("没有用户开启了早报推送")
            return []
        
        # 获取这些用户的ID
        user_ids = [config.user_id for config in enabled_configs]
        
        # 查询这些用户的openid
        users = session.query(User).filter(User.id.in_(user_ids)).all()
        
        # 返回openid列表
        user_openids = [user.openid for user in users if user.openid]
        print(f"找到{len(user_openids)}个开启了早报推送的用户")
        return user_openids

def get_access_token():
    url = f"https://api.weixin.qq.com/cgi-bin/token?grant_type=client_credential&appid={APPID}&secret={APPSECRET}"
    res = requests.get(url).json()
    print(res)
    return res["access_token"]

def get_hk_us_news(session):
    """从数据库获取港美股重要新闻并查询关联标签"""
    start_time = time_module.time()  # 使用重命名后的time模块
    
    # 查询最新的重要新闻（is_important=1）
    query_start = time_module.time()
    news_list = session.query(News).filter(
        News.code == 'hk_us',
        News.is_important == 1
    ).order_by(News.ctime.desc()).limit(2).all()
    query_end = time_module.time()
    print(f"港美股新闻查询耗时: {query_end - query_start:.2f}秒, 获取{len(news_list)}条记录")

    # 获取新闻标签
    formatted_news = []
    for news in news_list:
        # 查询新闻关联的标签
        news_tags = session.query(Tag).join(
            NewsTagRelation, NewsTagRelation.tag_id == Tag.id
        ).filter(
            NewsTagRelation.news_id == news.id
        ).all()
        
        # 将标签按类型分组
        positive_tags = [tag for tag in news_tags if tag.tag_type == 1]
        negative_tags = [tag for tag in news_tags if tag.tag_type == 0]
        
        # 默认评价和影响板块
        evaluation = "中性"
        sector = "暂无影响板块"
        
        # 根据标签类型设置评价，只拼接同类型的标签
        if positive_tags:  # 有利好标签
            evaluation = "利好"
            # 只拼接利好标签
            sector = "，".join([tag.name for tag in positive_tags])
        elif negative_tags:  # 有利空标签但没有利好标签
            evaluation = "利空"
            # 只拼接利空标签
            sector = "，".join([tag.name for tag in negative_tags])
        
        # 格式化新闻时间
        news_time = news.ctime.strftime("%H:%M") if news.ctime else "--:--"
        
        # 添加新闻数据（使用title而不是content，移除reason字段）
        formatted_news.append({
            'content': news.title,
            'evaluation': evaluation,
            'sector': sector,
            'time': news_time,
            'news_id': str(news.id),
        })
    
    # 确保至少有2条新闻
    while len(formatted_news) < 2:
        formatted_news.append({
            'content': '暂无相关新闻',
            'evaluation': '-',
            'sector': '-',
            'time': '--:--',
            'news_id': '0',
        })
    
    end_time = time_module.time()
    print(f"港美股新闻处理总耗时: {end_time - start_time:.2f}秒")
    return formatted_news

def get_top_news(session):
    """从数据库获取头条重要新闻并查询关联标签"""
    start_time = time_module.time()
    
    # 查询最新的重要新闻（is_important=1）
    query_start = time_module.time()
    news_list = session.query(News).filter(
        or_(News.code == 'top', News.code == 'cn'),
        News.is_important == 1
    ).order_by(News.ctime.desc()).limit(2).all()
    query_end = time_module.time()
    print(f"头条新闻查询耗时: {query_end - query_start:.2f}秒, 获取{len(news_list)}条记录")
    
    # 获取新闻标签
    formatted_news = []
    for news in news_list:
        # 查询新闻关联的标签
        news_tags = session.query(Tag).join(
            NewsTagRelation, NewsTagRelation.tag_id == Tag.id
        ).filter(
            NewsTagRelation.news_id == news.id
        ).all()
        
        # 将标签按类型分组
        positive_tags = [tag for tag in news_tags if tag.tag_type == 1]
        negative_tags = [tag for tag in news_tags if tag.tag_type == 0]
        
        # 默认评价和影响板块
        evaluation = "中性"
        sector = "暂无影响板块"
        
        # 根据标签类型设置评价，只拼接同类型的标签
        if positive_tags:  # 有利好标签
            evaluation = "利好"
            # 只拼接利好标签
            sector = "，".join([tag.name for tag in positive_tags])
        elif negative_tags:  # 有利空标签但没有利好标签
            evaluation = "利空"
            # 只拼接利空标签
            sector = "，".join([tag.name for tag in negative_tags])
        
        # 格式化新闻时间
        news_time = news.ctime.strftime("%H:%M") if news.ctime else "--:--"
        
        # 添加新闻数据（使用title而不是content，移除reason字段）
        formatted_news.append({
            'content': news.title,
            'evaluation': evaluation,
            'sector': sector,
            'time': news_time,
            'news_id': str(news.id),
        })
    
    # 确保至少有2条新闻
    while len(formatted_news) < 2:
        formatted_news.append({
            'content': '暂无相关新闻',
            'evaluation': '中性',
            'sector': '无',
            'time': '--:--',
            'news_id': '0',
        })
    
    end_time = time_module.time()
    print(f"头条新闻处理总耗时: {end_time - start_time:.2f}秒")
    return formatted_news

def build_message_data(date, top_news, hk_us_news):
    """根据新的模板格式构建消息数据"""
    return {
        "Date": {"value": date, "color": "#173177"},
        
        # 今日头条新闻
        "top_news_1": {"value": top_news[0]['content'], "color": "#173177"},
        "top_news_eva1": {"value": top_news[0]['evaluation'], "color": "#173177"},
        "top_news_sector1": {"value": top_news[0]['sector'], "color": "#173177"},
        "top_news_time1": {"value": top_news[0]['time'], "color": "#173177"},
        "top_news_id1": {"value": top_news[0]['news_id'], "color": "#173177"},
        
        "top_news_2": {"value": top_news[1]['content'], "color": "#173177"},
        "top_news_eva2": {"value": top_news[1]['evaluation'], "color": "#173177"},
        "top_news_sector2": {"value": top_news[1]['sector'], "color": "#173177"},
        "top_news_time2": {"value": top_news[1]['time'], "color": "#173177"},
        "top_news_id2": {"value": top_news[1]['news_id'], "color": "#173177"},
        
        # 港美股夜间新闻
        "hk_news_1": {"value": hk_us_news[0]['content'], "color": "#173177"},
        "hk_news_eva1": {"value": hk_us_news[0]['evaluation'], "color": "#173177"},
        "hk_news_sector1": {"value": hk_us_news[0]['sector'], "color": "#173177"},
        "hk_news_time1": {"value": hk_us_news[0]['time'], "color": "#173177"},
        "hk_news_id1": {"value": hk_us_news[0]['news_id'], "color": "#173177"},
        
        "hk_news_2": {"value": hk_us_news[1]['content'], "color": "#173177"},
        "hk_news_eva2": {"value": hk_us_news[1]['evaluation'], "color": "#173177"},
        "hk_news_sector2": {"value": hk_us_news[1]['sector'], "color": "#173177"},
        "hk_news_time2": {"value": hk_us_news[1]['time'], "color": "#173177"},
        "hk_news_id2": {"value": hk_us_news[1]['news_id'], "color": "#173177"},
    }

def get_user_id_by_openid(session, openid):
    """通过OpenID获取用户ID"""
    user = session.query(User).filter(User.openid == openid).first()
    return user.id if user else None

def send_template_message(openid, data):
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
    
    # 存储推送记录 - 拆分为两个事务
    with get_db_session() as session:
        user_id = get_user_id_by_openid(session, openid)
        if user_id:
            # 直接使用字典对象，不需要json.dumps
            content_data = {
                "date": data["Date"]["value"],
                "top_news": [
                    {
                        "content": data["top_news_1"]["value"],
                        "evaluation": data["top_news_eva1"]["value"],
                        "sector": data["top_news_sector1"]["value"],
                        "time": data["top_news_time1"]["value"],
                        "news_id": data["top_news_id1"]["value"]
                    },
                    {
                        "content": data["top_news_2"]["value"],
                        "evaluation": data["top_news_eva2"]["value"],
                        "sector": data["top_news_sector2"]["value"],
                        "time": data["top_news_time2"]["value"],
                        "news_id": data["top_news_id2"]["value"]
                    }
                ],
                "hk_us_news": [
                    {
                        "content": data["hk_news_1"]["value"],
                        "evaluation": data["hk_news_eva1"]["value"],
                        "sector": data["hk_news_sector1"]["value"],
                        "time": data["hk_news_time1"]["value"],
                        "news_id": data["hk_news_id1"]["value"]
                    },
                    {
                        "content": data["hk_news_2"]["value"],
                        "evaluation": data["hk_news_eva2"]["value"],
                        "sector": data["hk_news_sector2"]["value"],
                        "time": data["hk_news_time2"]["value"],
                        "news_id": data["hk_news_id2"]["value"]
                    }
                ]
            }
            
            # 创建推送记录 - 第一步：添加并提交PushRecord
            push_record = PushRecord(
                msgid=msg_uuid,
                user_id=user_id,
                push_time=datetime.now(),
                content=content_data,  # 直接存储字典对象
                result="success" if result.get("errcode") == 0 else f"failed: {result}"
            )
            session.add(push_record)
            session.commit()  # 先提交，确保PushRecord已创建
            
    # 收集所有实际对应到新闻的ID（排除占位符"0"）
    news_ids = []
    # 收集头条新闻ID
    if data["top_news_id1"]["value"] != "0":
        try:
            news_ids.append(int(data["top_news_id1"]["value"]))
        except (ValueError, TypeError):
            pass
            
    if data["top_news_id2"]["value"] != "0":
        try:
            news_ids.append(int(data["top_news_id2"]["value"]))
        except (ValueError, TypeError):
            pass
            
    # 收集港美股新闻ID
    if data["hk_news_id1"]["value"] != "0":
        try:
            news_ids.append(int(data["hk_news_id1"]["value"]))
        except (ValueError, TypeError):
            pass
            
    if data["hk_news_id2"]["value"] != "0":
        try:
            news_ids.append(int(data["hk_news_id2"]["value"]))
        except (ValueError, TypeError):
            pass

    # 第二步：在新事务中创建关联记录
    if news_ids:
        with get_db_session() as session:
            # 创建关联记录
            for news_id in news_ids:
                # 验证新闻是否存在
                news_exists = session.query(News).filter(News.id == news_id).first() is not None
                if news_exists:
                    relation = PushNewsRelation(
                        msgid=msg_uuid,
                        news_id=news_id,
                        created_at=datetime.now()
                    )
                    session.add(relation)
            # 提交关联记录
            session.commit()
    
    return result

# 构造内容
now = datetime.now()
formatted_datetime = now.strftime("%Y年%m月%d日 %H时%M分")

# 获取开启了早报推送的用户列表
USERS = get_users_with_morning_report_enabled()

# 如果没有开启推送的用户，直接退出
if not USERS:
    print("没有用户开启了早报推送功能，结束执行")
    exit(0)

# 执行推送
for user_openid in USERS:
    with get_db_session() as session:
        user = session.query(User).filter(User.openid == user_openid).first()
        if not user:
            print(f"未找到用户: {user_openid}")
            continue
        
        # 获取数据
        hk_us_news = get_hk_us_news(session)
        top_news = get_top_news(session)
    
    message_data = build_message_data(formatted_datetime.strip(), top_news, hk_us_news)
    send_template_message(user_openid, message_data)
