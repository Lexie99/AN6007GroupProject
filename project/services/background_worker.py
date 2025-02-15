# services/background_worker.py
import os
import time
import json
import threading
from datetime import datetime
from services.redis_service import RedisService

BULK_QUEUE_KEY = "meter:readings_queue"
BULK_BATCH_SIZE = 100
WORKER_SLEEP_INTERVAL = 2

_stop_flag = False

def start_background_worker(redis_service=None):
    """
    在主应用或独立脚本调用此函数即可后台线程运行
    """
    if redis_service is None:
        redis_service = RedisService()
    t = threading.Thread(target=_worker_loop, args=(redis_service,), daemon=True)
    t.start()
    print("[background_worker] Worker thread started as daemon.")

def stop_background_worker():
    """
    通知 worker 停止
    """
    global _stop_flag
    _stop_flag = True
    print("[background_worker] stop flag set.")

def _worker_loop(redis_service):
    global _stop_flag
    print("[background_worker] Enter worker loop.")
    while not _stop_flag:
        process_batch(redis_service)
        time.sleep(WORKER_SLEEP_INTERVAL)
    print("[background_worker] Worker loop finished.")

def process_batch(redis_service):
    """
    1) 从 meter:readings_queue 取 BULK_BATCH_SIZE 条记录
    2) 对每条记录计算当次用电量（累积差值）
    3) 批量更新 meter:{id}:history,并同时更新该电表的 last_reading
    """
    batch_data = []
    for _ in range(BULK_BATCH_SIZE):
        item = redis_service.client.lpop(BULK_QUEUE_KEY)
        if item:
            batch_data.append(item)
        else:
            break

    if not batch_data:
        return

    pipeline = redis_service.client.pipeline(transaction=False)

    for raw in batch_data:
        try:
            record = json.loads(raw)
            meter_id = record["meter_id"]
            ts_str = record["timestamp"]
            reading_val = float(record["reading"])
            dt_obj = datetime.fromisoformat(ts_str)
            current_timestamp = dt_obj.timestamp()

            # 使用一个单独的键存储该电表上一次的累积读数
            last_key = f"meter:{meter_id}:last_reading"
            last_value = redis_service.client.get(last_key)
            if last_value is not None:
                last_value = float(last_value)
                consumption = reading_val - last_value
            else:
                # 如果没有上次数据，则无法计算增量，默认设为0
                consumption = 0.0

            # 更新 last_reading 为当前读数
            pipeline.set(last_key, reading_val)

            # 构造存入历史记录的完整数据，包含原始读数与计算出的当次用电量
            new_record = json.dumps({
                "timestamp": dt_obj.isoformat(),
                "reading_value": reading_val,
                "consumption": consumption
            })

            # 存入历史记录的有序集合，score使用时间戳
            history_key = f"meter:{meter_id}:history"
            pipeline.zadd(history_key, {new_record: current_timestamp})
        except (KeyError, ValueError) as e:
            print(f"[background_worker] Skipped invalid record: {raw} => {e}")
            continue

    pipeline.execute()
    print(f"[background_worker] Processed {len(batch_data)} records in batch.")
