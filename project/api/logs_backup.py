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
        date_str = request.args.get("date")
        if not date_str:
            y = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
            date_str = y
        
        backup_key = f"backup:meter_data:{date_str}"
        bdata = redis_service.client.hgetall(backup_key)
        if not bdata:
            return jsonify({"status":"error","message":f"No backup data for {date_str}"}), 404
        
        return jsonify({"status":"success","date":date_str,"backup_data":bdata})

    return bp
