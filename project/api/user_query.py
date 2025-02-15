# api/user_query_api.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta
import math

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

        # ========== 30分钟增量 ==========
        if period == "30m":
            # 获取最新（分值最高）的记录
            newest_list = redis_service.client.zrevrange(f"meter:{meter_id}:history", 0, 0)
            if not newest_list:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200

            newest_data = json.loads(newest_list[0])
            target_time = now.timestamp() - 1800  # 30分钟之前的目标时间

            # 在分值<=target_time 的范围内，按分值降序取第一条记录
            old_list = redis_service.client.zrevrangebyscore(
                f"meter:{meter_id}:history", target_time, '-inf', start=0, num=1)
            if not old_list:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200

            old_data = json.loads(old_list[0])
            increment = float(newest_data["reading_value"]) - float(old_data["reading_value"])
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'increment_last_30m': increment
            })

        # ========== 其他时间范围 ==========
        # period_map 表示：过去1天、1周、1月、1年分别对应的天数
        period_map = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}
        if period not in period_map:
            return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

        # 计算查询起始时间（过去N天）
        start_time = now - timedelta(days=period_map[period])
        recs = redis_service.get_meter_readings_by_score(meter_id, start_time.timestamp(), now.timestamp())
        if not recs:
            return jsonify({'status': 'success', 'data': 'No data available'}), 200

        # 将记录解析为 (datetime, value) 列表，并按时间升序排序
        data_sorted = []
        for record in recs:
            try:
                rec = json.loads(record)
                dt = datetime.fromisoformat(rec["timestamp"])
                val = float(rec["reading_value"])
                data_sorted.append((dt, val))
            except Exception:
                continue
        data_sorted.sort(key=lambda x: x[0])

        # 计算连续记录的增量，得到每个时间段的用电量，以及总用电量
        increments = []  # 每个元素为 (timestamp, increment)
        total_usage = 0.0
        for i in range(len(data_sorted) - 1):
            t1, v1 = data_sorted[i]
            t2, v2 = data_sorted[i + 1]
            inc = v2 - v1
            if inc < 0:
                # 如果累计读数出现下降，视为异常情况，跳过
                continue
            increments.append((t2, inc))
            total_usage += inc

        # 根据 period 的不同进行数据聚合
        if period == "1d":
            # 过去一天：返回每对连续记录的增量数据，假设设备每半小时上报一次
            usage_list = []
            for (ts, inc) in increments:
                usage_list.append({
                    "time": ts.isoformat(),  # 可作为具体时间标签
                    "consumption": inc
                })
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'usage_list': usage_list  # 每条记录代表一段时间的增量
            })

        elif period in ["1w", "1m"]:
            # 过去一周或一月：按天聚合数据
            daily_map = {}  # key: "YYYY-MM-DD", value: 累计用电量
            for (ts, inc) in increments:
                day_str = ts.strftime("%Y-%m-%d")
                daily_map[day_str] = daily_map.get(day_str, 0.0) + inc

            usage_list = []
            for day in sorted(daily_map.keys()):
                usage_list.append({
                    "date": day,
                    "consumption": daily_map[day]
                })
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'daily_usage': usage_list
            })

        elif period == "1y":
            # 过去一年：按月份聚合数据
            monthly_map = {}  # key: "YYYY-MM", value: 累计用电量
            for (ts, inc) in increments:
                ym_str = ts.strftime("%Y-%m")
                monthly_map[ym_str] = monthly_map.get(ym_str, 0.0) + inc

            usage_list = []
            for ym in sorted(monthly_map.keys()):
                usage_list.append({
                    "month": ym,
                    "consumption": monthly_map[ym]
                })
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'monthly_usage': usage_list
            })

        return jsonify({'status': 'error', 'message': 'Unsupported data format.'})

    return bp
