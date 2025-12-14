from flask import Blueprint, request, jsonify, current_app as app
import logging
from datetime import datetime, timedelta
from db.models import db, News, Tag, NewsTagRelation, StockTagRelation, NewsSummary
from sqlalchemy import func, select
from utils.ai_utils import get_tag_leaders as fetch_tag_leaders
from utils.redis_cache import redis_cache

tags_bp = Blueprint('tags', __name__, url_prefix='/api/tags')
logger = logging.getLogger('app')

@tags_bp.route('/', methods=['GET'])
def get_all_tags():
    """获取所有使用过的标签列表，分利好和利空两类"""
    try:
        # 查询所有正面标签
        positive_tags = db.session.query(Tag.name).filter(Tag.tag_type == 1).all()
        
        # 查询所有负面标签
        negative_tags = db.session.query(Tag.name).filter(Tag.tag_type == 0).all()
        
        # 处理结果
        all_positive_tags = [tag[0] for tag in positive_tags]
        all_negative_tags = [tag[0] for tag in negative_tags]
        
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "positive_tags": all_positive_tags,
                "negative_tags": all_negative_tags
            }
        })
    except Exception as e:
        logger.error(f"获取标签列表失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": f"获取标签列表失败: {str(e)}"}), 500

@tags_bp.route('/news', methods=['GET'])
def get_tagged_news():
    """根据标签获取相关新闻"""
    tag_name = request.args.get('tag')
    tag_type = request.args.get('type', 'positive')  # 默认查询正面标签
    days = int(request.args.get('days', 7))  # 默认查询7天内的新闻
    
    if not tag_name:
        return jsonify({"code": 400, "msg": "请提供标签参数"}), 400
    
    try:
        # 设置时间范围
        start_date = datetime.now() - timedelta(days=days)
        
        # 确定标签类型
        tag_type_value = 1 if tag_type == 'positive' else 0
        
        # 查找标签ID
        tag = Tag.query.filter_by(name=tag_name, tag_type=tag_type_value).first()
        if not tag:
            return jsonify({"code": 404, "msg": f"标签 '{tag_name}' 不存在"}), 404
        
        # 查询包含指定标签的新闻
        news_with_tag = db.session.query(News)\
            .join(NewsTagRelation, News.id == NewsTagRelation.news_id)\
            .filter(NewsTagRelation.tag_id == tag.id)\
            .filter(News.ctime >= start_date)\
            .order_by(News.ctime.desc()).all()
        
        result = []
        for news in news_with_tag:
            # 获取新闻关联的所有标签
            positive_tags_query = db.session.query(Tag.name)\
                .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
                .filter(NewsTagRelation.news_id == news.id)\
                .filter(Tag.tag_type == 1).all()
            
            negative_tags_query = db.session.query(Tag.name)\
                .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
                .filter(NewsTagRelation.news_id == news.id)\
                .filter(Tag.tag_type == 0).all()
            
            positive_tags = [tag[0] for tag in positive_tags_query]
            negative_tags = [tag[0] for tag in negative_tags_query]
            
            result.append({
                "id": news.id,
                "title": news.title,
                "content": news.content,
                "code": news.code,
                "link": news.link,
                "publish_time": news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
                "positive_tags": positive_tags,
                "negative_tags": negative_tags,
                "is_important": news.is_important == 1
            })
        
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": result
        })
    except Exception as e:
        logger.error(f"获取标签新闻失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": f"获取标签新闻失败: {str(e)}"}), 500

@tags_bp.route('/important', methods=['GET'])
def get_important_news():
    """获取标记为重要的新闻"""
    days = int(request.args.get('days', 7))  # 默认查询7天内的新闻
    
    try:
        # 设置时间范围
        start_date = datetime.now() - timedelta(days=days)
        
        # 查询重要新闻 (is_important = 1)
        important_news = db.session.query(News)\
            .filter(News.is_important == 1)\
            .filter(News.ctime >= start_date)\
            .order_by(News.ctime.desc()).all()
        
        result = []
        for news in important_news:
            # 获取新闻关联的所有标签
            positive_tags_query = db.session.query(Tag.name)\
                .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
                .filter(NewsTagRelation.news_id == news.id)\
                .filter(Tag.tag_type == 1).all()
            
            negative_tags_query = db.session.query(Tag.name)\
                .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
                .filter(NewsTagRelation.news_id == news.id)\
                .filter(Tag.tag_type == 0).all()
            
            positive_tags = [tag[0] for tag in positive_tags_query]
            negative_tags = [tag[0] for tag in negative_tags_query]
            
            # 获取新闻摘要
            summary = ""
            summary_obj = db.session.query(NewsSummary).filter_by(news_id=news.id).first()
            if summary_obj and summary_obj.summary:
                summary = summary_obj.summary
            
            result.append({
                "id": news.id,
                "title": news.title,
                "content": news.content,
                "code": news.code,
                "link": news.link,
                "publish_time": news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
                "positive_tags": positive_tags,
                "negative_tags": negative_tags,
                "summary": summary
            })
        
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": result
        })
    except Exception as e:
        logger.error(f"获取重要新闻失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": f"获取重要新闻失败: {str(e)}"}), 500

