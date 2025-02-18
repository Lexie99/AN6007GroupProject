import re
from flask import Blueprint, request, jsonify
from services.validation import validate_meter_id  # 如有必要，可加入其他校验函数

# 测试的时候访问API需要带meter_id和month参数，如：
# http://127.0.0.1:8050/api/billing?meter_id=100000001&month=2025-02
# 请根据需要修改API的参数和返回值,否则取不到数据


def create_billing_blueprint(redis_service):
    bp = Blueprint('billing_api', __name__)

    @bp.route('/api/billing', methods=['GET'])
    def get_monthly_billing():
        """
        Aggregate monthly electricity consumption for billing.
        Query parameters:
            - meter_id: required, 9-digit meter ID.
            - month: required, in format "YYYY-MM" (e.g., "2025-02").
        The API will search daily backup data (keys with format "backup:meter_data:{date}")
        for all dates within the specified month, sum up the consumption for the given meter,
        and return the total usage along with daily details.
        """
        meter_id = request.args.get('meter_id')
        month_str = request.args.get('month')

        # Validate meter_id
        if not meter_id or not meter_id.isdigit() or len(meter_id) != 9:
            return jsonify({'status': 'error', 'message': 'Invalid or missing meter_id'}), 400

        # Validate month format (YYYY-MM)
        if not month_str or not re.match(r'^\d{4}-\d{2}$', month_str):
            return jsonify({'status': 'error', 'message': 'Invalid or missing month. Expected format: YYYY-MM'}), 400

        total_usage = 0.0
        daily_details = {}

        # Construct a pattern to scan keys: backup:meter_data:YYYY-MM-*
        pattern = f"backup:meter_data:{month_str}-*"
        keys = list(redis_service.client.scan_iter(pattern))
        for key in keys:
            # Extract date from key. Key format: backup:meter_data:{date}
            date_part = key.split(":")[-1]
            backup_data = redis_service.get_backup_data(date_part)
            if backup_data and meter_id in backup_data:
                try:
                    usage = float(backup_data[meter_id])
                except ValueError:
                    usage = 0.0
                total_usage += usage
                daily_details[date_part] = usage

        if total_usage == 0.0:
            return jsonify({'status': 'error', 'message': f'No billing data found for meter {meter_id} in month {month_str}'}), 404

        return jsonify({
            'status': 'success',
            'meter_id': meter_id,
            'month': month_str,
            'total_usage': total_usage,
            'daily_usage': daily_details
        })

    return bp
