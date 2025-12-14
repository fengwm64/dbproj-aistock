# 路由模块初始化
from flask import Flask

def init_routes(app: Flask):
    """初始化所有路由"""
    from .user import user_bp
    from .stock import stock_bp
    from .news import news_bp
    from .ai_eva import ai_eva_bp
    from routes.market import market_bp
    from .wechat import wechat_bp
    from .update_logs import update_logs_bp
    from .tags import tags_bp
    from .monitor import monitor_bp
    from .chat import chat_bp

    # 注册蓝图
    app.register_blueprint(user_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(ai_eva_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(wechat_bp)
    app.register_blueprint(update_logs_bp)
    app.register_blueprint(tags_bp)
    app.register_blueprint(monitor_bp)
    app.register_blueprint(chat_bp)

    app.logger.info("所有路由已注册")