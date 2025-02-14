# api/meter_reading_api.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime

def create_meter_reading_blueprint(redis_service):
    bp = Blueprint('meter_reading_api', __name__)

    @bp.route('/meter/reading', methods=['POST'])
    def receive_reading():
        """
        单条读数上报 -> meter:{id}:history
        """
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            timestamp_str = data.get('timestamp')
            reading_val = data.get('reading')

            if not meter_id or not timestamp_str or reading_val is None:
                return jsonify({'status': 'error', 'message': 'Missing fields'}), 400

            if not redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            dt_obj = datetime.fromisoformat(timestamp_str)
            score = dt_obj.timestamp()

            record_str = json.dumps({
                "timestamp": dt_obj.isoformat(),
                "reading_value": float(reading_val)
            })
            redis_service.add_meter_reading(meter_id, record_str, score)

            return jsonify({'status': 'success'}), 200
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid timestamp format'}), 400
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return bp
