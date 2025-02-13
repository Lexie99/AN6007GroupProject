import redis
import json
import threading
from datetime import datetime, timedelta
from flask import jsonify

r = redis.Redis(host='localhost', port=6379, decode_responses=True)
KEEP_DAYS = 365  # 只保留 365 天的数据
MAINTENANCE_DURATION = 3600  # 维护时间（1小时）

def register_daily_jobs(app):
    @app.route('/stopserver', methods=['GET'])
    def stop_server():
        """
        启动服务器维护模式：
        - 计算昨日用电量并备份
        - 清理过期数据
        - 处理维护期间的 pending 数据
        """
        thread = threading.Thread(target=run_maintenance)
        thread.start()
        return jsonify({'status': 'success', 'message': 'Server is in maintenance mode. Background jobs started.'})

def run_maintenance():
    """
    服务器维护任务（后台运行，不阻塞 Flask）
    """
    print("🚧 Server entering maintenance mode...")

    # 计算昨日用电量并备份
    process_daily_meter_readings()

    # 模拟 1 小时维护
    print(f"⏳ Maintenance for {MAINTENANCE_DURATION / 60} minutes...")
    threading.Event().wait(MAINTENANCE_DURATION)

    # 处理维护期间积压的数据
    process_pending_data()

    print("✅ Server maintenance completed.")

def process_daily_meter_readings():
    """
    计算昨日总用电量，存入 Redis 备份
    """
    yesterday = (datetime.now() - timedelta(days=1)).date()
    start_timestamp = datetime(yesterday.year, yesterday.month, yesterday.day).timestamp()
    end_timestamp = start_timestamp + 86400  # 24小时后的时间戳

    meter_keys = r.keys("meter:*:history")
    backup_key = f"backup:meter_data:{yesterday}"

    total_processed = 0
    for key in meter_keys:
        meter_id = key.split(":")[1]
        readings = r.zrangebyscore(f"meter:{meter_id}:history", start_timestamp, end_timestamp)

        if len(readings) < 2:
            continue  # 至少需要两个数据点才能计算增量

        data = [json.loads(h) for h in readings]
        total_usage = float(data[-1]["reading_value"]) - float(data[0]["reading_value"])

        r.hset(backup_key, meter_id, json.dumps({
            "meter_id": meter_id,
            "date": str(yesterday),
            "total_usage": total_usage
        }))
        total_processed += 1

    print(f"📊 Processed {total_processed} meters for {yesterday}. Backup stored in {backup_key}.")
    
    # 清理 Redis 旧数据
    clean_old_data()

def clean_old_data():
    """
    删除 Redis 过期数据（超过 365 天）
    """
    cutoff_date = datetime.now() - timedelta(days=KEEP_DAYS)
    cutoff_timestamp = cutoff_date.timestamp()

    meter_keys = r.keys("meter:*:history")
    deleted_records = 0
    for key in meter_keys:
        deleted_count = r.zremrangebyscore(key, "-inf", cutoff_timestamp)  # 删除过旧的数据
        deleted_records += deleted_count

    print(f"🗑️ Deleted {deleted_records} old records from Redis (older than {KEEP_DAYS} days).")

def process_pending_data():
    """
    服务器恢复后，处理维护期间的 pending 数据
    """
    meter_keys = r.keys("meter:*:pending")
    processed_count = 0

    for key in meter_keys:
        meter_id = key.split(":")[1]
        pending_data = r.lrange(f"meter:{meter_id}:pending", 0, -1)

        if not pending_data:
            continue

        for record in pending_data:
            data = json.loads(record)
            timestamp = datetime.fromisoformat(data["timestamp"]).timestamp()

            # 存入 `Sorted Set`
            r.zadd(f"meter:{meter_id}:history", {record: timestamp})

        r.delete(f"meter:{meter_id}:pending")
        processed_count += 1

    print(f"✅ Processed pending data for {processed_count} meters.")
