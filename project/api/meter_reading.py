# api/meter_reading_api.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime
import services.state
from services.validation import validate_meter_id,validate_timestamp

def create_meter_reading_blueprint(redis_service):
    bp = Blueprint('meter_reading_api', __name__)

    @bp.route('/meter/reading', methods=['POST'])
    def receive_reading():
        """
        单条读数上报：
        - 如果在维护模式下，将数据写入 pending 队列(meter:{meter_id}:pending)
        - 否则写入正常的 readings_queue
        JSON格式: {
          "meter_id": "...",
          "timestamp": "YYYY-MM-DDTHH:MM:SS",
          "reading": 123.45
        }
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

            meter_id = data.get('meter_id')
            timestamp_str = data.get('timestamp')
            reading_val = data.get('reading')

            if not validate_meter_id(meter_id):  # 统一校验
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format'}), 400

            # 检查电表是否注册
            if not redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            record = {
                "meter_id": meter_id,
                "timestamp": timestamp_str,
                "reading": reading_val
            }
            # 判断是否处于维护模式
            if services.state.IS_MAINTENANCE:
                # 存入 pending 队列，后续由维护结束时统一处理
                key = f"meter:{meter_id}:pending"
                redis_service.client.rpush(key, json.dumps(record))
                message = "Reading stored to pending queue due to maintenance mode."
            else:
                # 正常写入 readings_queue，由后台 Worker 处理
                redis_service.client.rpush("meter:readings_queue", json.dumps(record))
                message = "Reading queued."

            return jsonify({'status': 'success', 'message': message}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/meter/bulk_readings', methods=['POST'])
    def receive_bulk_readings():
        """
        批量读数上报：
        - 根据是否处于维护模式，将数据写入 pending 队列或 readings_queue
        JSON格式: [
          {
            "meter_id": "...",
            "timestamp": "YYYY-MM-DDTHH:MM:SS",
            "reading": 123.45
          },
          ...
        ]
        """
        try:
            readings = request.get_json()
            if not isinstance(readings, list):
                return jsonify({'status': 'error', 'message': 'Input must be a JSON list'}), 400

            success_count = 0
            fail_count = 0

            # 读取当前维护状态
            maintenance_mode = services.state.IS_MAINTENANCE

            for record in readings:
                meter_id = record.get('meter_id')
                timestamp_str = record.get('timestamp')
                reading_val = record.get('reading')

                # 简单校验
                if not meter_id or not timestamp_str or reading_val is None:
                    fail_count += 1
                    continue

                # 检查电表是否注册
                if not redis_service.is_meter_registered(meter_id):
                    fail_count += 1
                    continue

                if maintenance_mode:
                    key = f"meter:{meter_id}:pending"
                    redis_service.client.rpush(key, json.dumps(record))
                else:
                    redis_service.client.rpush("meter:readings_queue", json.dumps(record))
                success_count += 1

            return jsonify({
                'status': 'success',
                'message': f'Bulk queued. success={success_count}, failed={fail_count}'
            }), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return bp
