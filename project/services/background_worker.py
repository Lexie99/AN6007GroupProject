import os
import time
import json
import threading
import hashlib
import redis
from datetime import datetime, timedelta, timezone
from services.redis_service import RedisService

# Redis 相关常量定义
BULK_QUEUE_KEY = "meter:readings_queue"    # 待处理的电表读数队列键名
BULK_BATCH_SIZE = 100                      # 每次批量处理的最大记录数
NUM_WORKERS = 4                            # 同时启动的后台 worker 数量
WORKER_SLEEP_INTERVAL = 1                  # 工作线程休眠间隔（秒）
MAX_RETRIES = 3                            # 单条记录的最大重试次数
DEAD_LETTER_QUEUE = "meter:dead_letter"    # 死信队列
RETRY_QUEUE = "meter:retry_queue"          # 重试队列
RETRY_COUNTS_KEY = "meter:retry_counts"    # 记录每条数据重试次数的有序集合
PROCESSED_SET = "processed_records"        # 存储已处理记录唯一标识的集合

# 使用 threading.Event 替代全局停止标志
_stop_event = threading.Event()

# 初始化全局默认的 RedisService 实例，并设置 DEAD_LETTER_QUEUE 的过期时间
_default_redis_service = RedisService()
_default_redis_service.client.expire(DEAD_LETTER_QUEUE, 86400)  # 24小时后自动删除

def generate_record_id(raw):
    """计算记录的唯一标识（使用 MD5 哈希 raw 数据）"""
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

# 修改后的 Lua 脚本：原子操作计算 consumption，并将计算结果写入新记录 JSON 字符串中
# KEYS[1] - 上次读数键 (meter:{id}:last_reading)，存储纯数字字符串
# KEYS[2] - 历史记录键 (meter:{id}:history)
# ARGV[1] - 新读数 (new_reading)，数字字符串
# ARGV[2] - 当前时间戳 (score)
# ARGV[3] - 原始的新记录 JSON 字符串（其中 "consumption" 的值为 0 ）
local_lua_script = r"""
local last = redis.call('GET', KEYS[1])
local consumption = 0
if last then
    consumption = tonumber(ARGV[1]) - tonumber(last)
end
redis.call('SET', KEYS[1], ARGV[1])
local new_record = string.sub(ARGV[3], 1, -2) .. ', "consumption":' .. consumption .. '}'
redis.call('ZADD', KEYS[2], ARGV[2], new_record)
return consumption
"""

def process_record_atomic(redis_client, meter_id, new_reading, current_timestamp, new_record_json):
    """调用 Lua 脚本进行原子操作，返回计算出的消费量。"""
    last_key = f"meter:{meter_id}:last_reading"
    history_key = f"meter:{meter_id}:history"
    consumption = redis_client.eval(local_lua_script, 2, last_key, history_key, str(new_reading), str(current_timestamp), new_record_json)
    return consumption

def start_background_worker(redis_service=None):
    """启动后台 worker(支持并发多个 worker)"""
    if redis_service is None:
        redis_service = _default_redis_service
    workers = []
    for i in range(NUM_WORKERS):
        t = threading.Thread(target=_worker_loop, args=(redis_service,), daemon=True)
        t.start()
        workers.append(t)
        print(f"[background_worker] Worker thread {i+1} started as daemon.")
    return workers

def stop_background_worker():
    """设置停止标志，通知 worker 终止。"""
    _stop_event.set()
    print("[background_worker] Stop flag set.")

def _worker_loop(redis_service):
    """Worker 主循环"""
    print("[background_worker] Enter worker loop.")
    while not _stop_event.is_set():
        process_batch(redis_service)
        time.sleep(WORKER_SLEEP_INTERVAL)
    print("[background_worker] Worker loop finished.")

def process_batch(redis_service):
    """批量处理电表读数数据，确保同一电表记录按时间顺序处理"""
    batch_data = []
    # 使用 BLPOP 阻塞方式，每次最多读取 BULK_BATCH_SIZE 条记录（timeout=1秒）
    for _ in range(BULK_BATCH_SIZE):
        item = redis_service.client.blpop(BULK_QUEUE_KEY, timeout=1)
        if item:
            batch_data.append(item[1])
        else:
            break
    if not batch_data:
        return

    # 按 meter_id 分组
    records_by_meter = {}
    for raw in batch_data:
        try:
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            rec = json.loads(raw)
            meter_id = rec["meter_id"]
            records_by_meter.setdefault(meter_id, []).append((raw, rec))
        except Exception as e:
            redis_service.log_event("background_worker", f"Failed to parse record: {e}")
    
    # 对每个电表的数据按时间戳排序后逐条处理
    for meter_id, rec_list in records_by_meter.items():
        # 排序（按 timestamp 升序）
        rec_list.sort(key=lambda x: datetime.fromisoformat(x[1]["timestamp"]))
        # 对同一电表加锁，确保串行处理
        lock_key = f"lock:meter:{meter_id}"
        lock = redis_service.client.lock(lock_key, timeout=5)
        acquired = lock.acquire(blocking=True, blocking_timeout=3)
        if not acquired:
            continue
        try:
            for raw, record in rec_list:
                # 确保同一记录只处理一次
                record_id = generate_record_id(raw)
                if redis_service.client.sadd(PROCESSED_SET, record_id) == 0:
                    continue

                ts_str = record["timestamp"]
                reading_val = float(record["reading"])
                # 解析时间并转换为 UTC 时间戳
                dt_obj = datetime.fromisoformat(ts_str)
                if dt_obj.tzinfo is None:
                    dt_obj = dt_obj.astimezone()  # 假设为本地时间
                dt_obj_utc = dt_obj.astimezone(timezone.utc)
                current_timestamp = dt_obj_utc.timestamp()
                timestamp_str = dt_obj.isoformat()

                # 构造新记录 JSON，注意 "consumption" 字段暂设为 0
                new_record = {
                    "timestamp": timestamp_str,
                    "reading_value": reading_val,
                    "consumption": 0
                }
                new_record_json = json.dumps(new_record)
                print(f"[DEBUG] Meter {meter_id}: processing record with timestamp {timestamp_str}, reading = {reading_val}")
                print(f"[DEBUG] Meter {meter_id}: about to call Lua with new_reading = {reading_val}, current_timestamp = {current_timestamp}")
                consumption = process_record_atomic(redis_service.client, meter_id, reading_val, current_timestamp, new_record_json)
                print(f"[DEBUG] Meter {meter_id}: after Lua, updated last_reading = {reading_val}, Lua returned consumption = {consumption}")
        finally:
            lock.release()
