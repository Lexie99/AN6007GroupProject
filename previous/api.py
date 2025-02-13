# api.py
import json
import random
import re
import time
from datetime import datetime, timedelta
from flask import request, jsonify
import pandas as pd
from apscheduler.schedulers.background import BackgroundScheduler

# --- 加载 JSON 配置数据 ---
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

area_data_config = config.get("area_data", {})
dwelling_data_config = config.get("dwelling_data", {})

# 使用 Pandas DataFrame 存储配置数据
area_data = pd.DataFrame(area_data_config)
dwelling_data = pd.DataFrame(dwelling_data_config)

# 根据区域数据生成“区域-街道”映射
region_area_mapping = area_data.groupby('Region')['Area'].apply(list).to_dict()

# --- 全局变量 ---
# 存储电表读数数据，结构为：{ meter_id: [ { 'timestamp': ..., 'reading': ... }, ... ], ... }
meter_data = {}
# --- 加载meter data ---
METER_DATA_FILE = "meter_data.json"

def load_meter_data():
    global meter_data
    try:
        with open(METER_DATA_FILE, "r", encoding="utf-8") as f:
            meter_data = json.load(f)
        print(f"Loaded meter_data from {METER_DATA_FILE}")
    except (FileNotFoundError, json.JSONDecodeError):
        meter_data = {}
        print(f"No existing meter_data found, starting with an empty dictionary.")

