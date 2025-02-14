import json
import redis
from flask import request, jsonify
from datetime import datetime, timedelta
import os

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

def user_query_api(app):
    @app.route('/api/user/query', methods=['GET'])
    def api_query():
        meter_id = request.args.get('meter_id')
        period = request.args.get('period')
        
        if not meter_id:
            return jsonify({'status': 'error', 'message': 'Missing meter_id'}), 400
        if not r.hexists("all_users", meter_id):
            return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

        now = datetime.now()
        key = f"meter:{meter_id}:history"
        
        # ========== 30 分钟增量 ==========
        if period == "30m":
            newest_readings = r.zrevrange(key, 0, 0)
            if not newest_readings:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200
            
            newest_data = json.loads(newest_readings[0])
            target_time = now.timestamp() - 1800

            old_readings = r.zrevrangebyscore(key, target_time, '-inf', start=0, num=1)
            if not old_readings:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200
            
            old_data = json.loads(old_readings[0])
            increment_30m = float(newest_data["reading_value"]) - float(old_data["reading_value"])
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'increment_last_30m': increment_30m
            }), 200
        
        # ========== 固定时间范围(1d,1w,1m,1y) ==========
        period_map = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}
        if period not in period_map:
            return jsonify({'status': 'error', 'message': 'Invalid period (choose 30m / 1d / 1w / 1m / 1y)'}), 400

        start_time = now - timedelta(days=period_map[period])
        
        total_count = r.zcount(key, start_time.timestamp(), now.timestamp())
        if total_count == 0:
            return jsonify({'status': 'success', 'data': 'No data available'}), 200

        readings = r.zrangebyscore(key, start_time.timestamp(), now.timestamp())
        if not readings:
            return jsonify({'status': 'success', 'data': 'No data available'}), 200
        
        data = [json.loads(h) for h in readings]
        total_usage = float(data[-1]["reading_value"]) - float(data[0]["reading_value"])

        # 计算每日用电量
        day_map = {}
        for rec in data:
            dt_str = rec["timestamp"]
            val = float(rec["reading_value"])
            day_str = dt_str.split("T")[0]  # YYYY-MM-DD

            if day_str not in day_map:
                day_map[day_str] = {"first": val, "last": val}
            else:
                day_map[day_str]["last"] = val
        
        daily_usage = {}
        for day_str, f_l in day_map.items():
            daily_usage[day_str] = f_l["last"] - f_l["first"]
        
        return jsonify({
            'status': 'success',
            'meter_id': meter_id,
            'total_usage': total_usage,            # 改名
            'daily_usage': daily_usage,            # 改名
            'total_count': total_count
        }), 200
