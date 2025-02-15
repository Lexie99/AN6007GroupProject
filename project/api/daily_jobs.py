# api/daily_jobs.py
import time
import threading
from flask import jsonify, Blueprint, request
from datetime import datetime, timedelta
import json
import services.state # 引入专门的状态模块

MAINTENANCE_DURATION = 180  # 维护时长（秒），测试时可调短
KEEP_DAYS = 365            # 超过多少天的历史读数要删除

def create_daily_jobs_blueprint(redis_service):
    bp = Blueprint('daily_jobs', __name__)

    @bp.route('/stopserver', methods=['GET'])
    def stop_server():
        if services.state.IS_MAINTENANCE:
            return jsonify({'status': 'error', 'message': 'Already in maintenance'}), 400

        services.state.IS_MAINTENANCE = True  # 修改全局状态
        t = threading.Thread(target=run_maintenance, args=(redis_service,), daemon=True)
        t.start()
        return jsonify({'status': 'success', 'message': 'Server in maintenance mode. Background job started.'})

    return bp

def run_maintenance(redis_service):
    print("🚧 Entering maintenance mode...")

    # 1) 备份昨日数据
    process_daily_meter_readings(redis_service)
    
    # 2) 清理旧数据
    clean_old_data(redis_service, KEEP_DAYS)

    # 3) 维持维护状态
    time.sleep(MAINTENANCE_DURATION)

    # 4) 处理 pending 数据
    process_pending_data(redis_service)

    services.state.IS_MAINTENANCE = False
    print("✅ Maintenance done.")

def process_daily_meter_readings(redis_service):
    """
    计算昨日总用电量, 并通过 RedisService 存入 backup:meter_data:<yyyy-mm-dd>
    """
    yesterday = (datetime.now() - timedelta(days=1)).date()
    start_ts = datetime(yesterday.year, yesterday.month, yesterday.day).timestamp()
    end_ts = start_ts + 86400

    meter_keys = redis_service.client.scan_iter("meter:*:history")
    total_processed = 0

    for mk in meter_keys:
        parts = mk.split(":")
        if len(parts) < 3:
            continue
        meter_id = parts[1]

        recs = redis_service.client.zrangebyscore(mk, start_ts, end_ts)
        if len(recs) < 2:
            continue

        data_list = []
        for raw in recs:
            try:
                data_list.append(json.loads(raw))
            except Exception as e:
                print(f"Error decoding JSON for key {mk}: {e}")
                continue

        try:
            usage = float(data_list[-1]["reading_value"]) - float(data_list[0]["reading_value"])
        except Exception as e:
            print(f"Error calculating usage for meter {meter_id}: {e}")
            continue

        redis_service.store_backup_usage(str(yesterday), meter_id, usage)
        total_processed += 1

    print(f"📊 Processed {total_processed} meters for {yesterday}, usage stored via RedisService.")

def clean_old_data(redis_service, keep_days):
    """
    调用 RedisService.remove_old_history(keep_days)
    删除 meter:*:history 中早于 cutoff_timestamp 的读数
    """
    total_deleted = redis_service.remove_old_history(keep_days)
    print(f"🗑️ Deleted {total_deleted} old records older than {keep_days} days.")

def process_pending_data(redis_service):
    """
    将维护期间写到 meter:{id}:pending 的数据转移到 history
    """
    keys = redis_service.client.keys("meter:*:pending")
    total_m = 0
    for k in keys:
        mid = k.split(":")[1]
        count = redis_service.move_pending_to_history(mid)
        if count:
            total_m += 1
    print(f"✅ Processed pending data for {total_m} meter(s).")

# 全局维护检查蓝图
def create_maintenance_blueprint():
    """
    注册此蓝图后,在维护期间除允许路径外,其他所有API请求都将返回 503 错误。
    """
    bp = Blueprint('maintenance', __name__)

    @bp.before_app_request
    def check_maintenance():
        # 允许访问的路径列表（可根据需要调整）
        allowed_paths = ['/stopserver', '/backup','/meter/reading','/meter/bulk_readings']
        if services.state.IS_MAINTENANCE and request.path not in allowed_paths:
            return jsonify({
                'status': 'error',
                'message': 'Server is in maintenance mode. Please try again later.'
            }), 503

    return bp
