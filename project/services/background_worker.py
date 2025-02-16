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

# 全局停止标志（用于控制后台线程终止）
_stop_flag = False


def start_background_worker(redis_service=None):
    """启动后台工作线程。
    
    Args:
        redis_service (RedisService, optional): Redis 服务实例。若未提供，默认创建新实例。
    """
    if redis_service is None:
        redis_service = RedisService()
    # 创建守护线程（主程序退出时自动终止）
    t = threading.Thread(target=_worker_loop, args=(redis_service,), daemon=True)
    t.start()
    print("[background_worker] Worker thread started as daemon.")


def stop_background_worker():
    """设置全局停止标志，通知工作线程终止。"""
    global _stop_flag
    _stop_flag = True
    print("[background_worker] Stop flag set.")


def _worker_loop(redis_service):
    """工作线程的主循环逻辑。
    
    1. 循环调用 process_batch 处理数据
    2. 通过 _stop_flag 控制循环终止
    """
    global _stop_flag
    print("[background_worker] Enter worker loop.")
    while not _stop_flag:
        process_batch(redis_service)
        time.sleep(WORKER_SLEEP_INTERVAL)
    print("[background_worker] Worker loop finished.")


def process_batch(redis_service):
    """批量处理电表读数数据。
    
    1. 从队列中取出最多 BULK_BATCH_SIZE 条记录
    2. 解析每条记录并计算用电量（累积差值）
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
        try:
            # --- 数据解析与校验 ---
            record = json.loads(raw)
            meter_id = record["meter_id"]
            ts_str = record["timestamp"]
            reading_val = float(record["reading"])
            dt_obj = datetime.fromisoformat(ts_str)
            current_timestamp = dt_obj.timestamp()

            # --- 计算用电量（当前读数 - 上次读数）---
            last_key = f"meter:{meter_id}:last_reading"
            last_value = redis_service.client.get(last_key)
            if last_value is not None:
                consumption = float(last_value) - reading_val
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
            # 生成简化的错误元数据（避免日志过长）
            short_raw = f"meter_id={record.get('meter_id', 'unknown')}, ts={record.get('timestamp', 'unknown')}"
            # 记录结构化错误日志
            redis_service.log_event("background_worker", 
                f"Failed to process record: {str(e)} | Metadata: {short_raw}")
            
            # --- 重试机制 ---
            # 1. 获取当前重试次数
            retry_count = redis_service.client.zscore(RETRY_COUNTS_KEY, raw) or 0
            retry_count = int(retry_count) + 1
            # 2. 更新重试次数到有序集合
            redis_service.client.zadd(RETRY_COUNTS_KEY, {raw: retry_count})
            
            if retry_count <= MAX_RETRIES:
                # 若未超最大重试次数，加入重试队列
                redis_service.client.rpush(RETRY_QUEUE, raw)
            else:
                # 若超过最大重试次数，加入死信队列并清理重试计数
                redis_service.client.rpush(DEAD_LETTER_QUEUE, raw)
                redis_service.client.zrem(RETRY_COUNTS_KEY, raw)

    try:
        # 批量执行所有 Redis 命令
        pipeline.execute()
        print(f"[background_worker] Processed {len(batch_data)} records in batch.")
    except redis.exceptions.RedisError as e:
        # 记录管道执行失败日志
        redis_service.log_event("background_worker", f"Pipeline execution failed: {str(e)}")