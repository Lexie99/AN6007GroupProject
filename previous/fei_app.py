# app.py
from flask import Flask, request, jsonify
from datetime import datetime, timedelta
import json
import random
import re
import pandas as pd
import project.dash_app.dash_app as dash_app
from project.dash_app.dash_app import dcc, html, Input, Output, State
from project.dash_app.dash_app import dash_table

# =============================================================================
# 1. 全局变量与数据定义
# =============================================================================

# 用于电表读数校验的静态元数据（示例数据）
user_dict = {
    "000000001": {"area": "Area1", "region": "Region1", "dwelling_type": "Apartment", "username": "user1", "meter_id": "000000001"},
    "000000002": {"area": "Area2", "region": "Region2", "dwelling_type": "House",     "username": "user2", "meter_id": "000000002"},
    "000000003": {"area": "Area3", "region": "Region3", "dwelling_type": "Apartment", "username": "user3", "meter_id": "000000003"}
}

# 用于存储电表读数数据，结构：{ meter_id: [ { 'timestamp': ..., 'reading': ... }, ... ], ... }
meter_data = {}

# 创建 Flask 主服务器
server = Flask(__name__)

# =============================================================================
# 2. 电表读数 API (Flask 路由)
# =============================================================================


@server.route('/meter/reading', methods=['POST'])
def receive_reading():
    global user_dict, meter_data
    try:
        data = request.get_json()
        # 从请求中解析参数
        meter_id = data.get('meter_id')
        timestamp_str = data.get('timestamp')
        reading = data.get('reading')

        # 校验电表 ID 是否在 user_dict 中（注意：本示例中 user_dict 的 key 为 "1", "2", "3"）
        if meter_id not in user_dict:
            return jsonify({'status': 'error', 'message': 'Invalid meter_id'}), 400

        # 将 ISO 格式的时间戳转换为 "YYYY-MM-DD HH:MM" 格式
        try:
            timestamp = datetime.fromisoformat(
                timestamp_str).strftime("%Y-%m-%d %H:%M")
        except Exception as e:
            return jsonify({'status': 'error', 'message': 'Invalid timestamp format'}), 400

        # 初始化该电表的数据列表（如果不存在）
        if meter_id not in meter_data:
            meter_data[meter_id] = []
        # 保存本次读数
        meter_data[meter_id].append({
            'timestamp': timestamp,
            'reading': reading
        })

        # 调试输出，可根据需要注释掉
        print("当前所有电表读数数据：")
        for mid, records in meter_data.items():
            print(f"Meter {mid}:")
            for rec in records:
                print(f"  {rec}")

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# =============================================================================
# 3. 用户注册部分（Dash 应用）——数据准备及注册回调
# =============================================================================


# 尝试加载或初始化存储的注册用户数据
try:
    with open("store_user_data.json", "r") as f:
        store_user_data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    store_user_data = {}
    with open("store_user_data.json", "w") as f:
        json.dump({}, f, indent=4)

# 当前用户 ID（当 store_user_data 不为空时取最大值，否则从 0 开始）
if store_user_data:
    current_id = max(map(int, store_user_data.keys())) + 1
else:
    current_id = 0

