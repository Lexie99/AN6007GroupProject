# api/user_query_api.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta
from services.validation import validate_meter_id  # 导入校验函数

def create_user_query_blueprint(redis_service):
    """创建用户查询接口蓝图，支持按不同时间范围查询电表数据"""
    bp = Blueprint('user_query', __name__)

    def _parse_records(records):
        """解析并排序 Redis 记录，返回 (datetime, consumption) 列表"""
        parsed = []
        for raw in records:
            try:
                rec = json.loads(raw)
                dt = datetime.fromisoformat(rec["timestamp"])
                cons = float(rec.get("consumption", 0))
                parsed.append((dt, cons))
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                redis_service.log_event("query_error", 
                    f"Failed to parse record: {str(e)} | Raw: {raw[:100]}...")
        parsed.sort(key=lambda x: x[0])
        return parsed

    def _aggregate_daily(increments):
        """按天聚合数据"""
        daily_map = {}
        for dt, cons in increments:
            day_str = dt.strftime("%Y-%m-%d")
            daily_map[day_str] = daily_map.get(day_str, 0.0) + cons
        return [
            {"date": day, "consumption": daily_map[day]}
            for day in sorted(daily_map.keys())
        ]

    def _aggregate_monthly(increments):
        """按月聚合数据"""
        monthly_map = {}
        for dt, cons in increments:
            ym_str = dt.strftime("%Y-%m")
            monthly_map[ym_str] = monthly_map.get(ym_str, 0.0) + cons
        return [
            {"month": ym, "consumption": monthly_map[ym]}
            for ym in sorted(monthly_map.keys())
        ]

    @bp.route('/api/user/query', methods=['GET'])
    def api_query():
        """处理电表数据查询请求"""
        try:
            # --- 参数校验 ---
            meter_id = request.args.get('meter_id')
            period = request.args.get('period')

            # 校验 Meter ID 格式和注册状态
            if not meter_id:
                return jsonify({'status': 'error', 'message': 'Missing meter_id'}), 400
            if not validate_meter_id(meter_id):
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format'}), 400
            if not redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400
            
            # 校验 Period 有效性
            valid_periods = ["30m", "1d", "1w", "1m", "1y"]
            if period not in valid_periods:
                return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

            # --- 数据查询 ---
            now = datetime.utcnow()  # 使用 UTC 时间
            history_key = f"meter:{meter_id}:history"

            # 30分钟增量查询
            if period == "30m":
                lower_bound = (now - timedelta(minutes=30)).timestamp()
                upper_bound = now.timestamp()
                records = redis_service.client.zrangebyscore(
                    history_key, lower_bound, upper_bound
                )
                if not records:
                    return jsonify({'status': 'success', 'data': []}), 200
                
                total = sum(
                    float(json.loads(rec).get("consumption", 0) for rec in records
                ))
                return jsonify({
                    'status': 'success',
                    'meter_id': meter_id,
                    'total_usage': total,
                    'data': [{"time": json.loads(rec)["timestamp"] for rec in records}]
                })

            # --- 长期范围查询（1d/1w/1m/1y）---
            # 计算时间范围
            period_days = {
                "1d": 1, "1w": 7, "1m": 30, "1y": 365
            }[period]
            start_time = now - timedelta(days=period_days)
            
            # 获取原始数据
            records = redis_service.get_meter_readings_by_score(
                meter_id, start_time.timestamp(), now.timestamp()
            )
            if not records:
                return jsonify({'status': 'success', 'data': []}), 200
            
            # 解析并聚合数据
            increments = _parse_records(records)
            total_usage = sum(cons for _, cons in increments)

            # 按不同周期返回聚合结果
            if period == "1d":
                data = [{"time": ts.isoformat(), "consumption": cons} for ts, cons in increments]
            elif period in ["1w", "1m"]:
                data = _aggregate_daily(increments)
            elif period == "1y":
                data = _aggregate_monthly(increments)
            else:
                return jsonify({'status': 'error', 'message': 'Unsupported period'}), 400

            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': total_usage,
                'data': data
            })

        except Exception as e:
            redis_service.log_event("query_error", 
                f"Query failed: meter_id={meter_id}, period={period}, error={str(e)}")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

    return bp