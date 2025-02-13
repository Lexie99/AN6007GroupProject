import redis
import json
from flask import request, jsonify
from datetime import datetime, timedelta

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def log_backup_api(app):
    """
    注册日志和备份 API
    """

    @app.route('/get_logs', methods=['GET'])
    def get_logs():
        """
        获取日志：
        - log_type: "daily_jobs" / "server_status"（默认 "daily_jobs")
        - limit: 指定获取的日志数量（默认 50 条）
        """
        log_type = request.args.get("log_type", "daily_jobs")
        limit = int(request.args.get("limit", 50))  # 默认获取最近 50 条日志

        logs = r.lrange(f"logs:{log_type}", -limit, -1)
        return jsonify({"log_type": log_type, "logs": logs})

    @app.route('/get_backup', methods=['GET'])
    def get_backup():
        """
        获取指定日期的电表备份数据：
        - 如果不提供 `date` 参数，默认获取昨天的备份数据。
        - 返回数据格式为 JSON 解析后的电表数据。
        """
        date = request.args.get("date")
        if not date:
            date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

        backup_key = f"backup:meter_data:{date}"
        backup_data = r.hgetall(backup_key)

        if not backup_data:
            return jsonify({"status": "error", "message": f"No backup data found for {date}"}), 404

        # 解析 JSON 使数据格式更友好
        parsed_backup = {meter_id: json.loads(data) for meter_id, data in backup_data.items()}

        return jsonify({"status": "success", "date": date, "backup_data": parsed_backup})

def log_event(log_type, message):
    """
    记录日志到 Redis:
    - log_type: "daily_jobs" / "server_status"
    - message: 记录的日志内容
    """
    timestamp = datetime.now().isoformat()
    log_entry = f"{timestamp} - {message}"
    
    # 存入 Redis List（最多保留 1000 条，避免占用太多内存）
    log_key = f"logs:{log_type}"
    r.rpush(log_key, log_entry)
    r.ltrim(log_key, -1000, -1)

    print(f"📝 Log [{log_type}]: {message}")