@tags_bp.route('/stats', methods=['GET'])
def get_tags_stats():
    """获取标签统计信息"""
    days = int(request.args.get('days', 30))  # 默认统计30天内的标签
    
    try:
        # 设置时间范围
        start_date = datetime.now() - timedelta(days=days)
        
        # 查询在时间范围内的新闻ID - 使用select()而不是子查询
        recent_news_ids = select(News.id).where(News.ctime >= start_date)
        
        # 统计正面标签
        positive_tag_counts = db.session.query(
                Tag.name, 
                func.count(NewsTagRelation.news_id).label('count')
            )\
            .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
            .filter(Tag.tag_type == 1)\
            .filter(NewsTagRelation.news_id.in_(recent_news_ids))\
            .group_by(Tag.name)\
            .order_by(func.count(NewsTagRelation.news_id).desc())\
            .limit(10).all()
            
        # 统计负面标签
        negative_tag_counts = db.session.query(
                Tag.name, 
                func.count(NewsTagRelation.news_id).label('count')
            )\
            .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
            .filter(Tag.tag_type == 0)\
            .filter(NewsTagRelation.news_id.in_(recent_news_ids))\
            .group_by(Tag.name)\
            .order_by(func.count(NewsTagRelation.news_id).desc())\
            .limit(10).all()
            
        # 计算重要新闻数量
        important_count = db.session.query(func.count(News.id))\
            .filter(News.is_important == 1)\
            .filter(News.ctime >= start_date)\
            .scalar() or 0
        
        # 计算总新闻数
        total_count = db.session.query(func.count(News.id))\
            .filter(News.ctime >= start_date)\
            .scalar() or 0
            
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "top_positive_tags": [{"tag": tag, "count": count} for tag, count in positive_tag_counts],
                "top_negative_tags": [{"tag": tag, "count": count} for tag, count in negative_tag_counts],
                "important_count": important_count,
                "total_count": total_count
            }
        })
    except Exception as e:
        logger.error(f"获取标签统计失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": f"获取标签统计失败: {str(e)}"}), 500

