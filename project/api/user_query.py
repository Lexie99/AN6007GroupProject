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

        # ========== 30分钟增量 =============
        if period == "30m":
            # 获取最新(分值最高)
            newest_list = redis_service.client.zrevrange(f"meter:{meter_id}:history", 0, 0)
            if not newest_list:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200

            newest_data = json.loads(newest_list[0])
            target_time = now.timestamp() - 1800
            # 在 [ -inf, target_time ] 中找最新一条
            old_list = redis_service.client.zrevrangebyscore(f"meter:{meter_id}:history", target_time, '-inf', start=0, num=1)
            if not old_list:
                return jsonify({'status': 'success', 'data': 'No data available'}), 200

            old_data = json.loads(old_list[0])
            increment = float(newest_data["reading_value"]) - float(old_data["reading_value"])
            return jsonify({'status': 'success', 'meter_id': meter_id, 'increment_last_30m': increment})

        # ========== 其他时间范围 ==========
        period_map = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}
        if period not in period_map:
            return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

        start_time = now - timedelta(days=period_map[period])
        recs = redis_service.get_meter_readings_by_score(meter_id, start_time.timestamp(), now.timestamp())
        if not recs:
            return jsonify({'status': 'success', 'data': 'No data available'}), 200

        # 1) 按时间顺序解析
        # 2) consecutive difference => increments
        data_sorted = []
        for r in recs:
            rec = json.loads(r)
            dt = datetime.fromisoformat(rec["timestamp"])
            val = float(rec["reading_value"])
            data_sorted.append((dt, val))
        data_sorted.sort(key=lambda x: x[0])  # 按时间升序

        # 计算 consecutive difference
        increments = []  # [(timestamp, usage_in_that_slot), ...]
        total_usage = 0.0

        for i in range(len(data_sorted)-1):
            t1, v1 = data_sorted[i]
            t2, v2 = data_sorted[i+1]
            inc = v2 - v1
            if inc < 0:
                # 累计值不应倒退，如有异常可skip
                continue
            increments.append((t2, inc))
            total_usage += inc

        # 根据 period 不同, 进行聚合
        if period == "1d":
            # 过去一天 => 每半小时 usage (实际上 设备是否整点半点上报?)
            # 我们只能把 consecutive increments 直接返回, 让前端画图
            usage_list = []
            for (ts, inc) in increments:
                usage_list.append({
                    "time": ts.isoformat(),  # or half-hour label
                    "consumption": inc
                })
            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'usage_list': usage_list  # each ~30 min increment
            })

        elif period in ["1w","1m"]:
            # 按天聚合
            daily_map = {}  # key=YYYY-MM-DD, value= sum_of_increments
            for (ts, inc) in increments:
                day_str = ts.strftime("%Y-%m-%d")
                if day_str not in daily_map:
                    daily_map[day_str] = 0.0
                daily_map[day_str] += inc

            # 转为 list 方便前端
            usage_list = []
            for day_str in sorted(daily_map.keys()):
                usage_list.append({
                    "date": day_str,
                    "consumption": daily_map[day_str]
                })

            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'daily_usage': usage_list
            })

        elif period == "1y":
            # 按月份聚合
            # day_str => 'YYYY-MM', accumulate
            monthly_map = {}
            for (ts, inc) in increments:
                ym_str = ts.strftime("%Y-%m")
                if ym_str not in monthly_map:
                    monthly_map[ym_str] = 0.0
                monthly_map[ym_str] += inc

            usage_list = []
            for ym_str in sorted(monthly_map.keys()):
                usage_list.append({
                    "month": ym_str,
                    "consumption": monthly_map[ym_str]
                })

            return jsonify({
                'status':'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'monthly_usage': usage_list
            })

    return bp
