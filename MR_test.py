import requests
from datetime import datetime

url = 'http://127.0.0.1:8000/meter/reading'
data = {
    "timestamp": datetime.now().isoformat(),
    "reading": 150,
    "meter_id": "1"
}

response = requests.post(url, json=data)
print("Status Code:", response.status_code)
print("Response Text:", response.text)
