# api/user_register.py

from flask import request, jsonify, Blueprint
from models.user import User
from services.validation import validate_meter_id
from services.redis_service import RedisService
from config.app_config import AppConfig

def create_user_register_blueprint(app_config: AppConfig, redis_service: RedisService):
    """
    用户注册接口蓝图：
    - 校验电表ID、区域、地区和住宅类型
    - 将注册信息持久化到 Redis
    依赖项：
      - app_config: 提供区域、地区、住宅类型的配置校验
      - redis_service: 管理用户数据的存储
    """
    bp = Blueprint('user_register', __name__)

    def _validate_region_area(region: str, area: str) -> bool:
        """校验区域和地区是否匹配配置"""
        return region in app_config.region_area_mapping and \
               area in app_config.region_area_mapping[region]

    def _validate_dwelling_type(dwelling_type: str) -> bool:
        """校验住宅类型是否合法"""
        return dwelling_type in app_config.dwelling_type_set

    @bp.route('/api/user/register', methods=['POST'])
    def register_user():
        """用户注册接口"""
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'Empty request body'}), 400

            # 提取并校验必填字段
            required_fields = ['meter_id', 'region', 'area', 'dwelling_type']
            if not all(field in data for field in required_fields):
                missing = [f for f in required_fields if f not in data]
                return jsonify({'status': 'error', 'message': f'Missing fields: {missing}'}), 400

            meter_id = data['meter_id']
            region = data['region']
            area = data['area']
            dwelling_type = data['dwelling_type']

            # 校验 Meter ID 格式
            if not validate_meter_id(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID must be 9 digits'}), 400

            # 检查电表是否已注册
            if redis_service.is_meter_registered(meter_id):
                return jsonify({'status': 'error', 'message': 'MeterID already registered'}), 409  # 409 Conflict

            # 校验区域和地区
            if not _validate_region_area(region, area):
                return jsonify({'status': 'error', 'message': 'Invalid region-area combination'}), 400

            # 校验住宅类型
            if not _validate_dwelling_type(dwelling_type):
                return jsonify({'status': 'error', 'message': 'Invalid dwelling type'}), 400

            # 创建用户对象
            user = User(meter_id, region, area, dwelling_type)
            with redis_service.client.pipeline() as pipe:
                pipe.multi()  # 开启事务
                pipe.hset("all_users", meter_id, 1)
                pipe.hset(f"user_data:{meter_id}", mapping=user.to_dict())
                pipe.execute()  # 原子提交

            # 记录成功日志
            redis_service.log_event("registration", 
                f"User registered: meter_id={meter_id}, region={region}, area={area}")

            return jsonify({
                'status': 'success',
                'message': 'Registration successful',
                'data': user.to_dict()  # 返回注册后的用户信息
            }), 201  # 201 Created

        except Exception as e:
            # 记录错误日志（避免返回敏感信息）
            redis_service.log_event("registration_error", 
                f"Registration failed: {str(e)} | Data: {data}")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500

    return bp