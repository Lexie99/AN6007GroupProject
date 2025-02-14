# api/logs_backup.py

from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta

def create_logs_backup_blueprint(redis_service):
    bp = Blueprint('logs_backup', __name__)

    @bp.route('/get_logs', methods=['GET'])
    def get_logs():
        log_type = request.args.get('log_type', 'daily_jobs')
        limit = int(request.args.get('limit', 50))
        logs = redis_service.get_logs(log_type, limit)
        return jsonify({"log_type": log_type, "logs": logs})

    @bp.route('/get_backup', methods=['GET'])
    def get_backup():
        """
        GET /get_backup?date=YYYY-MM-DD
        如未传 date,则默认获取昨天
        """
        date_str = request.args.get("date")
        if not date_str:
            date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        # 调用 RedisService 的 get_backup_data
        bdata = redis_service.get_backup_data(date_str)
        if not bdata:  # 空dict => 无数据
            return jsonify({"status": "error", "message": f"No backup data for {date_str}"}), 404

        return jsonify({"status":"success","date":date_str,"backup_data":bdata})

    return bp
