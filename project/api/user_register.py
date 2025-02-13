import json
import redis
import re
from flask import request, jsonify
from datetime import datetime

r = redis.Redis(host='localhost', port=6379, decode_responses=True)

# **🔹 直接在 Python 变量中存储 `region_area_mapping` 和 `dwelling_data`**
region_area_mapping = {}
dwelling_data = {}

def load_config():
    """
    读取 `config.json` 并加载 `region_area_mapping` 和 `dwelling_data`，以供其他模块导入。
    """
    global region_area_mapping, dwelling_data  # 使用全局变量存储，供 `register.py` 直接使用

    try:
        with open("project/config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        # **区域数据**
        area_data = config.get("area_data", {})
        region_area_mapping = {}
        for region, area in zip(area_data["Region"], area_data["Area"]):
            if region not in region_area_mapping:
                region_area_mapping[region] = []
            region_area_mapping[region].append(area)

        # **住宅类型**
        dwelling_data = {str(type_id): type_name for type_id, type_name in zip(config["dwelling_data"]["TypeID"], config["dwelling_data"]["DwellingType"])}

        print("✅ Loaded config into memory.")

    except Exception as e:
        print(f"❌ Failed to load config: {e}")

# **🔹 服务器启动时加载配置**
load_config()

# **🔹 注册 API**
def user_register_api(app):
    # **获取 `region` 和 `area` 映射**
    @app.route('/api/user/region-area', methods=['GET'])
    def get_region_area():
        """
        提供 `region` 和 `area` 对应数据给 Dash 下拉菜单。
        """
        return jsonify(region_area_mapping)

    # **获取 `dwelling_type` 选项**
    @app.route('/api/user/dwelling-types', methods=['GET'])
    def get_dwelling_types():
        """
        提供 `dwelling_type` 选项给 Dash 下拉菜单。
        """
        return jsonify(dwelling_data)

    # **注册用户**
    @app.route('/api/user/register', methods=['POST'])
    def register_user():
        """
        用户注册，数据存入 Redis。
        """
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            region = data.get('region')
            area = data.get('area')
            dwelling_type = data.get('dwelling_type')

            # **🔹 校验字段**
            if not meter_id or not region or not area or not dwelling_type:
                return jsonify({'status': 'error', 'message': 'Missing fields'}), 400
            if not re.fullmatch(r"\d{9}", meter_id):
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format'}), 400
            if r.hexists("all_users", meter_id):
                return jsonify({'status': 'error', 'message': 'This MeterID is already registered.'}), 400

            # **🔹 校验 `region` & `area` 是否匹配**
            if region not in region_area_mapping or area not in region_area_mapping[region]:
                return jsonify({'status': 'error', 'message': 'Invalid Region or Area'}), 400

            # **🔹 校验 `dwelling_type` 是否存在**
            if dwelling_type not in dwelling_data.values():
                return jsonify({'status': 'error', 'message': 'Invalid Dwelling Type'}), 400

            # **🔹 存入 Redis**
            timestamp = datetime.now().isoformat()
            user_data = {
                'MeterID': meter_id,
                'Region': region,
                'Area': area,
                'DwellingType': dwelling_type,
                'TimeStamp': timestamp
            }

            r.hset(f"user_data:{meter_id}", mapping=user_data)
            r.hset("all_users", meter_id, 1)  # 记录 MeterID 存在

            return jsonify({'status': 'success', 'message': 'Registration successful!'})

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
