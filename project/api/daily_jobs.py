import time
import threading
from flask import jsonify, Blueprint, request
from datetime import datetime, timedelta
import json
from services.state import MaintenanceState  # 导入状态管理类

MAINTENANCE_DURATION = 60  # 维护模式持续时间（秒）
KEEP_DAYS = 365            # 历史数据保留天数

def create_daily_jobs_blueprint(redis_service):
    """创建日常任务蓝图，包含维护模式触发接口"""
    bp = Blueprint('daily_jobs', __name__)
    maint_state = MaintenanceState(redis_service.client)  # 初始化维护状态管理器

    @bp.route('/stopserver', methods=['GET'])
    def stop_server():
        """触发维护模式接口"""
        if maint_state.is_maintenance():
            return jsonify({'status': 'error', 'message': 'Already in maintenance'}), 400
        
        maint_state.enter_maintenance()  # 原子操作设置维护状态
        redis_service.log_event("daily_jobs", f"触发维护模式: {datetime.now().isoformat()}")
        
        # 启动后台维护线程（非阻塞）
        t = threading.Thread(target=run_maintenance, args=(redis_service, maint_state), daemon=True)
        t.start()
        return jsonify({'status': 'success', 'message': 'Server in maintenance mode. Background job started.'})
    
    @bp.before_app_request
    def check_maintenance():
        allowed_paths = [
            '/stopserver',        # 触发维护模式
            '/get_backup',        # 查询备份数据
            '/get_logs',          # 查询日志
            '/meter/reading',     # 单条读数上报
            '/meter/bulk_readings' # 批量读数上报
        ]
        if maint_state.is_maintenance() and request.path not in allowed_paths:
            return jsonify({
                'status': 'error',
                'message': 'Server is in maintenance mode. Please try again later.'
            }), 503

    return bp

def run_maintenance(redis_service, maint_state):
    """执行维护任务（数据备份、清理、处理待定数据）"""
    try:
        redis_service.log_event("daily_jobs", "Entering Maintenance Mode...")
        
        # 1. 备份昨日数据
        process_daily_meter_readings(redis_service)
        
        # 2. 清理过期数据
        clean_old_data(redis_service, KEEP_DAYS)

        # 3. 模拟维护操作（等待指定时长）
        time.sleep(MAINTENANCE_DURATION)

        # 4. 处理维护期间暂存的数据
        process_pending_data(redis_service)
    finally:
        maint_state.exit_maintenance()  # 确保退出维护状态（异常安全）
        redis_service.log_event("daily_jobs", "Maintenance Done.")

def process_daily_meter_readings(redis_service):
    """计算并备份昨日总用电量"""
    yesterday = (datetime.now() - timedelta(days=1)).date()
    start_ts = datetime(yesterday.year, yesterday.month, yesterday.day).timestamp()
    end_ts = start_ts + 86400  # 24小时时间戳范围

    total_processed = 0
    # 遍历所有电表的历史数据键
    for key in redis_service.client.scan_iter("meter:*:history"):
        # 如果 key 为 bytes 类型，则解码
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        parts = key.split(":")
        if len(parts) < 3:
            continue
        meter_id = parts[1]  # 解析电表ID
        records = redis_service.client.zrangebyscore(key, start_ts, end_ts)
        if not records:
            continue

        # 修正语法错误，确保正确计算总用电量
        total_consumption = sum(float(json.loads(rec).get("consumption", 0)) for rec in records)
        # 存储备份数据
        redis_service.store_backup_usage(str(yesterday), meter_id, total_consumption)
        total_processed += 1

    redis_service.log_event("daily_jobs", f"Backup {total_processed} meter reading data for yesterday")

def clean_old_data(redis_service, keep_days):
    total_deleted = redis_service.remove_old_history(keep_days)
    redis_service.log_event("daily_jobs", f"Deleted {total_deleted} old records older than {keep_days} days.")

def process_pending_data(redis_service):
    """将维护期间的暂存数据转移到历史记录"""
    pending_keys = redis_service.client.keys("meter:*:pending")
    total_meters = 0
    for key in pending_keys:
        # 如果 key 为 bytes 类型，则解码
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        parts = key.split(":")
        if len(parts) < 3:
            continue
        meter_id = parts[1]
        count = redis_service.move_pending_to_history(meter_id)
        if count > 0:
            total_meters += 1
    redis_service.log_event("daily_jobs", f"Processed pending data for {total_meters} meter(s).")
