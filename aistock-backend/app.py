from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager
from dotenv import load_dotenv
import os
from datetime import datetime
from db.models import db
from routes import init_routes
import logging
from flask_cors import CORS

# --------------------------------------------------------------------
# 加载环境变量
# --------------------------------------------------------------------
load_dotenv(override=True)

# --------------------------------------------------------------------
# 初始化 Flask 应用
# --------------------------------------------------------------------
app = Flask(__name__)
app.config.update(
    SQLALCHEMY_DATABASE_URI=os.getenv("DATABASE_URI"),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    JWT_SECRET_KEY=os.getenv("JWT_SECRET_KEY"),
    WECHAT_APPID=os.getenv("WECHAT_APPID"),
    WECHAT_SECRET=os.getenv("WECHAT_SECRET"),
    WECHAT_TEMPLATE_ID=os.getenv("WECHAT_TEMPLATE_ID"),
    REDIS_BROKER_URL=os.getenv("REDIS_BROKER_URL"),
    WECHAT_SCAN_APPID=os.getenv("WECHAT_SCAN_APPID"),
    WECHAT_SCAN_SECRET=os.getenv("WECHAT_SCAN_SECRET"),
    WECHAT_SCAN_TOKEN=os.getenv("WECHAT_SCAN_TOKEN"),
)
CORS(app, supports_credentials=True, origins=["https://aistocklink.cn"])

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # 输出到控制台
    ]
)

# 初始化微信错误跟踪
app.last_wx_error = None

# --------------------------------------------------------------------
# 初始化扩展
# --------------------------------------------------------------------
db.init_app(app)
jwt = JWTManager(app)

# --------------------------------------------------------------------
# 初始化数据库表
# --------------------------------------------------------------------
with app.app_context():
    try:
        app.logger.info("正在初始化数据库表...")
        db.create_all()  # 确保所有模型被正确映射到数据库
        app.logger.info("数据库表初始化成功")
    except Exception as e:
        app.logger.error(f"数据库表初始化失败: {str(e)}")

# 初始化路由
init_routes(app)

# --------------------------------------------------------------------
# 路由示例
# --------------------------------------------------------------------
@app.route("/", methods=["GET"])
def server_info():
    return jsonify({
        "project": "Stock API Service",
        "version": "1.0.0",
        "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })


@app.route("/api", methods=["GET"])
def api_status():
    return jsonify({"status": "running"})


# --------------------------------------------------------------------
# 启动服务
# --------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9999, debug=True)
