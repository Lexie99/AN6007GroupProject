# test.py
import requests
import time
import random
from datetime import datetime, timedelta
#this is the test file,should be run in different terminal from app.py, or it will cause the meter_data be changed
#can remove the 1. part in later version

# ---------------------------
# 1. 生成虚拟数据用于展示 query 结果
# ---------------------------
# 这里直接尝试导入 api.py 中的 meter_data 进行数据初始化
try:
    from api import meter_data
    def generate_virtual_query_data():
        if "000000001" not in meter_data or not meter_data["000000001"]:
            now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            meter_data["000000001"] = []
            for i in range(48):
                t = now + timedelta(minutes=i * 30)
                meter_data["000000001"].append({
                    "timestamp": t.strftime("%Y-%m-%d %H:%M"),
                    "reading": random.randint(100, 500)
                })
            print("Virtual query data generated for meter 000000001.")
        else:
            print("Meter 000000001 already has data.")
    
    # 调用生成虚拟数据（仅适用于在同一进程测试时使用）
    generate_virtual_query_data()
except ImportError:
    print("can't import meter_data from api.py")

# ---------------------------
# 2. 模拟电表读数数据上传
# ---------------------------
def simulate_meter_readings():
    # 注意：本示例中 API 端口为 8050，如果不是请修改为实际端口
    url = 'http://127.0.0.1:8050/meter/reading'
    
    current_reading = 200
    # 固定起始时间（例如 2025-02-12 10:00:00）
    fixed_start_time = datetime(2025, 2, 12, 10, 0, 0)
    
    # 模拟 6 次数据上传
    for i in range(6):
        # 固定时间，每次增加 30 分钟
        timestamp = (fixed_start_time + timedelta(minutes=i * 30)).isoformat()
        data = {
            "timestamp": timestamp,
            "reading": current_reading,
            "meter_id": "99999999"
        }
        
        try:
            response = requests.post(url, json=data)
            print(f"Iteration {i + 1}:")
            print("Status Code:", response.status_code)
            print("Response Text:", response.text)
        except Exception as e:
            print(f"Iteration {i + 1}: Request failed with error: {e}")
        
        current_reading += 5  # 模拟读数递增
        if i < 5:
            # 等待 30 秒后再上传下一条数据（可根据需要调整等待时间）
            time.sleep(30)

if __name__ == '__main__':
    print("开始模拟电表读数上传测试……")
    simulate_meter_readings()
