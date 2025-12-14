import hashlib
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app as app
import akshare as ak
import pandas as pd
from db.models import db, News, Stocks, NewsTagRelation, Tag, NewsSummary
from semhash import SemHash
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from sqlalchemy import func, and_, text, or_
from utils.redis_cache import redis_cache, get_cached_data, cache_data, clear_cache_pattern

news_bp = Blueprint('news', __name__, url_prefix='/api')
logger = logging.getLogger('app')

@news_bp.route('/news/get', methods=['GET'])
def get_news():
    stock_code = request.args.get('code', '').strip()
    if not stock_code:
        return jsonify({"error": "缺少 code 参数"}), 400

    logger.debug(f"[news/get] 请求 code={stock_code}")

    # 分页参数
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(int(request.args.get('limit', 20)), 100))
    except ValueError:
        return jsonify({"error": "分页参数格式错误"}), 400

    # 新增强制刷新参数，默认为不强制刷新
    refresh = request.args.get('refresh', '0') == '1'

    # 生成缓存键，包含股票代码和分页参数
    cache_key = f"stock:news:{stock_code}:page:{page}:limit:{limit}"
    
    # 如果不是强制刷新，先尝试从缓存获取
    if not refresh:
        cached_result = get_cached_data(cache_key)
        if cached_result is not None:
            logger.debug(f"[news/get] 缓存命中: {cache_key}")
            return cached_result

    logger.debug(f"[news/get] 缓存未命中或强制刷新，查询数据库: {cache_key}")

    # 获取股票简称
    stock_name = None
    try:
        stock = db.session.query(Stocks).filter_by(code=stock_code).first()
        if stock:
            stock_name = stock.name
    except Exception as e:
        logger.error(f"[news/get] 获取股票简称失败: {e}", exc_info=True)
        stock_name = None

    # 查询数据库中的新闻 - 正确引用 tags_relation
    query = News.query.filter(News.code == stock_code).order_by(News.ctime.desc())
    total = query.count()
    news_list = query.offset((page - 1) * limit).limit(limit).all()

    # 特殊处理：如果code是cn或者hk_us，或者有分页参数(page > 1)，不触发更新，直接返回数据库数据
    if stock_code in ['cn', 'hk_us','top'] or page > 1:
        if page > 1:
            logger.debug(f"[news/get] 分页请求 page={page}，不触发新闻更新，直接返回数据库数据")
        else:
            logger.debug(f"[news/get] code为 {stock_code}，不触发新闻更新，直接返回数据库数据")
    else:
        # 如果新闻为空或下载时间超过1小时，或强制刷新，触发更新
        now = datetime.now()
        if refresh or not news_list or (news_list and (now - news_list[0].download_time).total_seconds() > 3600):
            logger.debug(f"[news/get] 触发新闻更新，stock_code={stock_code}，refresh={refresh}")
            try:
                if not stock_name:
                    logger.debug(f"[news/get] 股票简称未找到，使用股票代码作为名称")
                    stock_name = stock_code
                logger.debug(f"[news/get] akshare 拉取股票新闻，stock_name={stock_name}")
                # 使用 akshare 拉取最新新闻
                df = ak.stock_news_em(symbol=stock_name)
                if df is not None and not df.empty:
                    # 过滤新闻，确保包含股票名称或股票代码
                    filtered_df = df[df["新闻标题"].str.contains(stock_name) | 
                                    df["新闻内容"].str.contains(stock_name) |
                                    df["新闻标题"].str.contains(stock_code) | 
                                    df["新闻内容"].str.contains(stock_code)]
                    
                    logger.debug(f"[news/get] 原始新闻数量: {len(df)}，过滤后数量: {len(filtered_df)}")
                    
                    # 如果过滤后有新闻，则使用SemHash去重后更新到数据库
                    if not filtered_df.empty:
                        try:
                            # 将DataFrame转换为记录列表
                            news_records = filtered_df.to_dict('records')
                            
                            # 添加检查：确保记录不为空
                            if news_records:
                                logger.debug(f"[news/get] 新闻记录数量: {len(news_records)}")
                                
                                # 记录新闻记录的一些示例数据，帮助调试
                                logger.debug(f"[news/get] 新闻记录示例: {news_records[0].keys()}")
                                
                                # 检查是否所有记录都有必要的列
                                for i, record in enumerate(news_records):
                                    if "新闻标题" not in record or "新闻内容" not in record:
                                        logger.warning(f"[news/get] 记录 {i} 缺少必要列: {record.keys()}")
                                
                                # 确保所有记录都有所需的列
                                valid_records = [r for r in news_records if "新闻标题" in r and "新闻内容" in r]
                                if len(valid_records) != len(news_records):
                                    logger.warning(f"[news/get] 过滤掉了 {len(news_records) - len(valid_records)} 条缺少必要列的记录")
                                    news_records = valid_records
                                
                                if news_records:  # 再次检查，确保过滤后还有记录
                                    logger.debug(f"[news/get] 开始创建SemHash实例，有效记录数: {len(news_records)}")
                                    
                                    semhash = SemHash.from_records(records=news_records, columns=["新闻标题", "新闻内容"], use_ann=False)
                                    
                                    logger.debug(f"[news/get] SemHash实例创建成功，开始执行去重操作")
                                    # 执行去重操作，失败则直接返回空结果，不再重试
                                    try:
                                        logger.debug(f"[news/get] 执行SemHash去重操作")
                                        dedup_result = semhash.self_deduplicate(threshold=0.8)
                                    except Exception as e:
                                        logger.error(f"[news/get] SemHash去重失败: {str(e)}，直接返回空结果")
                                        dedup_result = None
                                    
                                    if dedup_result is not None:
                                        deduplicated_news = dedup_result.selected
                                        logger.debug(f"[news/get] SemHash去重后新闻数量: {len(deduplicated_news)}")
                                        # 检测重复项信息
                                        duplicates = dedup_result.duplicates
                                        if duplicates:
                                            logger.debug(f"[news/get] 发现并去除了 {len(duplicates)} 条重复新闻")
                                        # 将去重后的数据转回DataFrame
                                        import pandas as pd
                                        if deduplicated_news:
                                            # 确保所有记录都有必要的列
                                            required_columns = ["新闻标题", "新闻内容"]
                                            for record in deduplicated_news:
                                                for col in required_columns:
                                                    if col not in record:
                                                        record[col] = ""
                                            # 使用去重后的数据更新数据库
                                            deduplicated_df = pd.DataFrame(deduplicated_news)
                                            _update_news_in_db(stock_code, deduplicated_df)
                                            # 清除该股票的所有新闻缓存
                                            _clear_stock_news_cache(stock_code)
                                        else:
                                            logger.debug(f"[news/get] 去重后新闻为空，不更新数据库")
                                    else:
                                        logger.debug(f"[news/get] SemHash去重失败，未更新数据库")
                            else:
                                logger.debug(f"[news/get] 新闻记录为空，不进行去重处理")
                        except Exception as e:
                            logger.error(f"[news/get] 新闻处理失败: {e}", exc_info=True)
                            # 确保事务回滚
                            db.session.rollback()
                    else:
                        logger.debug(f"[news/get] 过滤后新闻为空，不更新数据库")
            except Exception as e:
                logger.error(f"[news/get] akshare 拉取失败: {e}", exc_info=True)

            # 重新查询数据库获取最新数据
            query = News.query.filter(News.code == stock_code).order_by(News.ctime.desc())
            total = query.count()
            news_list = query.offset((page - 1) * limit).limit(limit).all()

    # 构建返回数据
    news_data = []
    for news in news_list:
        # 构建标签数据
        tag = {
            "positive": [],
            "negative": []
        }
        
        # 通过关联查询获取标签信息
        positive_tags_query = db.session.query(Tag.name)\
            .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
            .filter(NewsTagRelation.news_id == news.id)\
            .filter(Tag.tag_type == 1).all()
        
        negative_tags_query = db.session.query(Tag.name)\
            .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
            .filter(NewsTagRelation.news_id == news.id)\
            .filter(Tag.tag_type == 0).all()
        
        tag["positive"] = [t[0] for t in positive_tags_query]
        tag["negative"] = [t[0] for t in negative_tags_query]
        
        # 获取摘要 - 优先使用 NewsSummary 表中的摘要
        content = news.content[:100] + "..." if len(news.content) > 100 else news.content
        
        # 查询新闻摘要
        summary_obj = NewsSummary.query.filter_by(news_id=news.id).first()
        if summary_obj:
            content = summary_obj.summary
        
        news_data.append({
            "id": news.id,
            "title": news.title,
            "content": content,
            "publish_time": news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
            "source": news.link,
            "url": news.link,
            "tag": tag
        })

    total_pages = (total + limit - 1) // limit
    logger.debug(f"[news/get] 返回 page={page}, limit={limit}, total={total}")

    # 构建返回结果
    result = jsonify({
        "code": 0,
        "msg": "success",
        "data": {
            "news": news_data,
            "pagination": {
                "page": page,
                "limit": limit,
                "total": total,
                "total_pages": total_pages,
                "has_more": page < total_pages
            }
        }
    })

    # 缓存结果，设置1小时过期时间
    try:
        cache_success = cache_data(cache_key, result.get_json(), expire_seconds=3600)
        if cache_success:
            logger.debug(f"[news/get] 结果已缓存: {cache_key}")
        else:
            logger.warning(f"[news/get] 结果缓存失败: {cache_key}")
    except Exception as e:
        logger.error(f"[news/get] 缓存操作异常: {e}")

    return result

