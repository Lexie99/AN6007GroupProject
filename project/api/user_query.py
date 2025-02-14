# api/user_query.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta

def create_user_query_blueprint(redis_service):
    bp = Blueprint('user_query', __name__)

    @bp.route('/api/user/query', methods=['GET'])
    def api_query():
        meter_id = request.args.get('meter_id')
        period = request.args.get('period')

        if not meter_id:
            return jsonify({'status': 'error', 'message': 'Missing meter_id'}), 400
        if not redis_service.is_meter_registered(meter_id):
            return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

        now = datetime.now()
        # 30分增量
        if period == "30m":
            newest_list = redis_service.client.zrevrange(f"meter:{meter_id}:history", 0, 0)
            if not newest_list:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200
            
            newest_data = json.loads(newest_list[0])
            target_time = now.timestamp() - 1800
            old_list = redis_service.client.zrevrangebyscore(f"meter:{meter_id}:history", target_time, '-inf', start=0, num=1)
            if not old_list:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200
            
            old_data = json.loads(old_list[0])
            increment = float(newest_data["reading_value"]) - float(old_data["reading_value"])
            return jsonify({'status': 'success', 'meter_id': meter_id, 'increment_last_30m': increment})

        # 固定范围
        period_map = {"1d":1, "1w":7, "1m":30, "1y":365}
        if period not in period_map:
            return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

        start_time = now - timedelta(days=period_map[period])
        recs = redis_service.get_meter_readings_by_score(meter_id, start_time.timestamp(), now.timestamp())
        if not recs:
            return jsonify({'status':'success','data':'No data available'}), 200

        data = [json.loads(r) for r in recs]
        total_usage = float(data[-1]["reading_value"]) - float(data[0]["reading_value"])

        # daily usage
        day_map = {}
        for item in data:
            d_str = item["timestamp"].split("T")[0]
            val = float(item["reading_value"])
            if d_str not in day_map:
                day_map[d_str] = {"first": val, "last": val}
            else:
                day_map[d_str]["last"] = val

        daily_usage = {}
        for d, v in day_map.items():
            daily_usage[d] = v["last"] - v["first"]

        return jsonify({
            'status': 'success',
            'meter_id': meter_id,
            'total_usage': total_usage,
            'daily_usage': daily_usage
        })

    return bp