@tags_bp.route('/leaders', methods=['GET'])
# @redis_cache("tags:leaders", expire_seconds=3600)
def get_tag_leaders():
    """根据标签获取相关龙头股票"""
    tag_name = request.args.get('tag')
    refresh = request.args.get('refresh', 'false').lower() == 'true'  # 添加强制刷新参数
    
    if not tag_name:
        return jsonify({"code": 400, "msg": "请提供标签参数"}), 400
    
    try:
        logger.info(f"开始处理标签 '{tag_name}' 的龙头股票查询，强制刷新: {refresh}")
        
        # 先查找标签是否存在
        tag = db.session.query(Tag).filter_by(name=tag_name).first()
        
        # 如果标签不存在，返回错误
        if not tag:
            logger.warning(f"标签 '{tag_name}' 在数据库中不存在")
            return jsonify({"code": 404, "msg": f"标签 '{tag_name}' 不存在"}), 404
        
        verified_leaders = []
        description = ""
        
        # 先查询数据库中的关联股票，无论是否强制刷新
        from db.models import Stocks, StockInfo, StockRealtimeQuote, StockTagRelation
        
        db_leaders = db.session.query(
            Stocks.code, 
            Stocks.name, 
            Stocks.market,
            StockInfo.industry,
            StockRealtimeQuote.latest_price,
            StockRealtimeQuote.change_percent,
            StockTagRelation.reason  # 添加 reason 字段到查询
        ).join(
            StockTagRelation, Stocks.code == StockTagRelation.code
        ).join(
            StockInfo, Stocks.code == StockInfo.code, isouter=True
        ).join(
            StockRealtimeQuote, Stocks.code == StockRealtimeQuote.code, isouter=True
        ).filter(
            StockTagRelation.tag_id == tag.id
        ).all()
        
        # 只有当不是强制刷新且数据库中有足够的关联股票时，才直接返回数据库数据
        if not refresh and len(db_leaders) >= 1:
            logger.info(f"从数据库中找到标签 '{tag_name}' 的 {len(db_leaders)} 只关联股票")
            
            for stock in db_leaders:
                verified_leaders.append({
                    'code': stock.code,
                    'name': stock.name,
                    'market': stock.market,
                    'industry': stock.industry,
                    'latest_price': stock.latest_price,
                    'change_percent': stock.change_percent,
                    'reason': stock.reason or f"与{tag_name}主题相关的股票"  # 使用数据库中的reason，如果为空则使用默认值
                })
            
            return jsonify({
                "code": 0,
                "msg": "success",
                "data": {
                    "leaders": verified_leaders,
                    "description": f"{tag_name}概念股票"
                }
            })
        
        # 以下情况会调用API：1.强制刷新 2.数据库中没有足够信息
        if refresh:
            logger.info(f"强制刷新模式：将调用API获取最新的龙头股票数据")
        else:
            logger.info(f"数据库中关联股票不足，将调用API获取数据")
            
        # 调用AI工具获取股票
        logger.debug(f"准备调用 fetch_tag_leaders 函数获取标签 '{tag_name}' 的龙头股票")
        result = fetch_tag_leaders(tag_name)
        logger.info(f"成功获取标签 '{tag_name}' 的龙头股票，找到 {len(result.get('leaders', []))} 只股票")
        description = result.get("description", "")
        
        # 提取所有股票名称，用于查询股票代码
        stock_names = []
        for item in result.get('leaders', []):
            if 'name' in item:
                stock_names.append(item['name'])
        
        logger.debug(f"需要查询的股票名称: {stock_names}")
        
        if not stock_names:
            logger.warning(f"未找到标签 '{tag_name}' 的有效龙头股票名称")
            return jsonify({
                "code": 0,
                "msg": "success",
                "data": {"leaders": [], "description": description}
            })
            
        # 使用股票名称查询数据库获取股票代码和其他信息
        from db.models import Stocks, StockInfo, StockRealtimeQuote
        from sqlalchemy import func  # 添加这行导入func
        
        valid_stocks = db.session.query(
            Stocks.code, 
            Stocks.name, 
            Stocks.market,
            StockInfo.industry,
            StockRealtimeQuote.latest_price,
            StockRealtimeQuote.change_percent
        ).join(
            StockInfo, Stocks.code == StockInfo.code, isouter=True
        ).join(
            StockRealtimeQuote, Stocks.code == StockRealtimeQuote.code, isouter=True
        ).filter(
            Stocks.name.in_(stock_names),
            func.length(Stocks.code) == 6  # 确保股票代码是6位
        ).all()
        
        logger.debug(f"数据库中找到 {len(valid_stocks)} 只有效股票")
        
        # 创建名称到信息的映射（使用名称作为键）
        stock_info_map = {stock.name: stock for stock in valid_stocks}
        
        # 如果强制刷新，先删除旧的关系
        if refresh:
            logger.info(f"强制刷新模式，删除标签 '{tag_name}' 的现有关联关系")
            db.session.query(StockTagRelation).filter_by(tag_id=tag.id).delete()
        
        # 更新结果并保存到数据库
        for leader in result.get('leaders', []):
            stock_name = leader.get('name', '')
            
            if stock_name in stock_info_map:
                stock_info = stock_info_map[stock_name]
                code = stock_info.code
                verified_leader = {
                    'code': code,
                    'name': stock_name,
                    'market': stock_info.market,
                    'industry': stock_info.industry,
                    'latest_price': stock_info.latest_price,
                    'change_percent': stock_info.change_percent,
                    'reason': leader.get('reason', '')
                }
                verified_leaders.append(verified_leader)
                
                # 将股票与标签的关系保存到数据库
                # 检查该关系是否已存在
                relation = db.session.query(StockTagRelation).filter_by(
                    code=code, tag_id=tag.id
                ).first()
                
                if not relation:
                    relation = StockTagRelation(
                        code=code,
                        tag_id=tag.id,
                        created_at=datetime.now(),
                        reason=leader.get('reason', '')
                    )
                    db.session.add(relation)
                    logger.debug(f"添加标签 '{tag_name}' 与股票 {code} 的关联关系")
                elif refresh:  # 如果是强制刷新模式，则更新原因
                    relation.reason = leader.get('reason', '')
                    logger.debug(f"更新标签 '{tag_name}' 与股票 {code} 的关联原因")
        
        # 提交所有数据库变更
        db.session.commit()
        logger.info(f"成功验证标签 '{tag_name}' 的龙头股票，最终数量: {len(verified_leaders)}，已保存到数据库")
        
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "leaders": verified_leaders,
                "description": description
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"获取标签龙头股票失败: {e}", exc_info=True)
        return jsonify({"code": 500, "msg": f"获取标签龙头股票失败: {str(e)}"}), 500

