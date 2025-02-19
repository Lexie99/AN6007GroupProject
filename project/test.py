import os
import time
import random
import requests
import redis
import json
from datetime import datetime, timedelta

# 基础 URL 及各接口 URL
BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")
REGISTER_URL    = f"{BASE_URL}/api/user/register"
BULK_READ_URL   = f"{BASE_URL}/meter/bulk_readings"
USER_QUERY_URL  = f"{BASE_URL}/api/user/query"
STOPSERVER_URL  = f"{BASE_URL}/stopserver"
BACKUP_URL      = f"{BASE_URL}/get_backup"
LOGS_URL        = f"{BASE_URL}/get_logs"
BILLING_URL     = f"{BASE_URL}/api/billing"  # Monthly billing API

# Redis 连接
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# 生成 10 个测试电表ID：100000001 ~ 100000010
TEST_METER_IDS = [str(100000000 + i) for i in range(1, 11)]

# # 模拟数据上传：原设半小时一次，但为了测试缩短为 30 秒之间上传一次
# # 这里“模拟时间间隔”用于生成记录中的时间戳（仍保持半小时步长），而实际发送间隔设为 30 秒
# SIMULATED_TIME_INTERVAL_MINUTES = 30  # 每个时间戳间隔30分钟
# UPLOAD_DELAY_SECONDS = 30             # 实际发送数据之间等待30秒

# 全局变量，用于记录每个电表上一次的读数（测试开始前重置为空字典）
last_readings = {}

def register_meter(meter_id):
    payload = {
        "meter_id": meter_id,
        "region": "Central Region",
        "area": "Bishan",
        "dwelling_type": "3-room"
    }
    resp = requests.post(REGISTER_URL, json=payload)
    return resp.json()

def get_last_reading_from_redis(meter_id):
    key = f"meter:{meter_id}:last_reading"
    value = r.get(key)
    if value:
        try:
            return float(value)
        except Exception:
            return None
    return None

def prepare_bulk_readings_for_timestamp(meter_ids, timestamp):
    """
    为指定时间戳生成所有电表数据(同一时间戳下的100个记录)。
    """
    records = []
    for meter_id in meter_ids:
        # 先尝试从 Redis 获取上次读数（纯数字）
        if meter_id not in last_readings:
            last = get_last_reading_from_redis(meter_id)
            if last is not None:
                last_readings[meter_id] = {"reading": last, "seq": 1}
            else:
                last_readings[meter_id] = {"reading": round(random.uniform(100, 200), 2), "seq": 1}
        else:
            # 累加随机增量
            increment = round(random.uniform(0.5, 2), 2)
            last_readings[meter_id]["reading"] = round(last_readings[meter_id]["reading"] + increment, 2)
            last_readings[meter_id]["seq"] += 1

        record = {
            "meter_id": meter_id,
            "timestamp": timestamp.isoformat(),
            "reading": last_readings[meter_id]["reading"],
            "seq": last_readings[meter_id]["seq"]
        }
        records.append(record)

        # 注：这里不再同步更新 Redis 中的最后读数，
        # 后台工作进程会通过 Lua 脚本进行原子更新和消费量计算。
        # key = f"meter:{meter_id}:last_reading"
        # r.set(key, str(last_readings[meter_id]["reading"]))

    return records

def send_bulk_meter_readings(readings):
    resp = requests.post(BULK_READ_URL, json=readings)
    return resp.json()

def query_meter(meter_id, period):
    params = {"meter_id": meter_id, "period": period}
    resp = requests.get(USER_QUERY_URL, params=params)
    return resp.json()

def stop_server():
    resp = requests.get(STOPSERVER_URL)
    return resp.json()

def get_backup(date=None):
    params = {}
    if date:
        params["date"] = date
    resp = requests.get(BACKUP_URL, params=params)
    return resp.json()

def get_logs(log_type="daily_jobs", limit=5, date=None):
    params = {"log_type": log_type, "limit": limit}
    if date:
        params["date"] = date
    resp = requests.get(LOGS_URL, params=params)
    return resp.json()

def get_billing(meter_id, month):
    params = {"meter_id": meter_id, "month": month}
    resp = requests.get(BILLING_URL, params=params)
    return resp.json()

