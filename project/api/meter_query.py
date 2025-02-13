import json
import redis
from flask import request, jsonify
from datetime import datetime, timedelta

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

def register_query_api(app):
    @app.route('/api/meter/query', methods=['GET'])
    def api_query():
        """
        查询电表数据：
        - 默认显示最近一次读数的 30 分钟增量。
        - 用户可以选择过去 1 天 / 1 周 / 1 个月 / 1 年 / 自定义时间段。
        """
        meter_id = request.args.get('meter_id')
        period = request.args.get('period')
        start_date = request.args.get('start_date')  # YYYY-MM-DD
        end_date = request.args.get('end_date')      # YYYY-MM-DD

        if not meter_id:
            return jsonify({'status': 'error', 'message': 'Missing meter_id'}), 400
        if not r.hexists("all_users", meter_id):
            return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

        now = datetime.utcnow()

        # ** 1️⃣ 查询最近一次读数的 30 分钟增量 **
        if not period and not start_date and not end_date:
            last_readings = r.zrevrange(f"meter:{meter_id}:history", 0, 1)  # 最新读数
            past_30m_readings = r.zrangebyscore(f"meter:{meter_id}:history", now.timestamp() - 1800, now.timestamp(), start=0, num=1)  # 30 分钟前的读数

            if not last_readings or not past_30m_readings:
                return jsonify({'status': 'success', 'data': 'No data available'})

            last_data = json.loads(last_readings[0])
            past_30m_data = json.loads(past_30m_readings[0])

            increment = float(last_data["reading_value"]) - float(past_30m_data["reading_value"])
            return jsonify({'status': 'success', 'meter_id': meter_id, 'increment_last_30m': increment})

        # ** 2️⃣ 处理时间范围查询 **
        period_map = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}
        if period in period_map:
            start_time = now - timedelta(days=period_map[period])
        elif start_date and end_date:
            start_time = datetime.strptime(start_date, "%Y-%m-%d")
            end_time = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)  # 结束时间包含当天
        else:
            return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

        readings = r.zrangebyscore(f"meter:{meter_id}:history", start_time.timestamp(), now.timestamp())

        if not readings:
            return jsonify({'status': 'success', 'data': 'No data available'})

        # ** 计算总用电量和每日用电量 **
        data = [json.loads(h) for h in readings]
        total_usage = float(data[-1]["reading_value"]) - float(data[0]["reading_value"])  # 总用电量

        daily_usage = {}
        for record in data:
            date = record["timestamp"].split("T")[0]  # 提取 YYYY-MM-DD
            if date not in daily_usage:
                daily_usage[date] = float(record["reading_value"])
            else:
                daily_usage[date] = max(daily_usage[date], float(record["reading_value"]))

        # 计算每日增量
        daily_usage_increment = {date: (daily_usage[date] - daily_usage[prev_date]) for date, prev_date in zip(list(daily_usage.keys())[1:], list(daily_usage.keys())[:-1])}

        return jsonify({
            'status': 'success',
            'meter_id': meter_id,
            'total_usage': total_usage,
            'daily_usage': daily_usage_increment
        })
