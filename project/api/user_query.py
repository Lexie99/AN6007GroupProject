# api/user_query_api.py

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
        history_key = f"meter:{meter_id}:history"

        # ========== 30分钟增量 ==========
        if period == "30m":
            # 查询过去30分钟内的记录（分值介于 now-1800 与 now 之间）
            lower_bound = now.timestamp() - 1800
            upper_bound = now.timestamp()
            records = redis_service.client.zrangebyscore(history_key, lower_bound, upper_bound)
            if not records:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200

            total_consumption = 0.0
            for record in records:
                try:
                    rec = json.loads(record)
                    total_consumption += float(rec.get("consumption", 0))
                except Exception:
                    continue

            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'increment_last_30m': total_consumption
            })

        # ========== 其他时间范围 ==========
        # period_map：1d, 1w, 1m, 1y 分别对应过去的天数
        period_map = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}
        if period not in period_map:
            return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

        # 计算查询起始时间
        start_time = now - timedelta(days=period_map[period])
        # 通过 redis_service 获取在 [start_time, now] 内的记录
        recs = redis_service.get_meter_readings_by_score(meter_id, start_time.timestamp(), now.timestamp())
        if not recs:
            return jsonify({'status': 'success', 'data': 'No data available'}), 200

        # 将记录解析为 (datetime, consumption) 列表
        data_sorted = []
        for record in recs:
            try:
                rec = json.loads(record)
                dt = datetime.fromisoformat(rec["timestamp"])
                cons = float(rec.get("consumption", 0))
                data_sorted.append((dt, cons))
            except Exception:
                continue
        data_sorted.sort(key=lambda x: x[0])

        total_usage = sum(cons for _, cons in data_sorted)
        # increments 即每条记录代表的用电量（通常为半小时数据）
        increments = data_sorted

        if period == "1d":
            # 过去一天：返回每条记录（假设设备每半小时上报一次），用于柱状图展示
            usage_list = []
            for (ts, cons) in increments:
                usage_list.append({
                    "time": ts.isoformat(),
                    "consumption": cons
                })
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'usage_list': usage_list  # 每条记录代表一段时间的用电量
            })

        elif period in ["1w", "1m"]:
            # 过去一周或一月：按天聚合数据
            daily_map = {}  # key: "YYYY-MM-DD", value: 累计用电量
            for (ts, cons) in increments:
                day_str = ts.strftime("%Y-%m-%d")
                daily_map[day_str] = daily_map.get(day_str, 0.0) + cons

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
            for (ts, cons) in increments:
                ym_str = ts.strftime("%Y-%m")
                monthly_map[ym_str] = monthly_map.get(ym_str, 0.0) + cons

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
