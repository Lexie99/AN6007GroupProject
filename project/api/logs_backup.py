import json
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta

def create_logs_backup_blueprint(redis_service):
    """创建日志与备份查询接口蓝图"""
    bp = Blueprint('logs_backup', __name__)

    @bp.route('/get_logs', methods=['GET'])
    def get_logs():
        """
        查询指定类型的日志(默认返回最近50条)。
        可选参数：
          - log_type: 日志类型（默认为 daily_jobs)
          - limit: 返回日志条数（默认为 50)
          - date: 指定日期（格式 YYYY-MM-DD),只返回该日期的日志
        """
        log_type = request.args.get('log_type', 'daily_jobs')
        limit = int(request.args.get('limit', 50))
        date_str = request.args.get('date')  # 可选的日期过滤参数

        # 从 Redis 中获取原始日志（存储为 JSON 字符串列表）
        logs = redis_service.get_logs(log_type, limit)

        # 如果传入了 date 参数，则过滤日志，只返回指定日期的日志记录
        if date_str:
            filtered_logs = []
            for log_entry in logs:
                try:
                    log_obj = json.loads(log_entry)
                    # 假设 timestamp 格式为 "YYYY-MM-DDTHH:MM:SS.ssssss"，取前 10 个字符进行比较
                    if log_obj.get("timestamp", "")[:10] == date_str:
                        filtered_logs.append(log_entry)
                except Exception as e:
                    # 解析错误则跳过该日志
                    continue
            return jsonify({"log_type": log_type, "logs": filtered_logs})
        else:
            return jsonify({"log_type": log_type, "logs": logs})

    @bp.route('/get_backup', methods=['GET'])
    def get_backup():
        """
        查询指定日期的备份数据（默认查询昨日）。
        可选参数：
          - date: 指定日期，格式为 YYYY-MM-DD
        """
        date_str = request.args.get("date") or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        backup_data = redis_service.get_backup_data(date_str)
        if not backup_data:
            return jsonify({"status": "error", "message": f"No Backup Data for {date_str}"}), 404
        return jsonify({"status": "success", "date": date_str, "data": backup_data})

    return bp
