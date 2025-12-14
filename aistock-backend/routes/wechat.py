from flask import Blueprint, request, jsonify, abort
from db.models import PushRecord, News, SessionLocal, UserPushConfig, PushNewsRelation, Stocks
from utils.push_helpers import PUSH_TYPE_STOCK, PUSH_TYPE_MORNING

# 创建蓝图
wechat_bp = Blueprint('wechat', __name__, url_prefix='/api')

@wechat_bp.route('/wechat', methods=['GET'])
def get_push_details():
    """获取微信推送详情"""
    msgid = request.args.get('msgid')
    if not msgid:
        return jsonify({"error": "缺少必要的msgid参数"}), 400

    session = SessionLocal()
    try:
        # 查找推送记录
        push_record = session.query(PushRecord).filter_by(msgid=msgid).first()
        if not push_record:
            return jsonify({"error": "未找到该推送记录"}), 404

        # 内容现在是JSON类型，直接使用而无需解析
        content = push_record.content

        # 检查是否为普通新闻推送（没有top_news或hk_us_news字段）
        if "top_news" not in content and "hk_us_news" not in content:
            # 处理普通新闻推送
            # 根据msgid查找PushNewsRelation获取新闻ID
            push_news_relation = session.query(PushNewsRelation).filter_by(msgid=msgid).first()
            if not push_news_relation:
                return jsonify({"error": "未找到相关新闻记录"}), 404

            # 根据新闻ID查找新闻详情
            news = session.query(News).filter_by(id=push_news_relation.news_id).first()
            if not news:
                return jsonify({"error": "未找到新闻详情"}), 404

            # 根据stock_name查找股票代码
            stock_name = content.get("stock_name", "")
            stock = None
            if stock_name:
                stock = (
                    session.query(Stocks)
                    .filter_by(name=stock_name)
                    .filter(Stocks.code.op("regexp")("^[0-9]{6}$"))  # MySQL
                    .first()
                )
            # 组装返回格式
            result = {
                "date": content.get("date", ""),
                "content": news.content,
                "evaluation": content.get("ai_eva", ""),
                "id": news.id,
                "link": news.link,
                "published_at": news.ctime.strftime("%Y-%m-%d %H:%M:%S") if news.ctime else "",
                "reason": content.get("ai_sum", ""),
                "stock_name": stock_name,
                "stock_id": stock.code if stock else "",
                "title": content.get("news_title", "")
            }

            return jsonify(result)

        # 收集所有新闻ID（只处理top_news和hk_us_news）
        news_ids = []
        if "top_news" in content:
            for news in content["top_news"]:
                if "news_id" in news:
                    news_ids.append(news["news_id"])

        if "hk_us_news" in content:
            for news in content["hk_us_news"]:
                if "news_id" in news:
                    news_ids.append(news["news_id"])

        # 查询所有相关新闻详情
        news_map = {}
        if news_ids:
            news_items = session.query(News).filter(News.id.in_(news_ids)).all()
            for news in news_items:
                news_map[str(news.id)] = {
                    "id": news.id,
                    "full_content": news.content,
                    "link": news.link,
                    "published_at": news.ctime.strftime("%Y-%m-%d %H:%M:%S") if news.ctime else ""
                }

        # 构建优化后的结果数据
        result = {
            "date": content.get("date", "")
        }

        # 处理国内新闻并添加详情，优化结构
        if "top_news" in content:
            result["top_news"] = []
            for news in content["top_news"]:
                news_item = {
                    "title": news.get("content", ""),
                    "evaluation": news.get("evaluation", ""),
                    "sector": news.get("sector", ""),
                    "reason": news.get("reason", "")
                }

                if "news_id" in news and news["news_id"] in news_map:
                    news_detail = news_map[news["news_id"]]
                    news_item.update({
                        "id": news_detail["id"],
                        "content": news_detail["full_content"],
                        "link": news_detail["link"],
                        "published_at": news_detail["published_at"]
                    })

                result["top_news"].append(news_item)

        # 处理港股美股新闻并添加详情，优化结构
        if "hk_us_news" in content:
            result["hk_us_news"] = []
            for news in content["hk_us_news"]:
                news_item = {
                    "title": news.get("content", ""),
                    "evaluation": news.get("evaluation", ""),
                    "sector": news.get("sector", ""),
                    "reason": news.get("reason", "")
                }

                if "news_id" in news and news["news_id"] in news_map:
                    news_detail = news_map[news["news_id"]]
                    news_item.update({
                        "id": news_detail["id"],
                        "content": news_detail["full_content"],
                        "link": news_detail["link"],
                        "published_at": news_detail["published_at"]
                    })

                result["hk_us_news"].append(news_item)

        return jsonify(result)

    except Exception as e:
        session.rollback()
        return jsonify({"error": "服务器错误", "details": str(e)}), 500
    finally:
        session.close()


@wechat_bp.route('/wechat/push/settings', methods=['GET'])
def get_push_settings():
    """获取用户推送设置"""
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "缺少必要的user_id参数"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "user_id必须是整数"}), 400

    session = SessionLocal()
    try:
        # 查询用户的所有推送配置
        configs = session.query(UserPushConfig).filter_by(user_id=user_id).all()

        # 构建返回数据，包含所有可能的推送类型
        settings = {
            PUSH_TYPE_STOCK: False,  # 自选股推送，默认关闭
            PUSH_TYPE_MORNING: False  # 早报推送，默认关闭
        }

        # 用实际配置覆盖默认值
        for config in configs:
            settings[config.push_type] = config.enabled

        return jsonify({
            "code": 0,
            "msg": "success",
            "data": {
                "user_id": user_id,
                "settings": settings
            }
        })

    except Exception as e:
        return jsonify({"error": "服务器错误", "details": str(e)}), 500
    finally:
        session.close()


@wechat_bp.route('/wechat/push/settings', methods=['POST'])
def set_push_settings():
    """设置用户推送配置"""
    data = request.json
    if not data:
        return jsonify({"error": "请求数据为空"}), 400

    user_id = data.get('user_id')
    settings = data.get('settings')

    if not user_id or settings is None:
        return jsonify({"error": "缺少必要参数"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"error": "user_id必须是整数"}), 400

    session = SessionLocal()
    try:
        # 更新每个推送类型的设置
        for push_type, enabled in settings.items():
            # 检查推送类型是否有效
            if push_type not in [PUSH_TYPE_STOCK, PUSH_TYPE_MORNING]:
                continue

            # 查找现有配置
            config = session.query(UserPushConfig).filter_by(
                user_id=user_id,
                push_type=push_type
            ).first()

            if config:
                # 更新现有配置
                config.enabled = enabled
            else:
                # 创建新配置
                new_config = UserPushConfig(
                    user_id=user_id,
                    push_type=push_type,
                    enabled=enabled
                )
                session.add(new_config)

        session.commit()
        return jsonify({
            "code": 0,
            "msg": "推送设置已更新",
            "success": True
        })

    except Exception as e:
        session.rollback()
        return jsonify({"error": "服务器错误", "details": str(e)}), 500
    finally:
        session.close()