def _clear_stock_news_cache(stock_code):
    """
    清除指定股票的所有新闻缓存
    
    Args:
        stock_code: 股票代码
    """
    try:
        # 清除该股票所有分页的缓存
        pattern = f"stock:news:{stock_code}:*"
        cleared_count = clear_cache_pattern(pattern)
        logger.debug(f"[cache] 已清除股票 {stock_code} 的 {cleared_count} 个新闻缓存")
    except Exception as e:
        logger.error(f"[cache] 清除股票 {stock_code} 缓存失败: {e}")

def _update_news_in_db(stock_code, df):
    """
    更新数据库中的新闻数据
    """
    logger.debug(f"[news/update] 开始更新新闻，stock_code={stock_code}")
    now = datetime.now()  # 获取当前时间作为下载时间
    
    added_count = 0
    skipped_count = 0
    duplicate_count = 0
    
    # 使用no_autoflush避免自动刷新导致的问题
    with db.session.no_autoflush:
        for _, row in df.iterrows():
            try:
                title = row.get("新闻标题", "").strip()
                content = row.get("新闻内容", "").strip()
                tstr = row.get("发布时间", "").strip()
                source = row.get("文章来源", "").strip()
                url = row.get("新闻链接", "").strip()

                if not (title and content and tstr and len(content) >= 20):
                    logger.debug("[news/update] 跳过无效或过短新闻")
                    skipped_count += 1
                    continue

                # 解析发布时间
                try:
                    t = tstr.replace("年", "-").replace("月", "-").replace("日", " ")
                    if len(t) == 10:
                        t += " 00:00:00"
                    publish_time = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
                except Exception:
                    publish_time = datetime.now()

                # 计算内容哈希值，用于去重
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

                # 检查是否已存在
                existing_news = News.query.filter_by(content_hash=content_hash).first()
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


