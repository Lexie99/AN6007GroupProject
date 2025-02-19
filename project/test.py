import os
import time
import random
import requests
import redis
import json
from datetime import datetime, timedelta

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")

REGISTER_URL    = f"{BASE_URL}/api/user/register"
BULK_READ_URL   = f"{BASE_URL}/meter/bulk_readings"
USER_QUERY_URL  = f"{BASE_URL}/api/user/query"
STOPSERVER_URL  = f"{BASE_URL}/stopserver"
BACKUP_URL      = f"{BASE_URL}/get_backup"
LOGS_URL        = f"{BASE_URL}/get_logs"
BILLING_URL     = f"{BASE_URL}/api/billing"  # Monthly billing API

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# 生成 100 个测试电表ID：100000001 ~ 100000100
TEST_METER_IDS = [str(100000000 + i) for i in range(1, 101)]

# 模拟数据上传间隔：30 分钟
TIME_INTERVAL_SECONDS = 1800  # 1800 秒 = 30 分钟

# 用于生成模拟数据时记录每个电表上一次读数的全局变量
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

def prepare_bulk_readings_for_batch(meter_ids, batch_start_time):
    """
    为一批电表生成一组读数数据，每条记录包含 meter_id, timestamp 和 reading。
    """
    batch_data = []
    for meter_id in meter_ids:
        if meter_id not in last_readings:
            last_readings[meter_id] = round(random.uniform(100, 200), 2)
        else:
            increment = round(random.uniform(0, 10), 2)
            last_readings[meter_id] = round(last_readings[meter_id] + increment, 2)
        record = {
            "meter_id": meter_id,
            "timestamp": batch_start_time.isoformat(),
            "reading": last_readings[meter_id]
        }
        batch_data.append(record)
    return batch_data

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
    模拟当天的备份数据和日志
    - 备份数据存储在 Redis 键名:backup:meter_data:YYYY-MM-DD
    - 日志存储在 Redis 列表键名:logs:daily_jobs
    """
    date_str = date_obj.strftime("%Y-%m-%d")
    
    # 模拟备份数据：每个电表对应一个随机的用电量（单位 kWh）
    backup_data = {}
    for meter_id in TEST_METER_IDS:
        backup_data[meter_id] = round(random.uniform(5, 20), 2)
    backup_key = f"backup:meter_data:{date_str}"
    r.hset(backup_key, mapping=backup_data)
    
    # 模拟日志：生成 3 条日志记录，每条记录包含当天的时间戳
    log_key = "logs:daily_jobs"
    for i in range(3):
        # 生成当天不同时间的日志，例如 10:00, 11:00, 12:00
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

    # 注册所有电表并打印注册结果
    print("[Test] Registering 100 meter IDs:")
    for mid in TEST_METER_IDS:
        res = register_meter(mid)
        print(f"  Meter {mid} registration: {res.get('message', res)}")
    
    # 模拟从 2025-02-01 到 2025-02-19，每天每隔半小时上传一次数据
    start_date = datetime(2025, 2, 1)
    end_date = datetime(2025, 2, 19)
    interval_minutes = 30
    batches_per_day = 24 * 60 // interval_minutes  # 每天 48 个批次

    current_date = start_date
    print(f"\n[Test] Sending bulk readings for all 100 meters from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}:")
    while current_date <= end_date:
        # 每天从 00:00 开始
        simulated_start = datetime(current_date.year, current_date.month, current_date.day, 0, 0, 0)
        for batch in range(batches_per_day):
            batch_time = simulated_start + timedelta(minutes=interval_minutes * batch)
            bulk_data = prepare_bulk_readings_for_batch(TEST_METER_IDS, batch_time)
            result = send_bulk_meter_readings(bulk_data)
            print(f"  Date {current_date.strftime('%Y-%m-%d')} Batch {batch+1:02d} (timestamp: {batch_time.isoformat()}) bulk upload result: {result}")
        # 模拟每天的备份数据和日志
        simulate_backup_and_logs(current_date)
        current_date += timedelta(days=1)

    # 增加等待时间，确保后台 worker 有足够时间处理队列数据并写入历史记录
    print("\n[Test] Waiting 10 seconds to allow background worker to process data...")
    time.sleep(20)

    # 查询前3个电表的 30m 和 1d 数据
    print("\n[Test] Querying usage data (30-minute & 1-day) for first 3 meters:")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        r1d = query_meter(mid, "1d")
        print(f"  Meter {mid} 30m query: {r30}")
        print(f"  Meter {mid} 1d query: {r1d}")

    # 测试 backup 和 log API
    test_date = "2025-02-17"
    print(f"\n[Test] Viewing backup data for date {test_date}:")
    backup_result = get_backup(date=test_date)
    print(f"  Backup data: {backup_result}")
    print(f"\n[Test] Viewing logs (daily_jobs) for date {test_date}:")
    logs_result = get_logs("daily_jobs", 100, date=test_date)
    print(f"  Logs: {logs_result}")

    # 维护模式前测试月度账单 API
    test_month = "2025-02"
    print(f"\n[Test] Testing monthly billing API BEFORE maintenance mode for month {test_month}:")
    for mid in TEST_METER_IDS[:3]:
        billing_result = get_billing(mid, test_month)
        print(f"  Billing for Meter {mid} in {test_month}: {billing_result}")

    # 触发维护模式
    print("\n[Test] Triggering maintenance mode by calling stop_server...")
    maint_result = stop_server()
    print(f"  stop_server response: {maint_result}")

    # 在维护模式期间，通过 bulk 接口发送数据（仅测试前3个电表）
    print("\n[Test] Sending bulk readings during maintenance mode for first 3 meters:")
    maint_start = datetime(2025, 2, 19, 12, 0, 0)  # 示例时间
    for mid in TEST_METER_IDS[:3]:
        bulk_data = prepare_bulk_readings_for_batch([mid], maint_start)
        result = send_bulk_meter_readings(bulk_data)
        print(f"  Meter {mid} bulk upload during maintenance: {result}")

    # 等待维护模式结束
    MAINTENANCE_WAIT = 60  # 维护模式等待时间（秒）
    print(f"\n[Test] Waiting {MAINTENANCE_WAIT} seconds for maintenance mode to complete...")
    time.sleep(MAINTENANCE_WAIT + 5)

    # 维护模式结束后查询前3个电表的 30m 和 1d 数据
    print("[Test] Querying usage data (30-minute & 1-day) for first 3 meters AFTER maintenance mode:")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        r1d = query_meter(mid, "1d")
        print(f"  Meter {mid} 30m query: {r30}")
        print(f"  Meter {mid} 1d query: {r1d}")

    # 维护模式后再次测试月度账单 API
    print(f"\n[Test] Testing monthly billing API AFTER maintenance mode for month {test_month}:")
    for mid in TEST_METER_IDS[:3]:
        billing_result = get_billing(mid, test_month)
        print(f"  Billing for Meter {mid} in {test_month}: {billing_result}")
        
    # 同时验证 backup 和 logs 数据在“重启”后仍然可用
    print(f"\n[Test] Viewing backup data for date {test_date} after restart:")
    backup_result = get_backup(date=test_date)
    print(f"  Backup data: {backup_result}")
    print(f"\n[Test] Viewing logs (daily_jobs) for date {test_date} after restart:")
    logs_result = get_logs("daily_jobs", 100, date=test_date)
    print(f"  Logs: {logs_result}")

    print("\n===== Test Script Finished =====")
