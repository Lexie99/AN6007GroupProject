import requests
import time
from datetime import datetime

url = 'http://127.0.0.1:8000/meter/reading'

current_reading = 200


for i in range(6):
    # 构造数据：使用当前时间和当前读数
    data = {
        "timestamp": datetime.now().isoformat(),#不要取当前时间，直接自己设定固定的时间，不然数据写入会很慢
        "reading": current_reading,
        "meter_id": "000000001"
    }
    
    # 发送 POST 请求
    response = requests.post(url, json=data)
    
    print(f"Iteration {i+1}:")
    print("Status Code:", response.status_code)
    print("Response Text:", response.text)
    
    # 更新读数（例如每次增加 5）
    current_reading += 5
    
    # 如果不是最后一次，则等待 30 秒
    if i < 5:
        time.sleep(30)