def save_meter_data():
    with open(METER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(meter_data, f, indent=4)
    print(f"Saved meter_data to {METER_DATA_FILE}")
# 加载历史数据
load_meter_data()

# 加载或初始化注册用户数据
try:
    with open("store_user_data.json", "r", encoding="utf-8") as f:
        store_user_data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    store_user_data = {}
    with open("store_user_data.json", "w", encoding="utf-8") as f:
        json.dump({}, f, indent=4)

# 当前用户 ID（如果已有注册数据，则取最大值+1，否则从 0 开始）
if store_user_data:
    current_id = max(map(int, store_user_data.keys())) + 1
else:
    current_id = 0

# 用于控制 API 是否接收请求的全局标志，True 表示正常接收，False 表示维护中（不接受请求）
acceptAPI = True

# --- 辅助函数 ---
def get_meter_data(meter_id, start_time):
    """
    根据起始时间筛选 meter_data 中的读数记录
    """
    if meter_id not in meter_data:
        return []
    records = meter_data[meter_id]
    filtered = []
    for record in records:
        try:
            record_time = datetime.strptime(record['timestamp'], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if record_time >= start_time:
            filtered.append(record)
    return filtered

def matainJobs():
    """
    将昨日获取的所有 meter reading 数据导出成 CSV 文件。
    导出的 CSV 文件名格式为 "meter_data_YYYY-MM-DD.csv"（日期为昨日日期）。
    """
    # 首先加载最新的持久化数据，确保内存数据最新
    load_meter_data()

    # 计算昨日日期（使用当前本地时间）
    yesterday = (datetime.now() - timedelta(days=1)).date()
    export_records = []
    for meter_id, records in meter_data.items():
        for rec in records:
            try:
                dt = datetime.strptime(rec['timestamp'], "%Y-%m-%d %H:%M")
            except Exception:
                continue
            if dt.date() == yesterday:
                export_records.append({
                    "meter_id": meter_id,
                    "timestamp": rec['timestamp'],
                    "reading": rec['reading']
                })
    if export_records:
        df = pd.DataFrame(export_records)
        csv_filename = f"meter_data_{yesterday}.csv"
        df.to_csv(csv_filename, index=False)
        print(f"Exported {len(export_records)} records to {csv_filename}")
    else:
        print("No records found for yesterday.")
    
    print("Waiting for one minute...")
    time.sleep(60)


# --- 注册 API 路由 ---
def register_api(app):
    # 在每个请求前检查是否允许接收请求，如果 acceptAPI 为 False，则返回维护信息
    @app.before_request
    def check_accept():
        if not acceptAPI:
            return jsonify({
                "status": "error",
                "message": "Server is under maintenance. Please try again later."
            }), 503

    # 接收电表读数数据接口
    @app.route('/meter/reading', methods=['POST'])
    def receive_reading():
        global meter_data, store_user_data, acceptAPI
        if not acceptAPI:
            return jsonify({'status': 'error', 'message': 'Server temporarily not accepting requests.'}), 503
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            timestamp_str = data.get('timestamp')
            reading = data.get('reading')
            
            # 通过 store_user_data 校验 meter_id 是否已注册
            registered_meter_ids = [user.get('MeterID') for user in store_user_data.values()]
            if meter_id not in registered_meter_ids:
                return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

            try:
                timestamp = datetime.fromisoformat(timestamp_str).strftime("%Y-%m-%d %H:%M")
            except Exception as e:
                return jsonify({'status': 'error', 'message': 'Invalid timestamp format'}), 400

            if meter_id not in meter_data:
                meter_data[meter_id] = []
            meter_data[meter_id].append({'timestamp': timestamp, 'reading': reading})
            
            # 调用保存函数，将最新数据持久化到文件
            save_meter_data()

            print("Current meter data:")
            for mid, records in meter_data.items():
                print(f"Meter {mid}:")
                for rec in records:
                    print(f"  {rec}")

            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500


    # 用户注册 API 接口
    @app.route('/api/user/register', methods=['POST'])
    def api_register():
        global current_id, store_user_data, acceptAPI
        # if not acceptAPI:
        #     return jsonify({'status': 'error', 'message': 'Server temporarily not accepting requests.'}), 503
        try:
            data = request.get_json()
            meter_id = data.get('meter_id')
            region = data.get('region')
            area = data.get('area')
            dwelling_type = data.get('dwelling_type')

            # 基本数据校验
            if not meter_id or not region or not area or not dwelling_type:
                return jsonify({'status': 'error', 'message': 'Missing fields'}), 400
            if not re.fullmatch(r"\d{9}", meter_id):
                return jsonify({'status': 'error', 'message': 'Invalid MeterID format'}), 400
            if any(user['MeterID'] == meter_id for user in store_user_data.values()):
                return jsonify({'status': 'error', 'message': 'This MeterID is already registered.'}), 400

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            current_id += 1
            user_data = {
                'MeterID': meter_id,
                'Region': region,
                'Area': area,
                'DwellingType': dwelling_type,
                'TimeStamp': timestamp
            }
            store_user_data[str(current_id)] = user_data
            # 保存注册数据到文件
            with open("store_user_data.json", "w", encoding="utf-8") as f:
                json.dump(store_user_data, f, indent=4)

            return jsonify({'status': 'success', 'message': 'Registration successful!'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500

    # 电表数据查询 API 接口
    @app.route('/api/meter/query', methods=['GET'])
    def api_query():
        meter_id = request.args.get('meter_id')
        period = request.args.get('period')
        if not meter_id or not period:
            return jsonify({'status': 'error', 'message': 'Missing parameters'}), 400

        # 校验 meter_id 是否已注册
        registered_meter_ids = [user.get('MeterID') for user in store_user_data.values()]
        if meter_id not in registered_meter_ids:
            return jsonify({'status': 'error', 'message': 'MeterID not registered'}), 400

        now = datetime.utcnow()
        if period == "30m":
            start_time = now - timedelta(minutes=30)
        elif period == "1d":
            start_time = now - timedelta(days=1)
        elif period == "1w":
            start_time = now - timedelta(weeks=1)
        elif period == "1m":
            start_time = now - timedelta(days=30)
        elif period == "1y":
            start_time = now - timedelta(days=365)
        else:
            return jsonify({'status': 'error', 'message': 'Invalid period'}), 400

        data = get_meter_data(meter_id, start_time)
        return jsonify({'status': 'success', 'data': data})

    # 停机维护接口：在调用时暂停接收 API 请求，导出昨日数据，再恢复服务
    @app.route('/stopserver', methods=['GET'])
    def stop_server():
        global acceptAPI
        acceptAPI = False
        # 调用 matainJobs 导出昨日数据到 CSV 文件
        matainJobs()
        acceptAPI = True
        return "Server Restarted"

# --- 导出变量供其他模块使用 ---
__all__ = ["register_api", "region_area_mapping", "dwelling_data"]