@news_bp.route('/news/detail', methods=['GET'])
def get_news_detail():
    """
    获取单条新闻详情：
    - 从 query 参数获取 id
    - 从数据库中读取原始 JSON
    - 返回标准化的 JSON 结构
    """
    news_id = request.args.get('id', '').strip()
    if not news_id:
        app.logger.debug("[news/detail] 缺少参数 id")
        return jsonify({'code': 400, 'msg': '缺少必要参数 id'}), 400

    # 生成缓存键
    cache_key = f"news:detail:{news_id}"
    
    # 先尝试从缓存获取
    cached_result = get_cached_data(cache_key)
    if cached_result is not None:
        app.logger.debug(f"[news/detail] 缓存命中: {cache_key}")
        return cached_result

    app.logger.debug(f"[news/detail] 查询数据库 news_id={news_id}")
    try:
        news = News.query.filter(News.id == news_id).first()
    except Exception as e:
        app.logger.error(f"[news/detail] 数据库查询错误: {e}", exc_info=True)
        return jsonify({'code': 500, 'msg': '数据库服务错误'}), 500

    if not news:
        app.logger.warning(f"[news/detail] 未找到 news_id={news_id}")
        return jsonify({'code': 404, 'msg': '新闻不存在'}), 404

    # 构建标签数据
    tag = {
        "positive": [],
        "negative": []
    }
    
    # 通过关联查询获取标签信息
    positive_tags_query = db.session.query(Tag.name)\
        .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
        .filter(NewsTagRelation.news_id == news.id)\
        .filter(Tag.tag_type == 1).all()
    
    negative_tags_query = db.session.query(Tag.name)\
        .join(NewsTagRelation, Tag.id == NewsTagRelation.tag_id)\
        .filter(NewsTagRelation.news_id == news.id)\
        .filter(Tag.tag_type == 0).all()
    
    tag["positive"] = [t[0] for t in positive_tags_query]
    tag["negative"] = [t[0] for t in negative_tags_query]
    
    # 查找摘要
    summary = None
    summary_obj = NewsSummary.query.filter_by(news_id=news.id).first()
    if summary_obj:
        summary = summary_obj.summary

    # 构建返回数据
    detail = {
        'id':           news.id,
        'title':        news.title,
        'content':      news.content,
        'summary':      summary,
        'publish_time': news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
        'url':          news.link,
        'tag':          tag
    }
    
    # 构建返回结果
    result = jsonify({'code': 0, 'msg': 'success', 'data': detail})
    
    # 缓存结果，设置30分钟过期时间 (1800秒)
    try:
        cache_success = cache_data(cache_key, result.get_json(), expire_seconds=1800)
        if cache_success:
            app.logger.debug(f"[news/detail] 结果已缓存: {cache_key}")
        else:
            app.logger.warning(f"[news/detail] 结果缓存失败: {cache_key}")
    except Exception as e:
        app.logger.error(f"[news/detail] 缓存操作异常: {e}")
    
    app.logger.debug(f"[news/detail] 成功返回 news_id={news_id}")
    return result

