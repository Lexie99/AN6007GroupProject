import os
import dash
from dash import dcc, html, Input, Output, State
from config.app_config import AppConfig
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")
REGISTER_ENDPOINT = f"{API_BASE_URL}/api/user/register"

def create_registration_app(flask_server):
    """创建用户注册前端应用"""
    # 若 AppConfig 需要传入配置文件路径，可通过环境变量传入，否则使用默认构造函数
    config_path = os.getenv("CONFIG_PATH", "project/config/config.json")
    app_config = AppConfig(config_path=config_path)
    
    # 创建 Dash 应用，并指定 URL 路径前缀
    reg_app = dash.Dash("registration_app", server=flask_server, url_base_pathname='/register/')
    
    # 从配置中获取区域与居住类型数据
    region_area_data = app_config.region_area_mapping
    dwelling_set = app_config.dwelling_type_set

    # 构造 region 和 dwelling 的选项列表
    region_options = [{'label': r, 'value': r} for r in sorted(region_area_data.keys())]
    dwelling_options = [{'label': d, 'value': d} for d in sorted(dwelling_set)]

    # 定义前端布局
    reg_app.layout = html.Div([
        html.H2("New User Registration", style={'textAlign': 'center'}),
        html.Label("Meter ID:"),
        dcc.Input(id='meter-id', type='text', placeholder='Enter 9 digits MeterID',
                  style={'width': '99%', "height": "30px"}),
        html.Br(), html.Br(),
        html.Label("Region:"),
        dcc.Dropdown(id='region', options=region_options, placeholder='Select a Region', style={'width': '100%'}),
        html.Br(),
        html.Label("Area:"),
        dcc.Dropdown(id='area', options=[], placeholder='Select an Area', disabled=True, style={'width': '100%'}),
        html.Br(),
        html.Label("Dwelling Type:"),
        dcc.Dropdown(id='dwelling-type', options=dwelling_options, placeholder='Select a Dwelling Type',
                     style={'width': '100%'}),
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

    @reg_app.callback(
        [Output('area', 'options'), Output('area', 'disabled')],
        [Input('region', 'value')]
    )
    def update_area_options(selected_region):
        """根据所选 Region 动态更新 Area 选项"""
        if not selected_region or selected_region not in region_area_data:
            return [], True
        area_list = sorted(region_area_data[selected_region])
        area_opts = [{'label': a, 'value': a} for a in area_list]
        return area_opts, False

    @reg_app.callback(
        Output('output', 'children'),
        [Input('submit-btn', 'n_clicks')],
        [State('meter-id', 'value'),
         State('region', 'value'),
         State('area', 'value'),
         State('dwelling-type', 'value')]
    )
    def register_user(n_clicks, meter_id, region, area, dwelling_type):
        """提交用户注册请求"""
        if n_clicks > 0:
            # 检查所有字段是否均已填写
            if not all([meter_id, region, area, dwelling_type]):
                return "Please fill in all fields."
            payload = {
                'meter_id': meter_id,
                'region': region,
                'area': area,
                'dwelling_type': dwelling_type
            }
            try:
                # 向后端注册 API 发起 POST 请求
                resp = requests.post(REGISTER_ENDPOINT, json=payload)
                data = resp.json()
                if data.get('status') == 'success':
                    return html.P(data.get('message'), style={'color': 'green'})
                else:
                    return html.P(data.get('message'), style={'color': 'red'})
            except Exception as e:
                return html.P(f"Error: {str(e)}", style={'color': 'red'})
        return ""

    return reg_app
