import os
import time
import random
import requests
import redis
from datetime import datetime

# ========== 基本配置 ==========
API_BASE_URL   = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")

# 常用接口
REGISTER_URL   = f"{API_BASE_URL}/api/user/register"
METER_READ_URL = f"{API_BASE_URL}/meter/reading"
USER_QUERY_URL = f"{API_BASE_URL}/api/user/query"
STOPSERVER_URL = f"{API_BASE_URL}/stopserver"
GET_LOGS_URL   = f"{API_BASE_URL}/get_logs"
GET_BACKUP_URL = f"{API_BASE_URL}/get_backup"

REDIS_HOST     = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT     = int(os.getenv("REDIS_PORT", 6379))

# 测试用户 / 电表
TEST_METER_IDS = ["300000001", "300000002"]
READ_COUNT     = 5   # 每个电表发送多少条读数

# 日志类型
LOG_TYPE       = "daily_jobs"
LOG_LIMIT      = 5   # 查看最近 5 条日志

# 如果想固定时间戳(便于验证查询), 写死字符串，如 "2025-02-15T09:00:00"
CUSTOM_TIMESTAMP = None

# ========== Redis 连接 ==========
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# ========== 测试辅助函数 ==========

def clear_old_data():
    """
    选择性地删除测试相关的数据:
      - all_users
      - meter:*  (读数)
      - user_data:* (用户注册信息)
    如要彻底清空, 可以 r.flushdb()
    """
    print("\n[STEP] 清理Redis旧数据...")

    #如果要选择性清空, 注释下面的彻底删除, 改为
    r.flushdb()
    print("  [警告] 执行 flushdb, Redis全部被清空!")
    return

    # # 1) 删除 all_users
    # if r.exists("all_users"):
    #     r.delete("all_users")
    #     print("  已删除哈希 all_users")

    # # 2) 删除 meter:* 
    # m_keys = r.scan_iter("meter:*")
    # count_m = 0
    # for k in m_keys:
    #     r.delete(k)
    #     count_m += 1
    # print(f"  已删除 meter:* {count_m} 个Key")

    # # 3) 删除 user_data:*
    # u_keys = r.scan_iter("user_data:*")
    # count_u = 0
    # for k in u_keys:
    #     r.delete(k)
    #     count_u += 1
    # print(f"  已删除 user_data:* {count_u} 个Key")


def get_timestamp():
    if CUSTOM_TIMESTAMP:
        return CUSTOM_TIMESTAMP
    return datetime.now().isoformat()


def test_register_users():
    """
    注册多个电表用户
    如果你的后端需要校验 region/area/dwelling_type 合法性, 这里要写成真实值
    """
    print("\n[TEST] 注册用户 =>", REGISTER_URL)
    sample_region   = "Central Region"  # 需在 config.json 有此 region
    sample_area     = "Bedok"           # config.json area
    sample_dwelling = "3-room"          # config.json dwelling_type

    for mid in TEST_METER_IDS:
        payload = {
            "meter_id": mid,
            "region": sample_region,
            "area": sample_area,
            "dwelling_type": sample_dwelling
        }
        try:
            resp = requests.post(REGISTER_URL, json=payload)
            data = resp.json()
            status = data.get("status")
            msg = data.get("message")
            if status == "success":
                print(f"  MeterID={mid} 注册成功: {msg}")
            else:
                print(f"  MeterID={mid} 注册失败: {msg}")
        except Exception as e:
            print(f"  MeterID={mid} 注册异常: {e}")


def test_meter_readings():
    """
    模拟给每个电表发送多次读数 (递增)
    """
    print("\n[TEST] 提交电表读数 =>", METER_READ_URL)

    # 初始化每个电表起始读数
    current_vals = { mid: round(random.uniform(50, 100), 2) for mid in TEST_METER_IDS }

    for i in range(READ_COUNT):
        print(f"  [第 {i+1} 次读数提交]")
        for mid in TEST_METER_IDS:
            # 读数增加随机值
            increment = round(random.uniform(2.0, 5.0), 2)
            current_vals[mid] += increment

            payload = {
                "meter_id": mid,
                "timestamp": get_timestamp(),
                "reading": current_vals[mid]
            }
            try:
                resp = requests.post(METER_READ_URL, json=payload)
                if resp.status_code == 200:
                    print(f"    Meter {mid} => {current_vals[mid]}, 状态: OK")
                else:
                    print(f"    Meter {mid}, 状态码: {resp.status_code}, 响应: {resp.text}")
            except Exception as e:
                print(f"    Meter {mid}, 请求异常: {e}")

        # 提交完一次可暂停几秒, 避免瞬间提交太多
        time.sleep(1)


def test_query_usage():
    """
    测试 /api/user/query:
      - 30m
      - 1d
    这里只测试一个电表
    """
    print("\n[TEST] 查询电表用电量 =>", USER_QUERY_URL)
    test_meter = TEST_METER_IDS[0]

    # 30 分钟增量
    params_30m = {
        "meter_id": test_meter,
        "period": "30m"
    }
    try:
        resp = requests.get(USER_QUERY_URL, params=params_30m)
        data = resp.json()
        print(f"  查询 30m 增量, 响应: {data}")
    except Exception as e:
        print("  查询异常:", e)

    # 1 天
    params_1d = {
        "meter_id": test_meter,
        "period": "1d"
    }
    try:
        resp = requests.get(USER_QUERY_URL, params=params_1d)
        data = resp.json()
        print(f"  查询 1d 数据, 响应: {data}")
    except Exception as e:
        print("  查询异常:", e)


def test_stop_server():
    """
    测试维护模式 => /stopserver
    """
    print("\n[TEST] 进入维护模式 =>", STOPSERVER_URL)
    try:
        resp = requests.get(STOPSERVER_URL)
        data = resp.json()
        print("  响应:", data)
        # 若成功, 等待一小会, 等维护结束
        # 具体等待时长可根据 daily_jobs_api.py 的 MAINTENANCE_DURATION 调整
        time.sleep(10)  # 等待10秒或更多, 看你的配置
    except Exception as e:
        print("  维护模式调用异常:", e)


def test_get_logs():
    """
    测试 /get_logs => 获取日志
    """
    print("\n[TEST] 获取日志 =>", GET_LOGS_URL)
    params = {"log_type": "daily_jobs", "limit": "5"}
    try:
        resp = requests.get(GET_LOGS_URL, params=params)
        data = resp.json()
        print(f"  最新daily_jobs日志: {data}")
    except Exception as e:
        print("  日志查询异常:", e)


def test_get_backup():
    """
    测试 /get_backup => 获取指定或默认日期备份
    默认获取昨天
    """
    print("\n[TEST] 获取备份数据 =>", GET_BACKUP_URL)
    try:
        resp = requests.get(GET_BACKUP_URL)
        data = resp.json()
        print(f"  备份查询结果: {data}")
    except Exception as e:
        print("  备份查询异常:", e)


def main():
    print("========== 测试脚本启动 ==========")

    # 1) 清空与测试相关的Redis数据
    #！！！！！谨慎核对上面的清理逻辑！！！！！现在是彻底删除！！！！！
    clear_old_data()

    # 2) 注册用户
    test_register_users()

    # 3) 提交电表读数
    test_meter_readings()

    # 4) 查询电表用电量
    test_query_usage()

    # 5) 进入维护模式(可选)
    test_stop_server()

    # 6) 查看日志(若有 /get_logs)
    test_get_logs()

    # 7) 查看备份(若有 /get_backup)
    test_get_backup()

    print("========== 测试脚本结束 ==========")


if __name__ == "__main__":
    main()
