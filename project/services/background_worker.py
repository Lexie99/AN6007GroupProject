import os
import time
import json
import threading
import redis
from datetime import datetime
from services.redis_service import RedisService

# Redis 相关键常量定义
BULK_QUEUE_KEY = "meter:readings_queue"   # 待处理的电表读数队列键名
BULK_BATCH_SIZE = 100                     # 每次批量处理的最大记录数
WORKER_SLEEP_INTERVAL = 2                 # 工作线程休眠间隔（秒）
MAX_RETRIES = 3                           # 单条记录的最大重试次数
DEAD_LETTER_QUEUE = "meter:dead_letter"   # 死信队列（存储彻底失败的数据）
RETRY_QUEUE = "meter:retry_queue"         # 重试队列（存储需重试的数据）
RETRY_COUNTS_KEY = "meter:retry_counts"   # 有序集合键名（记录每条数据的重试次数）

# 使用 threading.Event 替代全局停止标志，保证线程安全
_stop_event = threading.Event()

# 初始化全局默认的 RedisService 实例，并设置 DEAD_LETTER_QUEUE 的过期时间
_default_redis_service = RedisService()
_default_redis_service.client.expire(DEAD_LETTER_QUEUE, 86400)  # 24小时后自动删除

def start_background_worker(redis_service=None):
    """启动后台工作线程。

    Args:
        redis_service (RedisService, optional): Redis 服务实例。若未提供，使用默认实例。
    """
    if redis_service is None:
        redis_service = _default_redis_service
    # 创建守护线程（主程序退出时自动终止）
    t = threading.Thread(target=_worker_loop, args=(redis_service,), daemon=True)
    t.start()
    print("[background_worker] Worker thread started as daemon.")

def stop_background_worker():
    """设置全局停止标志，通知工作线程终止。"""
    _stop_event.set()
    print("[background_worker] Stop flag set.")

def _worker_loop(redis_service):
    """工作线程的主循环逻辑。

    1. 循环调用 process_batch 处理数据
    2. 通过 _stop_event 控制循环终止
    """
    print("[background_worker] Enter worker loop.")
    while not _stop_event.is_set():
        process_batch(redis_service)
        time.sleep(WORKER_SLEEP_INTERVAL)
    print("[background_worker] Worker loop finished.")

def process_batch(redis_service):
    """批量处理电表读数数据。

    1. 从队列中取出最多 BULK_BATCH_SIZE 条记录
    2. 解析每条记录并计算用电量（当前读数 - 上次读数）
    3. 更新电表历史数据和最后读数
    4. 失败记录进入重试或死信队列
    """
    batch_data = []
    # 从队列中批量读取数据
    for _ in range(BULK_BATCH_SIZE):
        item = redis_service.client.lpop(BULK_QUEUE_KEY)
        if item:
            batch_data.append(item)
        else:
            break
    if not batch_data:
        return

    # 创建 Redis 管道（批量执行命令提升性能）
    pipeline = redis_service.client.pipeline(transaction=False)
    
    for raw in batch_data:
        record = {}
        try:
            # 确保 raw 为字符串（Redis 返回的可能为 bytes）
            if isinstance(raw, bytes):
                raw = raw.decode("utf-8")
            # --- 数据解析与校验 ---
            record = json.loads(raw)
            meter_id = record["meter_id"]
            ts_str = record["timestamp"]
            reading_val = float(record["reading"])
            dt_obj = datetime.fromisoformat(ts_str)
            current_timestamp = dt_obj.timestamp()

            # --- 计算用电量（当前读数减去上次读数） ---
            last_key = f"meter:{meter_id}:last_reading"
            last_value = redis_service.client.get(last_key)
            if last_value is not None:
                if isinstance(last_value, bytes):
                    last_value = last_value.decode("utf-8")
                # 修正计算公式：当前读数 - 上次读数
                consumption = reading_val - float(last_value)
            else:
                consumption = 0.0  # 首次读数无法计算增量，默认为0

            # --- 更新电表最后读数和历史记录 ---
            # 1. 设置当前读数为新的最后读数
            pipeline.set(last_key, reading_val)
            # 2. 构造完整历史记录（包含时间戳、读数和用电量）
            new_record = json.dumps({
                "timestamp": dt_obj.isoformat(),
                "reading_value": reading_val,
                "consumption": consumption
            })
            # 3. 将记录添加到有序集合（按时间戳排序）
            history_key = f"meter:{meter_id}:history"
            pipeline.zadd(history_key, {new_record: current_timestamp})

        except Exception as e:
            # --- 异常处理逻辑 ---
            short_raw = f"meter_id={record.get('meter_id', 'unknown')}, ts={record.get('timestamp', 'unknown')}"
            redis_service.log_event("background_worker", 
                f"Failed to process record: {str(e)} | Metadata: {short_raw}")
            
            # --- 重试机制 ---
            retry_count = redis_service.client.zscore(RETRY_COUNTS_KEY, raw) or 0
            retry_count = int(retry_count) + 1
            redis_service.client.zadd(RETRY_COUNTS_KEY, {raw: retry_count})
            
            if retry_count <= MAX_RETRIES:
                redis_service.client.rpush(RETRY_QUEUE, raw)
            else:
                redis_service.client.rpush(DEAD_LETTER_QUEUE, raw)
                redis_service.client.zrem(RETRY_COUNTS_KEY, raw)

    # 执行管道中的所有命令，并捕获可能的错误
    try:
        pipeline.execute()
    except redis.exceptions.RedisError as e:
        redis_service.log_event("background_worker", f"Pipeline execution failed: {str(e)}")
