import json
import redis
from flask import request, jsonify
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def meter_reading_api(app):
    @app.route('/meter/reading', methods=['POST'])
    def receive_reading():
        """
        处理电表读数，数据存入 Redis
        """
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            timestamp = data.get('timestamp')
            reading = float(data.get('reading'))

            if not r.hexists("all_users", meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            timestamp_iso = datetime.fromisoformat(timestamp).isoformat()
            timestamp_unix = datetime.fromisoformat(timestamp).timestamp()

            # 存入 Redis Sorted Set (时间序列数据)
            r.zadd(f"meter:{meter_id}:history", {json.dumps({"timestamp": timestamp_iso, "reading_value": reading}): timestamp_unix})

            return jsonify({'status': 'success'})

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
