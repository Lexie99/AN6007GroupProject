# dash/dash_register.py

import os
import dash
from dash import dcc, html, Input, Output, State
from config.app_config import AppConfig   # 直接导入你的 AppConfig
import sys
import requests

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")
REGISTER_ENDPOINT = f"{API_BASE_URL}/api/user/register"

def create_registration_app(flask_server):
    reg_app = dash.Dash("registration_app", server=flask_server, url_base_pathname='/register/')

    # 1) 在进程启动时就加载 config，拿到 region->area、dwelling
    app_config = AppConfig()
    region_area_data = app_config.region_area_mapping  # dict[region] = set(area)
    dwelling_set = app_config.dwelling_type_set        # set of dwelling strings

    # 构造 region dropdown初始选项
    region_options = [{'label': r, 'value': r} for r in sorted(region_area_data.keys())]
    # dwelling dropdown初始选项
    dwelling_options = [{'label': d, 'value': d} for d in sorted(dwelling_set)]

    # 2) Dash Layout
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

    # 3) 动态更新 area dropdown: 当 region 改变时
    @reg_app.callback(
        [Output('area', 'options'), Output('area', 'disabled')],
        [Input('region', 'value')]
    )
    def update_area_options(selected_region):
        if not selected_region:
            return [], True

        # 直接从 region_area_data 获取
        if selected_region not in region_area_data:
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
        if n_clicks>0:
            if not meter_id or not region or not area or not dwelling_type:
                return "Please fill in all fields."
            payload = {
                'meter_id': meter_id,
                'region': region,
                'area': area,
                'dwelling_type': dwelling_type
            }
            try:
                resp = requests.post(REGISTER_ENDPOINT, json=payload)
                data = resp.json()
                if data.get('status')=='success':
                    return html.P(data.get('message'), style={'color':'green'})
                else:
                    return html.P(data.get('message'), style={'color':'red'})
            except Exception as e:
                return html.P(f"Error: {str(e)}", style={'color':'red'})
        return ""

    return reg_app
