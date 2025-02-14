# background_worker.py

import os
import json
import redis
import time
import threading
from datetime import datetime

# ========== Redis 连接配置，与 meter_api.py 保持一致 ==========
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# ========== 常量定义 ==========
BULK_QUEUE_KEY = "meter:readings_queue"  # 批量读数队列（Redis List）
BULK_BATCH_SIZE = 100                    # 每次从队列最多取多少条
WORKER_SLEEP_INTERVAL = 2               # 如果队列为空，休眠多久(秒)再继续

def process_pending_meter_readings():
    """
    持续从 Redis 队列中读取批量记录，并将其写入每个电表的 SortedSet。
    """
    while True:
        try:
            # 1) 从队列里批量弹出 BULK_BATCH_SIZE 条数据
            batch_data = []
            for _ in range(BULK_BATCH_SIZE):
                item = r.lpop(BULK_QUEUE_KEY)
                if item:
                    batch_data.append(item)
                else:
                    break

            if not batch_data:
                # 队列为空 => 等待一会儿再继续
                time.sleep(WORKER_SLEEP_INTERVAL)
                continue

            # 2) 构建 Redis pipeline，批量 zadd 提升性能
            pipeline = r.pipeline(transaction=False)

            for raw_item in batch_data:
                try:
                    record = json.loads(raw_item)
                    meter_id = record['meter_id']
                    timestamp_str = record['timestamp']
                    reading_value = record['reading']

                    # 转换读数
                    reading = float(reading_value)  # 若出现 ValueError，跳到 except
                    # 转换时间戳
                    dt_obj = datetime.fromisoformat(timestamp_str)  # 若格式不对，会抛 ValueError
                    timestamp_iso = dt_obj.isoformat()
                    timestamp_unix = int(dt_obj.timestamp())

                    # 检查 MeterID 是否已注册
                    if not r.hexists("all_users", meter_id):
                        # 如果电表ID未注册，可跳过或记录错误
                        continue

                    # 批量写入 SortedSet
                    pipeline.zadd(
                        f"meter:{meter_id}:history",
                        {json.dumps({"timestamp": timestamp_iso, "reading_value": reading}): timestamp_unix}
                    )
                except (ValueError, KeyError, TypeError) as parse_err:
                    # 若解析失败或字段缺失，可选择记录日志或放入错误队列
                    print(f"[Worker] Skipped invalid record: {raw_item} | Error: {parse_err}")
                    continue
            
            # 3) 一次性提交 pipeline
            pipeline.execute()

        except redis.exceptions.RedisError as re:
            print(f"[Worker] Redis error: {str(re)}")
            time.sleep(WORKER_SLEEP_INTERVAL)
        except Exception as e:
            print(f"[Worker] Unexpected error: {str(e)}")
            time.sleep(WORKER_SLEEP_INTERVAL)


def start_background_worker():
    """
    启动后台线程，用于持续处理队列中的电表读数数据。
    在主应用 (app.py) 中调用即可。
    """
    worker_thread = threading.Thread(target=process_pending_meter_readings, daemon=True)
    worker_thread.start()
    print("[Worker] Background worker started.")
