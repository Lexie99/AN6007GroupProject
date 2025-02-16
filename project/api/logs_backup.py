# api/logs_backup.py
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta

def create_logs_backup_blueprint(redis_service):
    """创建日志与备份查询接口蓝图"""
    bp = Blueprint('logs_backup', __name__)

    @bp.route('/get_logs', methods=['GET'])
    def get_logs():
        """查询指定类型的日志（默认返回最近50条）"""
        log_type = request.args.get('log_type', 'daily_jobs')
        limit = int(request.args.get('limit', 50))
        logs = redis_service.get_logs(log_type, limit)
        return jsonify({"log_type": log_type, "logs": logs})

    @bp.route('/get_backup', methods=['GET'])
    def get_backup():
        """查询指定日期的备份数据（默认昨日）"""
        date_str = request.args.get("date") or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        backup_data = redis_service.get_backup_data(date_str)
        if not backup_data:
            return jsonify({"status": "error", "message": f"无{date_str}的备份数据"}), 404
        return jsonify({"status": "success", "date": date_str, "data": backup_data})

    return bp