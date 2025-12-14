from flask import Blueprint, request, jsonify, current_app as app
import logging
import json
import time
import re
from datetime import datetime, timedelta
from flask_jwt_extended import jwt_required
from db.models import db, StockEvaluation, News
from sqlalchemy import or_
from utils.ai_utils import analyze_financial_news
from .news import get_news
from utils.redis_cache import redis_cache, get_cached_data, cache_data

ai_eva_bp = Blueprint('ai_eva', __name__, url_prefix='/api')
logger = logging.getLogger('app')

# 股票交易时间定义
TRADING_START_HOUR = 9
TRADING_END_HOUR = 17

@ai_eva_bp.route('/eva', methods=['GET'])
# @jwt_required()
def evaluate_stock_news():
    """
    根据指定股票代码的近期新闻，评估其利好/利空情况
    参数：
    - code: 股票代码
    - refresh: 可选，是否强制刷新评估结果，默认false
    返回：
    - 评估结果
    """
    start_time = time.time()
    stock_code = request.args.get('code', '').strip()
    if not stock_code:
        logger.debug("[ai/eva] 缺少 code 参数")
        return jsonify({"code": 400, "msg": "缺少 code 参数"}), 400

    refresh = request.args.get('refresh', '').lower() in ('true', '1', 't', 'yes', 'y')

    logger.debug(f"[ai/eva] 请求评估股票 {stock_code}, 强制刷新: {refresh}")

    # 生成缓存键，包含股票代码
    cache_key = f"stock:eva:{stock_code}"
    
    # 如果不是强制刷新，先尝试从缓存获取
    if not refresh:
        cached_result = get_cached_data(cache_key)
        if cached_result is not None:
            logger.debug(f"[ai/eva] 缓存命中: {cache_key}")
            return cached_result

    # 检查是否有近72小时内的评测结果
    if not refresh:
        twelve_hours_ago = datetime.now() - timedelta(hours=72)
        recent_evaluation = StockEvaluation.query.filter(
            StockEvaluation.code == stock_code,
            StockEvaluation.evaluation_time >= twelve_hours_ago
        ).order_by(StockEvaluation.evaluation_time.desc()).first()

        if recent_evaluation:
            logger.debug(f"[ai/eva] 找到近72小时内的评测结果，直接返回")
            # 确保正确解析JSON字符串
            try:
                news_list_data = json.loads(recent_evaluation.news_list) if recent_evaluation.news_list else []
            except json.JSONDecodeError:
                logger.warning(f"[ai/eva] 无法解析news_list: {recent_evaluation.news_list}")
                news_list_data = []
            
            # 构建返回结果
            result = jsonify({
                "code": 0,
                "msg": "success",
                "data": {
                    "conclusion": recent_evaluation.conclusion,
                    "reason": recent_evaluation.reason,
                    "news_list": news_list_data,
                    "evaluation_time": recent_evaluation.evaluation_time.strftime("%Y-%m-%d %H:%M:%S")
                }
            })
            
            # 缓存数据库查询结果，设置3小时过期时间 (10800秒)
            try:
                cache_success = cache_data(cache_key, result.get_json(), expire_seconds=10800)
                if cache_success:
                    logger.debug(f"[ai/eva] 数据库结果已缓存: {cache_key}")
            except Exception as e:
                logger.error(f"[ai/eva] 缓存数据库结果异常: {e}")
                
            return result

    # 调用 get_news 方法触发新闻更新
    logger.debug(f"[ai/eva] 调用 get_news 更新股票 {stock_code} 的新闻")
    try:
        news_response = get_news()
        if news_response.status_code != 200:
            logger.error(f"[ai/eva] 更新新闻失败，返回状态码: {news_response.status_code}")
            return jsonify({"code": 500, "msg": "更新新闻失败"}), 500
    except Exception as e:
        logger.error(f"[ai/eva] 更新新闻异常: {e}", exc_info=True)
        # 即使更新失败也继续，使用现有新闻

    # 获取特定股票新闻
    now = datetime.now()
    
    # 直接获取最新10条新闻
    recent_news = News.query.filter(
        News.code == stock_code
    ).order_by(News.ctime.desc()).limit(10).all()

    if not recent_news:
        logger.debug(f"[ai/eva] 未找到股票 {stock_code} 的相关新闻")
        # 构建返回结果
        result = jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "conclusion": "中性",
                "reason": f"未找到股票 {stock_code} 的相关新闻",
                "news_list": [],
                "evaluation_time": now.strftime("%Y-%m-%d %H:%M:%S")
            }
        })
        
        # 缓存无新闻结果，设置较短的过期时间 (1小时)
        try:
            cache_success = cache_data(cache_key, result.get_json(), expire_seconds=3600)
            if cache_success:
                logger.debug(f"[ai/eva] 无新闻结果已缓存: {cache_key}")
        except Exception as e:
            logger.error(f"[ai/eva] 缓存无新闻结果异常: {e}")
            
        return result
    
    combined_news = ""
    
    # 合并新闻内容，包含新闻链接
    for i, news in enumerate(recent_news, 1):
        # 限制每条新闻的内容长度，防止过长
        content = news.content[:500] + "..." if len(news.content) > 500 else news.content
        news_item = f"【新闻{i}：{news.title}】{content} ({news.link})\n"
        combined_news += news_item

    logger.debug(f"[ai/eva] 准备评估股票 {stock_code} 的新闻内容")
    logger.debug(f"[ai/eva] 处理时间已经: {time.time() - start_time:.2f}秒")

    try:
        # 调用 AI 分析工具进行评估
        result = analyze_financial_news(combined_news)
        conclusion = result.get('conclusion', '未知')
        reason = result.get('reason', '未提供理由')
        raw_news_list = result.get('news_list', [])
        
        # 处理新闻列表，转换为对象格式
        news_list = []
        for news_item in raw_news_list:
            # 提取链接
            link_match = re.search(r'\((http[^)]+)\)', news_item)
            link = link_match.group(1) if link_match else ""
            
            # 提取标题
            title_match = re.search(r'\[(.*?)\]', news_item)
            title = title_match.group(1) if title_match else news_item
            
            # 根据链接查询数据库中的新闻记录获取发布时间
            publish_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if link:
                db_news = News.query.filter_by(link=link).first()
                if db_news:
                    publish_time = db_news.ctime.strftime("%Y-%m-%d %H:%M:%S")
            
            news_list.append({
                "title": title,
                "link": link,
                "publish_time": publish_time
            })
        
        # 存储评估结果到数据库 - 使用ensure_ascii=False确保中文正确编码
        new_evaluation = StockEvaluation(
            code=stock_code,
            evaluation_time=now,
            conclusion=conclusion,
            reason=reason,
            news_list=json.dumps(news_list, ensure_ascii=False)
        )
        db.session.add(new_evaluation)
        db.session.commit()

        logger.debug(f"[ai/eva] 评估完成并存储到数据库，股票代码: {stock_code}，总耗时: {time.time() - start_time:.2f}秒")

        # 构建返回结果
        result = jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "conclusion": conclusion,
                "reason": reason,
                "news_list": news_list,
                "evaluation_time": now.strftime("%Y-%m-%d %H:%M:%S")
            }
        })
        
        # 缓存结果，设置3小时过期时间 (10800秒)
        try:
            cache_success = cache_data(cache_key, result.get_json(), expire_seconds=10800)
            if cache_success:
                logger.debug(f"[ai/eva] 结果已缓存: {cache_key}")
            else:
                logger.warning(f"[ai/eva] 结果缓存失败: {cache_key}")
        except Exception as e:
            logger.error(f"[ai/eva] 缓存操作异常: {e}")
        
        return result
    except Exception as e:
        logger.error(f"[ai/eva] AI分析失败: {e}", exc_info=True)
        
        # 查找最近一次成功的评估作为备用
        fallback = StockEvaluation.query.filter(
            StockEvaluation.code == stock_code
        ).order_by(StockEvaluation.evaluation_time.desc()).first()
        
        if fallback:
            # 确保正确解析存储的JSON字符串
            try:
                fallback_news_list = json.loads(fallback.news_list) if fallback.news_list else []
            except json.JSONDecodeError:
                logger.warning(f"[ai/eva] 无法解析fallback news_list: {fallback.news_list}")
                fallback_news_list = []
                
            logger.debug(f"[ai/eva] 返回最近一次评估结果作为备用")
            # 构建返回结果
            result = jsonify({
                "code": 0,
                "msg": f"本次分析失败，返回历史结果",
                "data": {
                    "conclusion": fallback.conclusion,
                    "reason": fallback.reason,
                    "news_list": fallback_news_list,
                    "evaluation_time": fallback.evaluation_time.strftime("%Y-%m-%d %H:%M:%S"),
                    "is_fallback": True
                }
            })
            
            # 缓存备用结果，设置较短的过期时间 (30分钟)
            try:
                cache_success = cache_data(cache_key, result.get_json(), expire_seconds=1800)
                if cache_success:
                    logger.debug(f"[ai/eva] 备用结果已缓存: {cache_key}")
            except Exception as e:
                logger.error(f"[ai/eva] 缓存备用结果异常: {e}")
                
            return result
        
        return jsonify({
            "code": 500,
            "msg": f"AI分析失败: {str(e)}",
            "data": None
        }), 500
