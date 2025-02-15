# test.py

import os
import time
import random
import requests
import redis
from datetime import datetime

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")

REGISTER_URL    = f"{BASE_URL}/api/user/register"
METER_READ_URL  = f"{BASE_URL}/meter/reading"
USER_QUERY_URL  = f"{BASE_URL}/api/user/query"
STOPSERVER_URL  = f"{BASE_URL}/stopserver"
BACKUP_URL      = f"{BASE_URL}/get_backup"
LOGS_URL        = f"{BASE_URL}/get_logs"

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

TEST_METER_IDS = [
    "100000001", "100000002", "100000003", "100000004", "100000005",
    "100000006", "100000007", "100000008", "100000009", "100000010",
    "100000011", "100000012", "100000013", "100000014", "100000015",
    "100000016", "100000017", "100000018", "100000019", "100000020"
]
READ_TIMES = 3
MAINTENANCE_WAIT = 60

# 全局变量，用于记录每个电表的上一次读数
last_readings = {}

def clear_test_data():
    """
    删除 all_users, meter:* 以及 user_data:* 相关的 Redis Key
    """
    if r.exists("all_users"):
        r.delete("all_users")
    meter_keys = list(r.scan_iter("meter:*"))
    for mk in meter_keys:
        r.delete(mk)
    user_keys = list(r.scan_iter("user_data:*"))
    for uk in user_keys:
        r.delete(uk)

def register_meter(meter_id):
    payload = {
        "meter_id": meter_id,
        "region": "Central Region",
        "area": "Bishan",
        "dwelling_type": "3-room"
    }
    resp = requests.post(REGISTER_URL, json=payload)
    return resp.json()

def send_meter_reading(meter_id, timestamp=None):
    """
    发送电表读数，每次读数基于上一次随机增加。
    
    参数:
      - meter_id: 电表编号
      - timestamp: 可选，指定的上报时间（支持 datetime 对象或 ISO 格式字符串），
                   若未提供则使用当前时间。
    """
    # 初始化或更新读数
    if meter_id not in last_readings:
        last_readings[meter_id] = round(random.uniform(100, 200), 2)
    else:
        # 在上一次的基础上增加一个随机增量（0到10之间）
        increment = round(random.uniform(0, 10), 2)
        last_readings[meter_id] = round(last_readings[meter_id] + increment, 2)
    reading = last_readings[meter_id]

    # 设置时间戳，支持自定义时间
    if timestamp is None:
        ts = datetime.now().isoformat()
    else:
        ts = timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp

    payload = {
        "meter_id": meter_id,
        "timestamp": ts,
        "reading": reading
    }
    resp = requests.post(METER_READ_URL, json=payload)
    return resp.json()

def query_meter(meter_id, period):
    params = {"meter_id": meter_id, "period": period}
    resp = requests.get(USER_QUERY_URL, params=params)
    return resp.json()

def stop_server():
    resp = requests.get(STOPSERVER_URL)
    return resp.json()

def get_backup():
    resp = requests.get(BACKUP_URL)
    return resp.json()

def get_logs(log_type="daily_jobs", limit=5):
    params = {"log_type": log_type, "limit": limit}
    resp = requests.get(LOGS_URL, params=params)
    return resp.json()

if __name__ == "__main__":
    print("===== 测试脚本开始 =====")

    #print("[Test] 清理旧数据...")
    #clear_test_data()

    print("[Test] 注册 meter_id...")
    for mid in TEST_METER_IDS:
        res = register_meter(mid)
        print(f"  register {mid} =>", res)

       
    print("[Test] 发送电表读数...")
    custom_timestamp_str = "2025-02-13T12:30:00"
    for i in range(READ_TIMES):
        for mid in TEST_METER_IDS:
            # 可选：自定义时间，例如传入指定的时间字符串或 datetime 对象
            ret = send_meter_reading(mid,timestamp=custom_timestamp_str)
            print(f"  meter {mid} =>", ret)
        time.sleep(1)

    print("[Test] 查询30m与1d")
    for mid in TEST_METER_IDS:
        r30 = query_meter(mid, "30m")
        print(" 30m =>", r30)
        r1d = query_meter(mid, "1d")
        print(" 1d =>", r1d)

    print("[Test] 进入维护模式...")
    ret_maint = stop_server()
    print(" =>", ret_maint)
    time.sleep(MAINTENANCE_WAIT)  # 等待维护结束

    print("[Test] 查看昨日备份:")
    print(get_backup())

    print("[Test] 查看日志(daily_jobs):")
    print(get_logs("daily_jobs", 5))

    print("===== 测试脚本结束 =====")
