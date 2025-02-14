import os
import dash
from dash import dcc, html, Input, Output, State
import requests

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8050")
REGISTER_ENDPOINT = f"{API_BASE_URL}/api/user/register"
REGION_AREA_ENDPOINT = f"{API_BASE_URL}/api/user/region-area"
DWELLING_ENDPOINT = f"{API_BASE_URL}/api/user/dwelling-types"

def create_registration_app(flask_server):
    reg_app = dash.Dash("registration_app", server=flask_server, url_base_pathname='/register/')

    # 初始空，稍后在回调或layout加载时获取
    reg_app.layout = html.Div([
        html.H2("New User Registration", style={'textAlign': 'center'}),

        html.Label("MeterID:"),
        dcc.Input(id='meter-id', type='text', placeholder='Enter 9 digits MeterID', style={'width': '99%',"height":"30px"}),
        html.Br(), html.Br(),

        html.Label("Region:"),
        dcc.Dropdown(id='region', placeholder='Select a Region', style={'width': '100%'}),
        html.Br(),

        html.Label("Area:"),
        dcc.Dropdown(id='area', placeholder='Select an Area', disabled=True, style={'width': '100%'}),
        html.Br(),

        html.Label("Dwelling Type:"),
        dcc.Dropdown(id='dwelling-type', placeholder='Select a Dwelling Type', style={'width': '100%'}),
        html.Br(),

        html.Button("Submit", id='submit-btn', n_clicks=0,
                    style={'width': '100%', 'padding': '10px', 'fontSize': '16px'}),
        html.Br(),

        html.Div(id='output', style={'textAlign': 'center', 'marginTop': '20px'})
    ], style={
        'maxWidth': '500px',
        'margin': 'auto',
        'padding': '20px',
        'border': '1px solid #ddd',
        'borderRadius': '10px',
        'boxShadow': '2px 2px 10px rgba(0,0,0,0.1)'
    })

    # **🔹 启动时加载 region/area & dwelling-type 选项 (用一个回调 or layout load)**
    @reg_app.callback(
        [Output('region', 'options'),
         Output('dwelling-type', 'options')],
        [Input('region', 'id')]  # 一个dummy触发，也可用 dash.no_update
    )
    def load_options(_):
        """
        第一次布局加载时被调用。可以用更优的方式防止重复加载。
        """
        try:
            # 获取 region_area 数据
            resp1 = requests.get(REGION_AREA_ENDPOINT)
            region_area_data = resp1.json() if resp1.status_code == 200 else {}

            # region_area_data 形如 {"North Region": ["Sembawang", "Yishun"], ...}
            region_options = [{"label": reg, "value": reg} for reg in sorted(region_area_data.keys())]

            # 获取 dwelling_types
            resp2 = requests.get(DWELLING_ENDPOINT)
            dwellings = resp2.json() if resp2.status_code == 200 else []
            dwelling_options = [{"label": d, "value": d} for d in sorted(dwellings)]

            return region_options, dwelling_options
        except Exception:
            return [], []

    # **🔹 动态更新 area 选项**
    @reg_app.callback(
        Output('area', 'options'),
        Output('area', 'disabled'),
        Input('region', 'value')
    )
    def update_area_options(selected_region):
        try:
            if not selected_region:
                return [], True
            # 再次向后端拿当前region对应的areas
            # 也可在前面 load_options 回调里保存 region_area_data 到 dcc.Store
            # 这里为简单起见再次请求
            resp = requests.get(REGION_AREA_ENDPOINT)
            region_area_data = resp.json() if resp.status_code == 200 else {}

            if selected_region not in region_area_data:
                return [], True
            area_list = region_area_data[selected_region]
            area_opts = [{'label': a, 'value': a} for a in sorted(area_list)]
            return area_opts, False
        except Exception:
            return [], True

    # **🔹 提交注册**
    @reg_app.callback(
        Output('output', 'children'),
        [Input('submit-btn', 'n_clicks')],
        [State('meter-id', 'value'),
         State('region', 'value'),
         State('area', 'value'),
         State('dwelling-type', 'value')]
    )
    def register_user(n_clicks, meter_id, region, area, dwelling_type):
        if n_clicks > 0:
            payload = {
                'meter_id': meter_id,
                'region': region,
                'area': area,
                'dwelling_type': dwelling_type
            }
            try:
                response = requests.post(REGISTER_ENDPOINT, json=payload)
                result = response.json()
                if result.get('status') == 'success':
                    return html.P(result.get('message'), style={'color': 'green'})
                else:
                    return html.P(result.get('message'), style={'color': 'red'})
            except Exception as e:
                return html.P(f"Error: {str(e)}", style={'color': 'red'})
        return ""

    return reg_app
