from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required
import pandas as pd
import logging
import redis
import json
from datetime import datetime, timedelta
import akshare as ak
from db.models import db, Index

market_bp = Blueprint('market', __name__, url_prefix='/api')
logger = logging.getLogger('app')

@market_bp.route('/market/overview', methods=['GET'])
def get_market_overview():
    """
    极简市场概览API（仅返回核心指标）
    
    返回格式：
    {
        "code": 0,
        "msg": "success",
        "data": [
            {"index": "上证指数", "value": 3352.00, "change": 9.33, "change_pct": 0.279},
            {"index": "深证成指", "value": 10126.83, "change": -70.83, "change_pct": -0.69},
            {"index": "创业板指", "value": 2008.56, "change": -15.22, "change_pct": -0.755},
            {"index": "纳斯达克中国金龙指数", "value": 5643.22, "change": 25.52, "change_pct": 0.455},
            {"index": "富时中国A50指数", "value": 12345.67, "change": 123.45, "change_pct": 1.01},
            {"index": "恒生科技指数", "value": 4321.09, "change": -43.21, "change_pct": -0.99}
        ]
    }
    """
    try:
        # 使用ORM查询目标指数的最新数据
        target_indices = ['上证指数', '深证成指', '创业板指', 
                         '纳斯达克中国金龙指数', '富时中国A50', '恒生科技指数']
        
        indices_data = db.session.query(Index).filter(
            Index.name.in_(target_indices)
        ).all()
        
        # 格式化结果
        result_dict = {}
        for index in indices_data:
            result_dict[index.name] = {
                "index": index.name,
                "value": float(index.value),
                "change": float(index.change_amount),
                "change_pct": float(index.change_percent)
            }
        
        # 按照指定顺序排列结果
        ordered_result = []
        for idx_name in target_indices:
            if idx_name in result_dict:
                ordered_result.append(result_dict[idx_name])
        
        return jsonify({
            "code": 0,
            "msg": "success",
            "data": ordered_result
        })
    
    except Exception as e:
        logger.error(f"[market/overview] 数据库查询失败: {e}", exc_info=True)
        return jsonify({
            "code": 500,
            "msg": "服务端错误",
            "error": "无法从数据库获取指数数据"
        }), 500