# 模拟区域数据与住宅类型数据
area_data = pd.DataFrame({
    "AreaID": [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010,
               1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020,
               1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028, 1029, 1030,
               1031, 1032, 1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040,
               1041, 1042, 1043, 1044, 1045, 1046, 1047],
    "Area": ["Bishan", "Sembawang", "Yishun", "Outram", "Kallang", "North Region", "Bukit Batok", "Sengkang", "Clementi", "Woodlands",
             "Choa Chu Kang", "Serangoon", "Central Region", "Tampines", "North East Region", "Ang Mo Kio", "Toa Payoh", "Bedok", "East Region", "Jurong East",
             "Hougang", "Bukit Merah", "West Region", "Queenstown", "Geylang", "Novena", "Jurong West", "Marine Parade", "Rochor", "Pioneer",
             "Pasir Ris", "Paya Lebar", "Mandai", "Downtown", "Seletar", "Sungei Kadut", "Bukit Panjang", "Museum", "Singapore River", "Bukit Timah",
             "Changi", "River Valley", "Tanglin", "Punggol", "Orchard", "Southern Islands", "Newton"],
    "Region": ["Central Region", "North Region", "North Region", "Central Region", "Central Region", "North Region", "West Region", "North East Region", "West Region", "North Region",
               "West Region", "North East Region", "Central Region", "East Region", "North East Region", "North East Region", "Central Region", "East Region", "East Region", "West Region",
               "North East Region", "Central Region", "West Region", "Central Region", "Central Region", "Central Region", "West Region", "Central Region", "Central Region", "West Region",
               "East Region", "East Region", "North Region", "Central Region", "North East Region", "North Region", "West Region", "Central Region", "Central Region", "Central Region",
               "East Region", "Central Region", "Central Region", "North East Region", "Central Region", "Central Region", "Central Region"]
})

dwelling_data = pd.DataFrame({
    "TypeID": [1, 2, 3, 4, 5, 6],
    "DwellingType": [
        "1-room / 2-room",
        "Private Apartments and Condominiums",
        "Landed Properties",
        "5-room and Executive",
        "3-room",
        "4-room"
    ]
})

# 区域与区域内街道映射
region_area_mapping = area_data.groupby('Region')['Area'].apply(list).to_dict()


def create_registration_app(flask_server):
    reg_app = dash_app.Dash("registration_app", server=flask_server,
                        url_base_pathname='/register/')
    reg_app.layout = html.Div([
        html.Div([
            html.H2("New User Registration", style={'textAlign': 'center'}),
            html.Label("MeterID:"),
            dcc.Input(id='meter-id', type='text',
                      placeholder='Enter 9 digits MeterID', style={'width': '100%'}),
            html.Br(),
            html.Label("Region:"),
            dcc.Dropdown(
                id='region',
                options=[{'label': r, 'value': r}
                         for r in region_area_mapping.keys()],
                placeholder='Select a Region',
                style={'width': '100%'}
            ),
            html.Br(),
            html.Label("Area:"),
            dcc.Dropdown(id='area', placeholder='Select an Area',
                         disabled=True, style={'width': '100%'}),
            html.Br(),
            html.Label("Dwelling Type:"),
            dcc.Dropdown(
                id='dwelling-type',
                options=[{'label': dt_val, 'value': dt_val}
                         for dt_val in dwelling_data['DwellingType']],
                placeholder='Select a Dwelling Type',
                style={'width': '100%'}
            ),
            html.Br(),
            html.Button("Submit", id='submit-btn', n_clicks=0,
                        style={'width': '100%', 'padding': '10px', 'fontSize': '16px'}),
            html.Br(),
            html.Div(id='output', style={
                     'textAlign': 'center', 'marginTop': '20px'})
        ], style={'maxWidth': '500px', 'margin': 'auto', 'padding': '20px',
                  'border': '1px solid #ddd', 'borderRadius': '10px',
                  'boxShadow': '2px 2px 10px rgba(0,0,0,0.1)'})
    ])

    @reg_app.callback(
        [Output('area', 'options'), Output('area', 'disabled')],
        [Input('region', 'value')]
    )
    def update_area_options(selected_region):
        if selected_region:
            return ([{'label': area, 'value': area} for area in region_area_mapping[selected_region]], False)
        return ([], True)

    @reg_app.callback(
        Output('output', 'children'),
        [Input('submit-btn', 'n_clicks')],
        [State('meter-id', 'value'),
         State('region', 'value'),
         State('area', 'value'),
         State('dwelling-type', 'value')]
    )
    def update_output(n_clicks, meter_id, region, area, dwelling_type):
        global current_id, store_user_data
        if n_clicks > 0:
            if not meter_id or not region or not area or not dwelling_type:
                return html.P("Please fill in all fields.", style={'color': 'red'})
            if not re.fullmatch(r"\d{9}", meter_id):
                return html.P("Invalid MeterID format!", style={'color': 'red'})
            if any(user['MeterID'] == meter_id for user in store_user_data.values()):
                return html.P("This MeterID is already registered.", style={'color': 'red'})
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_data = {
                'MeterID': meter_id,
                'Region': region,
                'Area': area,
                'DwellingType': dwelling_type,
                'TimeStamp': timestamp
            }
            current_id += 1
            store_user_data[str(current_id)] = user_data
            with open("store_user_data.json", "w") as f:
                json.dump(store_user_data, f, indent=4)
            return html.P("Submission successful!", style={'color': 'green'})
        return ""

    return reg_app

