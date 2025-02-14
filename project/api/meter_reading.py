import json
import redis
from flask import request, jsonify
from datetime import datetime
import os
# 从 daily_jobs_api 引入维护模式标记
from api.daily_jobs import IS_MAINTENANCE

# ========== Redis 连接配置 ==========
redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

# ========== 常量定义 ==========
BULK_QUEUE_KEY = "meter:readings_queue"  # 用于批量读数的队列（Redis List）


def meter_reading_api(app):
    """
    定义与电表读数相关的API路由
    """

    @app.route('/meter/reading', methods=['POST'])
    def receive_reading():
        """
        单条读数：如果在维护模式 -> 写入 meter:{id}:pending,
                否则 -> meter:{id}:history
        """
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

            meter_id = data.get('meter_id')
            timestamp = data.get('timestamp')
            reading_value = data.get('reading')

            # 基础字段检验
            if not meter_id or not timestamp or reading_value is None:
                return jsonify({'status': 'error', 'message': 'Missing required fields'}), 400

            # 转换 reading
            try:
                reading = float(reading_value)
            except (TypeError, ValueError):
                return jsonify({'status': 'error', 'message': 'Invalid reading value'}), 400

            # 转换时间戳
            try:
                dt_obj = datetime.fromisoformat(timestamp)
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid timestamp format'}), 400

            timestamp_iso = dt_obj.isoformat()
            timestamp_unix = int(dt_obj.timestamp())

            # 检查 MeterID 是否注册
            if not r.hexists("all_users", meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            # 根据维护模式决定写入位置
            if IS_MAINTENANCE:
                # 维护中 -> 先写到 pending 列表
                r.rpush(
                    f"meter:{meter_id}:pending",
                    json.dumps({
                        "timestamp": timestamp_iso,
                        "reading_value": reading
                    })
                )
            else:
                # 非维护 -> 直接写入 history (SortedSet)
                r.zadd(
                    f"meter:{meter_id}:history",
                    {json.dumps({
                        "timestamp": timestamp_iso,
                        "reading_value": reading
                    }): timestamp_unix}
                )

            return jsonify({'status': 'success'}), 200

        except redis.exceptions.RedisError as re:
            return jsonify({'status': 'error', 'message': f'Redis error: {str(re)}'}), 500
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Unexpected error: {str(e)}'}), 500


    @app.route('/meter/bulk_readings', methods=['POST'])
    def receive_bulk_readings():
        """
        【批量写入】接收一个包含多条电表读数的 JSON 数组，将其写入队列，后续由后台 Worker 批量处理。
        每条记录格式: {
            "meter_id": "...",
            "timestamp": "...",  # isoformat
            "reading": 123.45
        }
        如果在维护模式 -> 全部写入 meter:{id}:pending,否则 -> meter:{id}:history
        """
   
        try:
            readings = request.get_json()
            if not isinstance(readings, list):
                return jsonify({'status': 'error', 'message': 'Input must be a JSON list'}), 400

            valid_records = []
            for record in readings:
                meter_id = record.get('meter_id')
                timestamp = record.get('timestamp')
                reading_value = record.get('reading')

                # 基础字段检查
                if not meter_id or not timestamp or reading_value is None:
                    # 缺少必要字段，跳过（要不要记录错误？）
                    continue

                # 不在这里做详细转换，Worker 里再做也可以
                valid_records.append(record)

            if not valid_records:
                return jsonify({'status': 'error', 'message': 'No valid meter readings found'}), 400
            if IS_MAINTENANCE:
            # 维护期间 -> 全部写入 pending
                for rec in valid_records:
                    meter_id = rec['meter_id']
                    # 不做强制解析，等后面 pending 处理时再解析也行
                    r.rpush(f"meter:{meter_id}:pending", json.dumps(rec))
            else:
            # 批量压入 Redis List，等待后台 Worker 异步处理
            # rpush 支持可变参数，这里要对列表做展开
                r.rpush(BULK_QUEUE_KEY, *[json.dumps(rec) for rec in valid_records])
                return jsonify({'status': 'success', 'received_count': len(valid_records)}), 200

        except redis.exceptions.RedisError as re:
            return jsonify({'status': 'error', 'message': f'Redis error: {str(re)}'}), 500
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Unexpected error: {str(e)}'}), 500