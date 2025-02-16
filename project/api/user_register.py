# api/user_register.py
import re
from flask import request, jsonify, Blueprint
from models.user import User
from services.validation import validate_meter_id

def create_user_register_blueprint(app_config, redis_service):
    """
    依赖:
      - AppConfig: 用于校验 region, area, dwelling_type
      - RedisService: 写 all_users, user_data:{meter_id}
    """
    bp = Blueprint('user_register', __name__)

    @bp.route('/api/user/register', methods=['POST'])
    def register_user():
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            region = data.get('region')
            area = data.get('area')
            dwelling_type = data.get('dwelling_type')

            if not meter_id or not region or not area or not dwelling_type:
                return jsonify({'status': 'error', 'message': 'Missing fields'}), 400
            
            if not validate_meter_id(meter_id):  # 使用统一校验
                return jsonify({'status': 'error', 'message': 'MeterID must be 9 digits'}), 400

            if redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID already registered'}), 400

            # 校验 region-area
            if region not in app_config.region_area_mapping or area not in app_config.region_area_mapping[region]:
                return jsonify({'status': 'error', 'message': 'Invalid region-area'}), 400

            # 校验 dwelling
            if dwelling_type not in app_config.dwelling_type_set:
                return jsonify({'status': 'error', 'message': 'Invalid dwelling_type'}), 400

            user_obj = User(meter_id, region, area, dwelling_type)
            redis_service.register_meter(meter_id)
            redis_service.set_user_data(meter_id, user_obj.to_dict())

            return jsonify({'status': 'success', 'message': 'Registration successful!'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    return bp
