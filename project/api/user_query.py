import json
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta, timezone
from services.validation import validate_meter_id  # Import validation function

def create_user_query_blueprint(redis_service):
    """Create a user query API blueprint that supports querying meter data for different time ranges."""
    bp = Blueprint('user_query', __name__)

    def _parse_records(records):
        """
        Parse and sort Redis records, returning a list of tuples (datetime in UTC, consumption).
        If the parsed time has no timezone info, assume local time and convert to UTC.
        """
        parsed = []
        for raw in records:
            try:
                rec = json.loads(raw)
                dt = datetime.fromisoformat(rec["timestamp"])
                if dt.tzinfo is None:
                    dt = dt.astimezone()  # Attach local timezone info
                dt_utc = dt.astimezone(timezone.utc)
                cons = float(rec.get("consumption", 0))
                parsed.append((dt_utc, cons))
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                redis_service.log_event("query_error",
                    f"Failed to parse record: {str(e)} | Raw: {raw[:100]}...")
        parsed.sort(key=lambda x: x[0])
        return parsed

    def _aggregate_daily(increments):
        """
        Aggregate the (UTC datetime, consumption) list by calendar day (UTC),
        returning a list of dictionaries: [{"date": "YYYY-MM-DD", "consumption": total}, ...]
        """
        daily_map = {}
        for dt, cons in increments:
            day_str = dt.strftime("%Y-%m-%d")
            daily_map[day_str] = daily_map.get(day_str, 0.0) + cons
        return [
            {"date": day, "consumption": daily_map[day]}
            for day in sorted(daily_map.keys())
        ]

    def _aggregate_monthly(increments):
        """
        Aggregate the (UTC datetime, consumption) list by calendar month (UTC),
        returning a list of dictionaries: [{"month": "YYYY-MM", "consumption": total}, ...]
        """
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
        """Handle meter data query requests."""
        try:
            # --- Parameter validation ---
            meter_id = request.args.get('meter_id')
            period = request.args.get('period')

            if not meter_id:
                return jsonify({'status': 'error', 'message': 'Missing meter_id'}), 400
            if not validate_meter_id(meter_id):
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format'}), 400
            if not redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            valid_periods = ["30m", "1d", "1w", "1m", "1y"]
            if period not in valid_periods:
                return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

            # 使用 UTC 时间作为查询参考时间
            now = datetime.utcnow().replace(tzinfo=timezone.utc)
            history_key = f"meter:{meter_id}:history"

            if period == "30m":
                # For 30-minute query, return the most recent record.
                records = redis_service.client.zrevrange(history_key, 0, 0)
                if not records:
                    return jsonify({'status': 'success', 'data': []}), 200
                last_record = json.loads(records[0])
                latest_increment = float(last_record.get("consumption", 0))
                return jsonify({
                    'status': 'success',
                    'meter_id': meter_id,
                    'latest_increment': latest_increment,
                    'data': [{"time": last_record["timestamp"]}]
                })

            # --- Long-term range query for 1d/1w/1m/1y ---
            period_days = {"1d": 1, "1w": 7, "1m": 30, "1y": 365}[period]
            start_time = now - timedelta(days=period_days)

            records = redis_service.get_meter_readings_by_score(
                meter_id, start_time.timestamp(), now.timestamp()
            )
            if not records:
                return jsonify({'status': 'success', 'data': []}), 200

            increments = _parse_records(records)
            total_usage = sum(cons for _, cons in increments)

            if period == "1d":
                # 对于1d查询，返回聚合后的总用电量和详细的每半小时数据
                aggregation = {
                    "consumption": round(total_usage, 2),
                    "start_time": start_time.isoformat(),
                    "end_time": now.isoformat()
                }
                detail = [{
                    "time": dt.strftime("%Y-%m-%d %H:%M"),
                    "consumption": round(cons, 2)
                } for dt, cons in increments]
                data = {
                    "aggregation": aggregation,
                    "detail": detail
                }
            elif period in ["1w", "1m"]:
                data = _aggregate_daily(increments)
            elif period == "1y":
                data = _aggregate_monthly(increments)
            else:
                return jsonify({'status': 'error', 'message': 'Unsupported period'}), 400

            return jsonify({
                'status': 'success',
                'meter_id': meter_id,
                'total_usage': round(total_usage, 2),
                'data': data
            })

        except Exception as e:
            redis_service.log_event("query_error",
                f"Query failed: meter_id={meter_id}, period={period}, error={str(e)}")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

    return bp
