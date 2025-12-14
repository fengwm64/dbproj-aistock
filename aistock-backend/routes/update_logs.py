from flask import Blueprint, jsonify, request, current_app as app
from db.models import UpdateRecord
from sqlalchemy import desc
from datetime import datetime

# 创建蓝图
update_logs_bp = Blueprint("update_logs", __name__, url_prefix="/api")

@update_logs_bp.route("/logs", methods=["GET"])
def get_update_logs():
    """获取更新日志
    
    查询参数:
    - page: 页码，默认1
    - per_page: 每页数量，默认10，最大100
    - update_type: 更新类型筛选，可选
    """
    try:
        # 获取查询参数
        page = request.args.get("page", 1, type=int)
        per_page = min(request.args.get("per_page", 10, type=int), 100)  # 限制最大100条
        update_type = request.args.get("update_type", "").strip()
        
        app.logger.debug(f"[UPDATE_LOGS] 查询参数 - page: {page}, per_page: {per_page}, update_type: {update_type}")
        
        # 构建查询
        query = UpdateRecord.query
        
        # 按类型筛选
        if update_type:
            query = query.filter(UpdateRecord.update_type == update_type)
        
        # 按创建时间倒序排列
        query = query.order_by(desc(UpdateRecord.created_at))
        
        # 分页查询
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # 构建返回数据
        logs = []
        for record in pagination.items:
            logs.append({
                "id": record.id,
                "update_type": record.update_type,
                "message": record.message,
                "created_at": record.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        app.logger.info(f"[UPDATE_LOGS] 成功返回 {len(logs)} 条日志记录")
        
        return jsonify({
            "code": 0,
            "data": {
                "logs": logs,
                "pagination": {
                    "page": pagination.page,
                    "per_page": pagination.per_page,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_prev": pagination.has_prev,
                    "has_next": pagination.has_next
                }
            }
        })
        
    except Exception as e:
        app.logger.error(f"[UPDATE_LOGS] 获取更新日志失败: {str(e)}")
        return jsonify({"code": 500, "msg": "获取更新日志失败"}), 500


@update_logs_bp.route("/logs/types", methods=["GET"])
def get_update_types():
    """获取所有可用的更新类型"""
    try:
        # 查询所有不同的更新类型
        types = UpdateRecord.query.with_entities(UpdateRecord.update_type).distinct().all()
        
        # 提取类型列表
        type_list = [t[0] for t in types if t[0]]
        
        app.logger.debug(f"[UPDATE_LOGS] 找到 {len(type_list)} 种更新类型")
        
        return jsonify({
            "code": 0,
            "data": {
                "types": sorted(type_list)  # 按字母顺序排序
            }
        })
        
    except Exception as e:
        app.logger.error(f"[UPDATE_LOGS] 获取更新类型失败: {str(e)}")
        return jsonify({"code": 500, "msg": "获取更新类型失败"}), 500
