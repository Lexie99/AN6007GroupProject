# test.py

import os
import time
import random
import requests
import redis
import argparse
from datetime import datetime, timedelta

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
MAINTENANCE_WAIT = 60  # 维护模式等待时间

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
    #r.flushall() 谨慎选择，这是一键全删

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

def send_multiple_meter_readings(meter_id, start_time, count=5, interval_seconds=600):
    """
    批量发送指定电表的读数，起始时间为 start_time,每条记录之间间隔 interval_seconds 秒。
    如果 start_time 是字符串，则尝试转换为 datetime 对象。
    返回一个列表，每个元素为 (时间戳, API 返回结果)。
    """
    from datetime import datetime, timedelta
    
    # 如果 start_time 是字符串，则转换
    if isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time)
        except Exception as e:
            raise ValueError(f"Invalid start_time format: {start_time}. Error: {e}")

    responses = []
    current_time = start_time
    for i in range(count):
        resp = send_meter_reading(meter_id, timestamp=current_time)
        responses.append((current_time.isoformat(), resp))
        current_time += timedelta(seconds=interval_seconds)
        time.sleep(0.1)  # 模拟较短的间隔，避免发送过快
    return responses


def query_meter(meter_id, period):
    params = {"meter_id": meter_id, "period": period}
    resp = requests.get(USER_QUERY_URL, params=params)
    return resp.json()

def stop_server():
    resp = requests.get(STOPSERVER_URL)
    return resp.json()

def get_backup(date=None):
    """
    获取指定日期的备份数据
    参数:
      - date: 可选，日期字符串，格式为 "YYYY-MM-DD"。如果不传，则由后端默认处理（通常为昨天）。
    """
    params = {}
    if date:
        params["date"] = date
    resp = requests.get(BACKUP_URL, params=params)
    return resp.json()

def get_logs(log_type="daily_jobs", limit=5, date=None):
    """
    获取日志数据
    参数:
      - log_type: 日志类型（默认为 "daily_jobs")
      - limit: 限制返回的日志条数
      - date: 可选，日期字符串，格式为 "YYYY-MM-DD"，如果后端支持日期过滤，可传入。
    """
    params = {"log_type": log_type, "limit": limit}
    if date:
        params["date"] = date
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

    print("[Test] 批量发送多个时间戳的电表读数...")
    # 使用自定义起始时间，从 custom_start 开始，每隔1分钟发送一条，共发送5条
    for mid in TEST_METER_IDS[:3]:  # 这里只选前三个电表作为示例
        responses = send_multiple_meter_readings(mid, start_time="2025-02-13T11:30:00", count=5, interval_seconds=60)
        for ts, resp in responses:
            print(f"  meter {mid} @ {ts} =>", resp)
        time.sleep(0.5)

    print("[Test] 查询30m与1d数据")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        print(f"  {mid} 30m =>", r30)
        r1d = query_meter(mid, "1d")
        print(f"  {mid} 1d =>", r1d)

    print("[Test] 测试维护模式效果...")
    print("[Test] 调用 stop_server 进入维护模式")
    ret_maint = stop_server()
    print("  stop_server =>", ret_maint)

    # 在维护模式期间，尝试发送电表读数，验证返回是否进入 pending 队列
    print("[Test] 在维护模式期间发送读数...")
    for mid in TEST_METER_IDS[:3]:
        resp = send_meter_reading(mid)
        print(f"  meter {mid} =>", resp)
    # 同时查询 30m 数据（pending 数据可能尚未转入 history）
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        print(f"  (维护模式) {mid} 30m =>", r30)

    print(f"[Test] 等待 {MAINTENANCE_WAIT} 秒（维护模式持续时间）...")
    time.sleep(MAINTENANCE_WAIT + 5)  # 多等待几秒确保维护模式结束

    print("[Test] 维护模式结束后，再次发送读数...")
    for mid in TEST_METER_IDS[:3]:
        resp = send_meter_reading(mid)
        print(f"  meter {mid} =>", resp)

    print("[Test] 查询30m与1d数据(维护模式后)")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        print(f"  {mid} 30m =>", r30)
        r1d = query_meter(mid, "1d")
        print(f"  {mid} 1d =>", r1d)

    print("[Test] 查看昨日备份:")
    print(get_backup())

    print("[Test] 查看日志(daily_jobs):")
    print(get_logs("daily_jobs", 5))

    print("===== 测试脚本结束 =====")
