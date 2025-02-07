from flask import Flask, request, jsonify
from datetime import datetime

# 各电表的元数据信息
user_dict = {
    "1": {"area": "Area1", "region": "Region1", "dwelling_type": "Apartment", "username": "user1", "meter_id": "000000001"},
    "2": {"area": "Area2", "region": "Region2", "dwelling_type": "House",     "username": "user2", "meter_id": "000000002"},
    "3": {"area": "Area3", "region": "Region3", "dwelling_type": "Apartment", "username": "user3", "meter_id": "000000003"}
}

# 用于存储各电表的读数数据
# 结构：{ meter_id: [ { 'timestamp': datetime对象, 'reading': 数值 }, ... ], ... }
meter_data = {}

app = Flask(__name__)

@app.route('/meter/reading', methods=['POST'])
def receive_reading():
    global user_dict, meter_data
    try:
        data = request.get_json()
        # 解析传入的字段
        meter_id = data.get('meter_id')
        timestamp_str = data.get('timestamp')
        reading = data.get('reading')

        # 校验电表 ID 是否有效
        if meter_id not in user_dict:
            return jsonify({'status': 'error', 'message': 'Invalid meter_id'}), 400

        # 将 ISO 格式的时间戳转换为 datetime 对象
        try:
            timestamp = datetime.fromisoformat(timestamp_str).strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Invalid timestamp format'}), 400

        # 如果该电表还没有数据，则初始化一个列表
        if meter_id not in meter_data:
            meter_data[meter_id] = []

        # 将本次读数记录存入对应电表的列表中
        meter_data[meter_id].append({
            'timestamp': timestamp,
            'reading': reading
        })

        # 输出调试信息之后可注释掉
        print(meter_data)
        print("Updated meter_data:")
        for mid, records in meter_data.items():
            print(f"Meter {mid}:")
            for rec in records:
                print(f"  {rec}")

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=8000)