# =============================================================================
# 4. 用户查询部分（Dash 应用）——查询电量数据并展示图表与表格
# =============================================================================

# 为查询提供一个辅助函数，用于根据起始时间过滤数据


def get_meter_data(meter_id, start_time):
    if meter_id not in meter_data:
        return []
    records = meter_data[meter_id]
    filtered = []
    for record in records:
        try:
            record_time = datetime.strptime(
                record['timestamp'], "%Y-%m-%d %H:%M")
        except Exception:
            continue
        if record_time >= start_time:
            filtered.append(record)
    return filtered


def create_user_query_app(flask_server):
    query_app = dash_app.Dash("query_app", server=flask_server,
                          url_base_pathname='/query/')
    query_app.layout = html.Div([
        html.H2("Electricity Usage Query"),
        html.Label("Meter ID:"),
        dcc.Input(id="meter_id", type="text",
                  placeholder="Enter Meter ID", value="000000001"),
        html.Br(), html.Br(),
        html.Label("Select Time Period:"),
        dcc.Dropdown(
            id="period",
            options=[
                {"label": "Last 30 Minutes", "value": "30m"},
                {"label": "Last 1 Day", "value": "1d"},
                {"label": "Last 1 Week", "value": "1w"},
                {"label": "Last 1 Month", "value": "1m"},
                {"label": "This Year", "value": "1y"},
            ],
            value="1d"
        ),
        html.Br(),
        html.Button("Get Usage", id="get_usage", n_clicks=0),
        html.Br(), html.Br(),
        dcc.Graph(id="usage_chart"),
        dash_table.DataTable(id="usage_table",
                             columns=[
                                 {"name": "Timestamp", "id": "timestamp"},
                                 {"name": "Reading (kWh)", "id": "reading"}
                             ],
                             data=[],
                             style_table={'overflowX': 'auto'})
    ])

    @query_app.callback(
        [Output("usage_table", "data"), Output("usage_chart", "figure")],
        [Input("get_usage", "n_clicks"),
         Input("meter_id", "value"),
         Input("period", "value")]
    )
    def update_usage(n_clicks, meter_id, period):
        if not meter_id:
            return [], {}
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
            return [], {}

        data = get_meter_data(meter_id, start_time)
        if not data:
            return [], {}

        df = pd.DataFrame(data)
        figure = {
            "data": [
                {"x": df["timestamp"], "y": df["reading"],
                    "type": "bar", "name": "Usage"}
            ],
            "layout": {"title": "Electricity Usage Over Time"}
        }
        return data, figure

    return query_app

# =============================================================================
# 5. 初始化模拟数据、创建 Dash 应用并启动服务器
# =============================================================================


# 如果 "000000001" 的数据为空，则生成每天 48 个数据点（每 30 分钟一个）
if "000000001" not in meter_data or not meter_data["000000001"]:
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    meter_data["000000001"] = []
    for i in range(48):
        t = now + timedelta(minutes=i*30)
        meter_data["000000001"].append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M"),
            "reading": random.randint(100, 500)
        })

# 创建两个 Dash 子应用（注册 & 查询），均绑定在同一 Flask 服务器上
registration_app = create_registration_app(server)
query_app = create_user_query_app(server)

if __name__ == '__main__':
    # 启动 Flask 服务器，Dash 子应用将随之挂载（本例监听 8050 端口）
    server.run(debug=True, port=8050)
