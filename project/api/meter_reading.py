import json
from flask import request, jsonify, Blueprint
from datetime import datetime
from services.state import MaintenanceState
from services.validation import validate_meter_id, validate_timestamp
import traceback
# 添加批量记录数限制
MAX_BULK_RECORDS = 1000

def create_meter_reading_blueprint(redis_service):
    """创建电表读数上报接口蓝图，支持单条和批量上报"""
    bp = Blueprint('meter_reading_api', __name__)
    maint_state = MaintenanceState(redis_service.client)  # 维护状态管理器

    def _validate_reading_data(data):
        """内部校验函数：校验单条读数数据的完整性"""
        meter_id = data.get('meter_id')
        timestamp_str = data.get('timestamp')
        reading_val = data.get('reading')
        
        # 基础字段缺失校验
        if not all([meter_id, timestamp_str, reading_val]):
            return False, "Missing required fields"
        
        # Meter ID 格式校验
        if not validate_meter_id(meter_id):
            return False, "Invalid MeterID format"
        
        # 时间戳格式校验
        if not validate_timestamp(timestamp_str):
            return False, "Invalid timestamp format"
        
        return True, None

    @bp.route('/meter/reading', methods=['POST'])
    def receive_reading():
        """
        单条读数上报接口：
        - 维护模式下数据存入 pending 队列
        - 正常模式下数据存入 readings_queue
        """
        data = None
        try:
            data = request.get_json()
            if not data:
                return jsonify({'status': 'error', 'message': 'Invalid JSON body'}), 400

            # 校验数据完整性
            is_valid, error_msg = _validate_reading_data(data)
            if not is_valid:
                redis_service.log_event("meter_reading", f"Validation failed: {error_msg}")
                return jsonify({'status': 'error', 'message': error_msg}), 400

            meter_id = data['meter_id']
            
            # 检查电表是否注册
            if not redis_service.is_meter_registered(meter_id):
                redis_service.log_event("meter_reading", f"Unregistered meter: {meter_id}")
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            # 根据维护状态选择存储队列
            if maint_state.is_maintenance():
                key = f"meter:{meter_id}:pending"
                message = "Reading stored to pending queue (maintenance mode)"
            else:
                key = "meter:readings_queue"
                message = "Reading queued successfully"

            # 记录存储操作日志
            redis_service.log_event("meter_reading", 
                f"Stored reading: meter_id={meter_id}, timestamp={data.get('timestamp')}")
            redis_service.client.rpush(key, json.dumps(data))
            
            return jsonify({'status': 'success', 'message': message}), 200
        
        except Exception as e:        
            traceback.print_exc()  # 打印详细异常信息到控制台
            meter_info = data.get('meter_id') if data and isinstance(data, dict) else 'unknown'
            redis_service.log_event("error", 
                f"Failed to process single reading: {str(e)} | Data: {meter_info}")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    
    @bp.route('/meter/bulk_readings', methods=['POST'])
    def receive_bulk_readings():
        """
        批量读数上报接口：
        - 使用 Redis 管道批量提交提升性能
        - 自动过滤无效数据并统计结果
        """
        readings = None
        try:
            readings = request.get_json()
            if not isinstance(readings, list):
                return jsonify({'status': 'error', 'message': 'Input must be a JSON list'}), 400
            if len(readings) > MAX_BULK_RECORDS:
                return jsonify({'status': 'error', 'message': 'Exceed max bulk records limit'}), 400

            success_count = 0
            fail_count = 0
            pipeline = redis_service.client.pipeline()  # 创建管道
            
            # 检查当前维护状态（避免循环内重复检查）
            is_maintenance = maint_state.is_maintenance()

            for record in readings:
                # 校验单条数据
                is_valid, _ = _validate_reading_data(record)
                if not is_valid:
                    fail_count += 1
                    continue
                
                meter_id = record['meter_id']
                if not redis_service.is_meter_registered(meter_id):
                    fail_count += 1
                    continue

                # 选择存储队列
                key = f"meter:{meter_id}:pending" if is_maintenance else "meter:readings_queue"
                pipeline.rpush(key, json.dumps(record))
                success_count += 1

            # 批量执行管道命令
            pipeline.execute()
            redis_service.log_event("meter_reading", 
                f"Bulk upload completed: success={success_count}, failed={fail_count}")

            return jsonify({
                'status': 'success',
                'message': f'Bulk queued. Success: {success_count}, Failed: {fail_count}'
            }), 200
        
        except Exception as e:
            traceback.print_exc()  # 打印详细异常信息到控制台
            total_records = len(readings) if readings and isinstance(readings, list) else 0
            redis_service.log_event("error",
                                    f"Bulk upload failed: {str(e)} | Total records: {total_records}")
            return jsonify({'status': 'error', 'message': 'Internal server error'}), 500
    return bp