@news_bp.route('/news/pushnews', methods=['GET'])
@jwt_required()
def get_push_news():
    """
    获取推送新闻列表 - 返回给用户推送过的新闻
    - 支持分页参数 page 和 limit
    """
    # 获取当前登录用户ID
    user_id = get_jwt_identity()

    if not user_id:
        logger.debug("[news/pushnews] 未提供用户ID")
        return jsonify({
            "code": 400,
            "msg": "缺少用户ID参数",
            "data": {
                "news": [],
                "pagination": {
                    "page": 1,
                    "limit": 20,
                    "total": 0,
                    "total_pages": 0,
                    "has_more": False
                }
            }
        }), 400

    # 解析分页参数
    try:
        page = max(1, int(request.args.get('page', 1)))
        limit = max(1, min(int(request.args.get('limit', 20)), 100))
    except ValueError:
        return jsonify({"code": 400, "msg": "分页参数格式错误"}), 400
    
    try:
        # 查询用户相关的推送记录
        from db.models import PushRecord, PushNewsRelation, News, NewsSummary
        from sqlalchemy import desc, func, and_, text
        
        # 查询该用户的所有推送消息ID
        push_messages = db.session.query(PushRecord.msgid, PushRecord.content, PushRecord.push_time)\
            .filter(PushRecord.user_id == user_id)\
            .order_by(desc(PushRecord.push_time))\
            .all()
            
        if not push_messages:
            logger.debug(f"[news/pushnews] 用户ID={user_id}没有推送记录")
            return jsonify({
                "code": 0,
                "msg": "success",
                "data": {
                    "news": [],
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": 0,
                        "total_pages": 0,
                        "has_more": False
                    }
                }
            })
        
        # 创建msgid到content的映射
        msgid_to_content = {msg.msgid: msg.content for msg in push_messages}
        msgid_to_pushtime = {msg.msgid: msg.push_time for msg in push_messages}
        
        # 获取这些消息相关的新闻ID
        news_relations = db.session.query(PushNewsRelation.msgid, PushNewsRelation.news_id)\
            .filter(PushNewsRelation.msgid.in_([msg.msgid for msg in push_messages]))\
            .all()
            
        if not news_relations:
            logger.debug(f"[news/pushnews] 没有找到与用户推送记录关联的新闻")
            return jsonify({
                "code": 0,
                "msg": "success",
                "data": {
                    "news": [],
                    "pagination": {
                        "page": page,
                        "limit": limit,
                        "total": 0,
                        "total_pages": 0,
                        "has_more": False
                    }
                }
            })
        
        # 创建news_id到msgid的映射
        news_id_to_msgid = {rel.news_id: rel.msgid for rel in news_relations}
        
        # 获取新闻IDs列表
        news_ids = [rel.news_id for rel in news_relations]
        
        # 获取所有相关新闻
        all_news = db.session.query(News)\
            .filter(News.id.in_(news_ids))\
            .all()
        
        # 过滤出6位代码的新闻
        filtered_news = [
            news for news in all_news 
            if news.code and len(news.code) == 6 and news.code.isdigit()
        ]
        
        # 创建新闻ID到新闻对象的映射
        news_id_to_news = {news.id: news for news in filtered_news}
        
        # 按照推送时间排序新闻ID，只保留6位数字code的新闻
        sorted_news_ids = []
        for rel in sorted(news_relations, key=lambda x: msgid_to_pushtime.get(x.msgid, datetime.min), reverse=True):
            if rel.news_id in news_id_to_news:
                sorted_news_ids.append(rel.news_id)
        
        logger.debug(f"[news/pushnews] 筛选前新闻数量: {len(all_news)}, 筛选后(6位数字code): {len(sorted_news_ids)}")
        
        # 获取总数并分页
        total = len(sorted_news_ids)
        paginated_news_ids = sorted_news_ids[(page-1)*limit:page*limit]
        
        # 查询这些新闻的摘要
        news_summaries = db.session.query(NewsSummary)\
            .filter(NewsSummary.news_id.in_(paginated_news_ids))\
            .all()
            
        # 创建news_id到summary的映射
        news_id_to_summary = {summary.news_id: summary.summary for summary in news_summaries}
        
        # 只保留分页后的新闻项
        paginated_news_items = [news_id_to_news[news_id] for news_id in paginated_news_ids]
        
        # 构建新闻数据
        news_data = []
        for news in paginated_news_items:
            # 获取对应的msgid和推送内容
            msgid = news_id_to_msgid.get(news.id)
            push_content = msgid_to_content.get(msgid, {})
            push_time = msgid_to_pushtime.get(msgid)
            
            # 从推送内容中提取标签信息
            tag = {"positive": [], "negative": []}
            try:
                if isinstance(push_content, dict) and 'ai_eva' in push_content:
                    if push_content['ai_eva'] == '重大利好':
                        tag["positive"] = [push_content['stock_name']]
                    elif push_content['ai_eva'] == '重大利空':
                        tag["negative"] = [push_content['stock_name']]
            except Exception as e:
                logger.error(f"[news/pushnews] 解析推送内容标签失败: {e}")
            
            # 获取摘要
            content = news.content[:100] + "..." if len(news.content) > 100 else news.content
            if news.id in news_id_to_summary:
                content = news_id_to_summary[news.id]
            
            # 添加新闻项
            news_data.append({
                "id": news.id,
                "title": news.title,
                "content": content,
                "publish_time": news.ctime.strftime("%Y-%m-%d %H:%M:%S"),
                "push_time": push_time.strftime("%Y-%m-%d %H:%M:%S") if push_time else None,
                "source": news.link,
                "url": news.link,
                "code": news.code,
                "tag": tag
            })
        
        # 新闻已经按推送时间排序，无需再次排序
        
        # 计算总页数
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        
        logger.debug(f"[news/pushnews] 用户ID={user_id} 返回新闻数量: {len(news_data)}, 总数: {total}, page={page}, limit={limit}")
        
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "news": news_data,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total,
                    "total_pages": total_pages,
                    "has_more": page < total_pages
                }
            }
        })
    
    except Exception as e:
        logger.error(f"[news/pushnews] 获取推送新闻失败: {e}", exc_info=True)
        return jsonify({
            "code": 500, 
            "msg": f"服务器错误: {str(e)}",
            "data": {
                "news": [],
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": 0,
                    "total_pages": 0,
                    "has_more": False
                }
            }
        }), 500
