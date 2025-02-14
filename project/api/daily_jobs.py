# daily_jobs_api.py

import os
import time
import json
import redis
import threading
from datetime import datetime, timedelta
from flask import jsonify
from api.logs_backup import log_event

# Redis 连接
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# 配置项
KEEP_DAYS = 365               # 保留365天的数据
MAINTENANCE_DURATION = 3600   # 维护时长（秒），默认1小时
IS_MAINTENANCE = False        # 全局标记：是否处于维护模式

def daily_jobs_api(app):
    @app.route('/stopserver', methods=['GET'])
    def stop_server():
        """
        启动维护模式：
        - 若当前已在维护，则返回错误
        - 否则，创建一个后台线程执行 run_maintenance()，然后立即返回
        """
        global IS_MAINTENANCE
        if IS_MAINTENANCE:
            return jsonify({'status': 'error', 'message': 'Already in maintenance mode.'}), 400

        try:
            # 标记进入维护
            IS_MAINTENANCE = True

            # 启动后台线程执行 run_maintenance（不阻塞当前请求）
            maintenance_thread = threading.Thread(target=run_maintenance, daemon=True)
            maintenance_thread.start()

            return jsonify({'status': 'success', 'message': 'Server is in maintenance mode. Background job started.'}), 200
        except Exception as e:
            IS_MAINTENANCE = False
            return jsonify({'status': 'error', 'message': f'Failed to start maintenance mode: {str(e)}'}), 500


def run_maintenance():
    """
    后台执行的维护任务：
    1. 日志记录进入维护模式
    2. 计算并备份昨日电表数据 -> process_daily_meter_readings()
    3. 模拟停机:sleep(维护时长)
    4. 维护结束后处理 pending -> process_pending_data()
    5. 退出维护模式
    """
    
    log_event("daily_jobs", "Server entering maintenance mode...")

    # 1) 计算并备份昨日电表数据
    process_daily_meter_readings()

    # 2) 模拟停机
    print(f"⏳ Server in maintenance mode for {MAINTENANCE_DURATION / 60} minutes...")
    time.sleep(MAINTENANCE_DURATION)

    # 3) 维护结束后处理 pending
    process_pending_data()

    global IS_MAINTENANCE
    IS_MAINTENANCE = False
    log_event("daily_jobs", "Server maintenance completed.")


def process_daily_meter_readings():
    """
    计算昨日总用电量，存入 Redis 备份
    """
    yesterday = (datetime.now() - timedelta(days=1)).date()
    start_timestamp = datetime(yesterday.year, yesterday.month, yesterday.day).timestamp()
    end_timestamp = start_timestamp + 86400

    backup_key = f"backup:meter_data:{yesterday}"
    total_processed = 0

    meter_keys = r.scan_iter("meter:*:history")
    for key in meter_keys:
        parts = key.split(":")
        if len(parts) < 3:
            continue
        meter_id = parts[1]

        # 获取昨日范围内数据
        readings = r.zrangebyscore(key, start_timestamp, end_timestamp)
        if len(readings) < 2:
            continue  # 不能计算增量

        data_points = []
        for raw in readings:
            try:
                data_points.append(json.loads(raw))
            except json.JSONDecodeError:
                print(f"[Backup] JSON decode error for meter {meter_id}: {raw}")
                continue

        # 计算增量 (最后 - 第一个)
        total_usage = float(data_points[-1]["reading_value"]) - float(data_points[0]["reading_value"])

        # 写入备份 hash
        r.hset(
            backup_key,
            meter_id,
            json.dumps({
                "meter_id": meter_id,
                "date": str(yesterday),
                "total_usage": total_usage
            })
        )
        total_processed += 1

    print(f"📊 [Backup] Processed {total_processed} meters for {yesterday}. Stored in {backup_key}.")

    # 备份完成后再清理旧数据
    clean_old_data()


def clean_old_data():
    """
    删除超过 KEEP_DAYS 的历史读数
    """
    cutoff_date = datetime.now() - timedelta(days=KEEP_DAYS)
    cutoff_timestamp = cutoff_date.timestamp()
    deleted_records = 0

    meter_keys = r.scan_iter("meter:*:history")
    for key in meter_keys:
        deleted = r.zremrangebyscore(key, "-inf", cutoff_timestamp)
        deleted_records += deleted

    print(f"🗑️ [Clean] Deleted {deleted_records} old records (older than {KEEP_DAYS} days).")


def process_pending_data():
    """
    若维护期间还要接收新读数并写到 pending,这里一次性处理并写回 history。
    """
    meter_keys = r.keys("meter:*:pending")
    processed_count = 0

    for key in meter_keys:
        parts = key.split(":")
        if len(parts) < 3:
            continue
        meter_id = parts[1]

        try:
            pending_data = r.lrange(key, 0, -1)
        except redis.RedisError as e:
            print(f"[Pending] Error retrieving data for meter {meter_id}: {str(e)}")
            continue

        if not pending_data:
            continue

        for record in pending_data:
            try:
                data = json.loads(record)
                dt_obj = datetime.fromisoformat(data["timestamp"])
                timestamp_unix = int(dt_obj.timestamp())

                # 写到 meter:{id}:history
                r.zadd(f"meter:{meter_id}:history", {record: timestamp_unix})
            except Exception as ex:
                print(f"[Pending] Error processing record: {record}, err={ex}")
                continue

        # 清空 pending
        r.delete(key)
        processed_count += 1

    print(f"✅ [Pending] Processed {processed_count} meters from pending.")
