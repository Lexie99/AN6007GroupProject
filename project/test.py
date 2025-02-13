import time
import random
import requests
import redis
from datetime import datetime

# 连接 Redis，从中获取 meter ID
r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# 电表读数接口地址
API_URL = "http://127.0.0.1:8050/meter/reading"

# 用于存储每个电表当前的累计读数
meter_readings = {}

# 自定义时间戳设置
# 如果希望每次发送固定或自定义的时间戳，请将 CUSTOM_TIMESTAMP 设置为一个符合 ISO 格式的字符串，
# 如 "2025-02-13T12:00:00"。如果设置为 None，则每次发送数据时使用当前时间。
CUSTOM_TIMESTAMP = "2025-02-14T12:00:00"

def get_meter_ids():
    """
    从 Redis 的 all_users 哈希中获取所有 meter ID
    """
    meter_ids = r.hkeys("all_users")
    if not meter_ids:
        print("未在 Redis 的 all_users 中找到任何 meter ID。")
    return meter_ids

def get_timestamp():
    """
    如果 CUSTOM_TIMESTAMP 不为 None，则使用它；否则返回当前时间的 ISO 格式字符串。
    """
    return CUSTOM_TIMESTAMP if CUSTOM_TIMESTAMP else datetime.now().isoformat()

def simulate_meter_reading():
    """
    为每个 meter ID 在上次的基础上增加一定增量，然后通过 HTTP POST 请求发送数据
    """
    meter_ids = get_meter_ids()
    if not meter_ids:
        return
    
    for meter_id in meter_ids:
        # 初始化累计读数或累加增量
        if meter_id not in meter_readings:
            meter_readings[meter_id] = round(random.uniform(100, 500), 2)
        else:
            increment = round(random.uniform(1, 10), 2)
            meter_readings[meter_id] += increment

        current_reading = meter_readings[meter_id]
        timestamp = get_timestamp()

        payload = {
            "meter_id": meter_id,
            "timestamp": timestamp,
            "reading": current_reading
        }

        try:
            response = requests.post(API_URL, json=payload)
            if response.status_code == 200:
                print(f"[{timestamp}] Meter {meter_id}: 发送读数 {current_reading} 成功。")
            else:
                print(f"[{timestamp}] Meter {meter_id}: 发送失败，状态码 {response.status_code}，响应：{response.text}")
        except Exception as e:
            print(f"[{timestamp}] Meter {meter_id}: 请求异常，错误信息：{e}")

if __name__ == "__main__":
    print("开始模拟电表读数，每30秒更新一次，每个电表共发送6次数据。")
    # 总共模拟6次数据传输
    for i in range(6):
        print(f"第 {i+1} 次传输数据:")
        simulate_meter_reading()
        if i < 5:
            time.sleep(30)
    print("测试结束。")
