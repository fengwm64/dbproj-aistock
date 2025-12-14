from flask import Blueprint, jsonify, request, current_app
import requests
import hashlib
import time
import os
from flask_jwt_extended import jwt_required

monitor_bp = Blueprint('monitor', __name__, url_prefix='/api/monitor')

def get_1panel_auth_headers():
    # 从环境变量获取API密钥
    api_key = os.getenv('MONITOR_KEY')
    timestamp = str(int(time.time()))
    # 生成1Panel token
    token_str = f"1panel{api_key}{timestamp}"
    token = hashlib.md5(token_str.encode()).hexdigest()
    
    return {
        "accept": "application/json",
        "1Panel-Token": token,
        "1Panel-Timestamp": timestamp,
        "Content-Type": "application/json"
    }

@monitor_bp.route('/server-status', methods=['GET'])
@jwt_required()
def get_server_status():
    """获取服务器状态信息"""
    try:
        # 从查询参数中获取时间范围，如果没有则使用默认值
        start_time = request.args.get('start_time', None)
        end_time = request.args.get('end_time', None)
        
        # 如果没有提供时间参数，使用前5分钟到当前的时间范围
        if not start_time or not end_time:
            from datetime import datetime, timedelta
            now = datetime.utcnow()
            end_time = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            start_time = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # 准备请求1Panel API的数据
        headers = get_1panel_auth_headers()
        payload = {
            "info": "",
            "param": "all",
            "startTime": start_time,
            "endTime": end_time
        }
        
        # 调用1Panel监控API
        response = requests.post(
            'http://129.204.195.248:10086/api/v1/hosts/monitor/search',
            headers=headers,
            json=payload
        )
        
        # 检查响应状态
        response.raise_for_status()
        data = response.json()
        
        # 返回数据，确保返回码为200
        return jsonify({
            "code": 200,
            "message": "获取服务器状态成功",
            "data": data.get("data", [])
        })
        
    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"请求1Panel API错误: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"请求1Panel API失败: {str(e)}",
            "data": None
        }), 500
    except Exception as e:
        current_app.logger.error(f"获取服务器状态错误: {str(e)}")
        return jsonify({
            "code": 500,
            "message": f"获取服务器状态失败: {str(e)}",
            "data": None
        }), 500
