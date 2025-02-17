# api/user_query_api.py

import json
from flask import request, jsonify, Blueprint
from datetime import datetime, timedelta
from services.validation import validate_meter_id  # Import validation function

def create_user_query_blueprint(redis_service):
    """Create a user query API blueprint that supports querying meter data for different time ranges."""
    bp = Blueprint('user_query', __name__)

    def _parse_records(records):
        """Parse and sort Redis records, returning a list of tuples (datetime, consumption)."""
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
        """Aggregate data on a daily basis."""
        daily_map = {}
        for dt, cons in increments:
            day_str = dt.strftime("%Y-%m-%d")
            daily_map[day_str] = daily_map.get(day_str, 0.0) + cons
        return [
            {"date": day, "consumption": daily_map[day]}
            for day in sorted(daily_map.keys())
        ]

    def _aggregate_monthly(increments):
        """Aggregate data on a monthly basis."""
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

            # Validate meter_id format and registration status
            if not meter_id:
                return jsonify({'status': 'error', 'message': 'Missing meter_id'}), 400
            if not validate_meter_id(meter_id):
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format'}), 400
            if not redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400
            
            # Validate period
            valid_periods = ["30m", "1d", "1w", "1m", "1y"]
            if period not in valid_periods:
                return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

            now = datetime.utcnow()  # Use UTC time
            history_key = f"meter:{meter_id}:history"

            if period == "30m":
                # Instead of filtering by current time, simply return the most recent record.
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

            # --- Long-term range query (1d/1w/1m/1y) ---
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