def simulate_backup_and_logs(date_obj):
    """
    模拟当天的备份数据和日志：
    - 备份数据存储在 Redis 键:backup:meter_data:YYYY-MM-DD
    - 日志存储在 Redis 列表:logs:daily_jobs
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    backup_data = {}
    for meter_id in TEST_METER_IDS:
        backup_data[meter_id] = round(random.uniform(5, 20), 2)
    backup_key = f"backup:meter_data:{date_str}"
    r.hset(backup_key, mapping=backup_data)
    
    log_key = "logs:daily_jobs"
    for i in range(3):
        log_timestamp = f"{date_str}T{10+i:02d}:00:00"
        log_entry = json.dumps({
            "timestamp": log_timestamp,
            "log_type": "daily_jobs",
            "message": f"Simulated log entry {i+1} for {date_str}",
            "service": "BackupService"
        })
        r.rpush(log_key, log_entry)

if __name__ == "__main__":
    print("===== Test Script Start =====\n")

    # 重置全局变量，确保数据连续
    last_readings = {}

    # 注册所有电表
    print("[Test] Registering 100 meter IDs:")
    for mid in TEST_METER_IDS:
        res = register_meter(mid)
        print(f"  Meter {mid} registration: {res.get('message', res)}")
    
    # # 模拟数据上传：
    # # 假设我们只模拟一天数据，比如2025-02-18这一天
    test_day = datetime(2025, 2, 20)
    # batches_per_day = 48  # 原来一天48个半小时时刻

    # print(f"\n[Test] Sending bulk readings for all 100 meters for {test_day.strftime('%Y-%m-%d')}:")
    # # 从当天00:00开始
    # simulated_start = datetime(test_day.year, test_day.month, test_day.day, 0, 0, 0)
    # for batch in range(batches_per_day):
    #     # 每批次的时间戳按半小时递增
    #     batch_time = simulated_start + timedelta(minutes=SIMULATED_TIME_INTERVAL_MINUTES * batch)
    #     # 对同一时间点生成所有电表的数据（100条记录）
    #     batch_records = prepare_bulk_readings_for_timestamp(TEST_METER_IDS, batch_time)
    #     # 发送一个批次（所有电表同一时间戳数据一次性上传）
    #     result = send_bulk_meter_readings(batch_records)
    #     print(f"[Test] Batch {batch+1:02d} at {batch_time.isoformat()} sent, result: {result}")
    #     # 为保证数据按顺序处理，每个批次间隔一定时间
    #     time.sleep(UPLOAD_DELAY_SECONDS)
    
    # 新增：只上传一个批次数据（单个时间戳下所有电表数据），并计时
    print("\n[Test] Uploading one batch (single timestamp) for all meters and measuring time:")
    single_batch_time = datetime(2025, 2, 20, 00, 00)  # 指定一个固定时间
    single_batch_records = prepare_bulk_readings_for_timestamp(TEST_METER_IDS, single_batch_time)
    start_time = time.time()
    single_result = send_bulk_meter_readings(single_batch_records)
    elapsed = time.time() - start_time
    print(f"[Test] Single batch at {single_batch_time.isoformat()} sent, result: {single_result}")
    print(f"[Test] Uploading single batch took {elapsed:.2f} seconds.")
    # 模拟当天的备份和日志
    simulate_backup_and_logs(test_day)
    
    print("\n[Test] Waiting 20 seconds to allow background worker to finish processing remaining data...")
    time.sleep(20)
    
    # 查询3 个电表的 30m（模拟“30分钟”）数据和 1d数据
    print("\n[Test] Querying usage data (30-minute & 1-day) for 3 meters:")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        r1d = query_meter(mid, "1d")
        print(f"  Meter {mid} 30m query: {r30}")
        print(f"  Meter {mid} 1d query: {r1d}")
    
    # 测试备份、日志和月度账单接口
    test_date = "2025-02-19"
    print(f"\n[Test] Viewing backup data for date {test_date}:")
    backup_result = get_backup(date=test_date)
    print(f"  Backup data: {backup_result}")
    
    print(f"\n[Test] Viewing logs (daily_jobs) for date {test_date}:")
    logs_result = get_logs("daily_jobs", 100, date=test_date)
    print(f"  Logs: {logs_result}")
    
    test_month = "2025-02"
    print(f"\n[Test] Testing monthly billing API BEFORE maintenance mode for month {test_month}:")
    for mid in TEST_METER_IDS[:3]:
        billing_result = get_billing(mid, test_month)
        print(f"  Billing for Meter {mid} in {test_month}: {billing_result}")
    
    print("\n[Test] Triggering maintenance mode by calling stop_server...")
    maint_result = stop_server()
    print(f"  stop_server response: {maint_result}")
    
    print("\n[Test] Sending bulk readings during maintenance mode for first 3 meters:")
    maint_start = datetime(2025, 2, 20, 12, 0, 0)  # 示例时间
    for mid in TEST_METER_IDS[:3]:
        # 此处为单个电表当天数据（可只取一批次数据）
        bulk_data = prepare_bulk_readings_for_timestamp([mid], maint_start)
        result = send_bulk_meter_readings(bulk_data)
        print(f"  Meter {mid} bulk upload during maintenance: {result}")
    
    MAINTENANCE_WAIT = 30
    print(f"\n[Test] Waiting {MAINTENANCE_WAIT} seconds for maintenance mode to complete...")
    time.sleep(MAINTENANCE_WAIT + 5)
    
    print("[Test] Querying usage data (30-minute & 1-day) for first 3 meters AFTER maintenance mode:")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        r1d = query_meter(mid, "1d")
        print(f"  Meter {mid} 30m query: {r30}")
        print(f"  Meter {mid} 1d query: {r1d}")
    
    print(f"\n[Test] Testing monthly billing API AFTER maintenance mode for month {test_month}:")
    for mid in TEST_METER_IDS[:3]:
        billing_result = get_billing(mid, test_month)
        print(f"  Billing for Meter {mid} in {test_month}: {billing_result}")
        
    print(f"\n[Test] Viewing backup data for date {test_date} after restart:")
    backup_result = get_backup(date=test_date)
    print(f"  Backup data: {backup_result}")
    
    print(f"\n[Test] Viewing logs (daily_jobs) for date {test_date} after restart:")
    logs_result = get_logs("daily_jobs", 100, date=test_date)
    print(f"  Logs: {logs_result}")
    
    print("\n===== Test Script Finished =====")
