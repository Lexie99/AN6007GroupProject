import json
import redis
import re
from flask import request, jsonify
from datetime import datetime
import os
from collections import defaultdict

redis_host = os.getenv('REDIS_HOST', 'localhost')
redis_port = int(os.getenv('REDIS_PORT', 6379))
r = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)

region_area_mapping = defaultdict(set)  # region -> set of areas
dwelling_type_set = set()              # for membership check

def load_config():
    """
    读取 `project/config.json` 并构建:
      - region_area_mapping: {region: set(areas)}
      - dwelling_type_set: {dwelling_type1, dwelling_type2, ...}
    """
    global region_area_mapping, dwelling_type_set

    config_path = os.path.join("project", "config.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        area_data = config.get("area_data", {})
        areas = area_data.get("Area", [])
        regions = area_data.get("Region", [])

        # 构建 region -> set of areas
        region_area_mapping = defaultdict(set)
        for region, area in zip(regions, areas):
            region_area_mapping[region].add(area)

        # 解析 dwelling_data
        dwelling_info = config.get("dwelling_data", {})
        dwelling_list = dwelling_info.get("DwellingType", [])
        # 若只需校验字符串
        dwelling_type_set = set(dwelling_list)

        print("✅ Loaded config (region-area + dwelling data) into memory.")

    except Exception as e:
        print(f"❌ Failed to load config: {e}")

# 启动时加载
load_config()

def user_register_api(app):
    @app.route('/api/user/region-area', methods=['GET'])
    def get_region_area():
        """
        返回 {region: list_of_areas} 供前端或其他模块使用
        """
        # region_area_mapping 里是 set，需要转成 list
        result = {r: sorted(list(areas)) for r, areas in region_area_mapping.items()}
        return jsonify(result)

    @app.route('/api/user/dwelling-types', methods=['GET'])
    def get_dwelling_types():
        """
        返回所有可用 dwelling_type 给前端
        """
        return jsonify(sorted(list(dwelling_type_set)))

    @app.route('/api/user/register', methods=['POST'])
    def register_user():
        """
        用户注册，写入 Redis
        """
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            region = data.get('region')
            area = data.get('area')
            dwelling_type = data.get('dwelling_type')

            # 1) 基础校验
            if not meter_id or not region or not area or not dwelling_type:
                return jsonify({'status': 'error', 'message': 'Missing fields'}), 400
            if not re.fullmatch(r"\d{9}", meter_id):
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format (must be 9 digits)'}), 400

            # 检查是否已存在
            if r.hexists("all_users", meter_id):
                return jsonify({'status': 'error', 'message': 'This MeterID is already registered.'}), 400

            # 2) 校验 region-area
            #   region_area_mapping[region] 是一个 set
            if region not in region_area_mapping or area not in region_area_mapping[region]:
                return jsonify({'status': 'error', 'message': 'Invalid Region or Area'}), 400

            # 3) 校验 dwelling_type
            if dwelling_type not in dwelling_type_set:
                return jsonify({'status': 'error', 'message': 'Invalid Dwelling Type'}), 400

            # 4) 存入 Redis
            timestamp = datetime.now().isoformat()
            user_data = {
                'MeterID': meter_id,
                'Region': region,
                'Area': area,
                'DwellingType': dwelling_type,
                'TimeStamp': timestamp
            }

            r.hset(f"user_data:{meter_id}", mapping=user_data)
            r.hset("all_users", meter_id, 1)

            return jsonify({'status': 'success', 'message': 'Registration successful!'})

        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
