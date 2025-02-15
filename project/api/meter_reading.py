# api/meter_reading_api.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime

def create_meter_reading_blueprint(redis_service):
    bp = Blueprint('meter_reading_api', __name__)

    @bp.route('/meter/reading', methods=['POST'])
    def receive_reading():
        """
        单条读数上报 -> 先存队列 meter:readings_queue, 由后台Worker处理
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

            # 基础校验
            if not meter_id or not timestamp_str or reading_val is None:
                return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

            # 检查电表是否注册
            if not redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            # 不再直接 zadd，而是写入队列
            record = {
                "meter_id": meter_id,
                "timestamp": timestamp_str,
                "reading": reading_val
            }
            # 入队
            redis_service.client.rpush("meter:readings_queue", json.dumps(record))

            return jsonify({'status': 'success', 'message': 'Reading queued'}), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    @bp.route('/meter/bulk_readings', methods=['POST'])
    def receive_bulk_readings():
        """
        批量读数上报 -> 先存队列 meter:readings_queue, 后台Worker再批量写
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

            for record in readings:
                meter_id = record.get('meter_id')
                timestamp_str = record.get('timestamp')
                reading_val = record.get('reading')

                # 简易校验
                if not meter_id or not timestamp_str or reading_val is None:
                    fail_count += 1
                    continue

                # 电表是否注册
                if not redis_service.is_meter_registered(meter_id):
                    fail_count += 1
                    continue

                # 入队即可，不需要解析 timestamp
                queue_record = {
                    "meter_id": meter_id,
                    "timestamp": timestamp_str,
                    "reading": reading_val
                }
                try:
                    redis_service.client.rpush("meter:readings_queue", json.dumps(queue_record))
                    success_count += 1
                except Exception:
                    fail_count += 1

            return jsonify({
                'status': 'success',
                'message': f'Bulk queued. success={success_count}, failed={fail_count}'
            }), 200
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return bp
