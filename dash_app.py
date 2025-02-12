# dash_app.py
import os
import dash
from dash import dcc, html, Input, Output, State, dash_table
import requests
import pandas as pd
# 从 api.py 导入区域映射数据和住宅数据（这些数据从 JSON 配置中加载）
from api import region_area_mapping, dwelling_data

# 从环境变量中读取 API 基础 URL，如果未设置则默认使用 http://127.0.0.1:8050
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8050")
# 定义各接口的 URL
REGISTER_ENDPOINT = f"{API_BASE_URL}/api/user/register"
QUERY_ENDPOINT = f"{API_BASE_URL}/api/meter/query"

def create_registration_app(flask_server):
    reg_app = dash.Dash("registration_app", server=flask_server,
                          url_base_pathname='/register/')
    reg_app.layout = html.Div([
        html.Div([
            html.H2("New User Registration", style={'textAlign': 'center'}),
            html.Label("MeterID:"),
            dcc.Input(id='meter-id', type='text', placeholder='Enter 9 digits MeterID', style={'width': '100%'}),
            html.Br(),
            html.Label("Region:"),
            dcc.Dropdown(
                id='region',
                options=[{'label': r, 'value': r} for r in region_area_mapping.keys()],
                placeholder='Select a Region',
                style={'width': '100%'}
            ),
            html.Br(),
            html.Label("Area:"),
            dcc.Dropdown(id='area', placeholder='Select an Area', disabled=True, style={'width': '100%'}),
            html.Br(),
            html.Label("Dwelling Type:"),
            dcc.Dropdown(
                id='dwelling-type',
                options=[{'label': dt, 'value': dt} for dt in dwelling_data['DwellingType']],
                placeholder='Select a Dwelling Type',
                style={'width': '100%'}
            ),
            html.Br(),
            html.Button("Submit", id='submit-btn', n_clicks=0,
                        style={'width': '100%', 'padding': '10px', 'fontSize': '16px'}),
            html.Br(),
            html.Div(id='output', style={'textAlign': 'center', 'marginTop': '20px'})
        ], style={'maxWidth': '500px', 'margin': 'auto', 'padding': '20px',
                  'border': '1px solid #ddd', 'borderRadius': '10px',
                  'boxShadow': '2px 2px 10px rgba(0,0,0,0.1)'})
    ])

    # 根据 Region 更新 Area 下拉选项
    @reg_app.callback(
        [Output('area', 'options'), Output('area', 'disabled')],
        [Input('region', 'value')]
    )
    def update_area_options(selected_region):
        if selected_region:
            return ([{'label': area, 'value': area} for area in region_area_mapping[selected_region]], False)
        return ([], True)

    # 通过调用 API 完成用户注册
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

def create_query_app(flask_server):
    query_app = dash.Dash("query_app", server=flask_server,
                            url_base_pathname='/query/')
    query_app.layout = html.Div([
        html.H2("Electricity Usage Query"),
        html.Label("Meter ID:"),
        dcc.Input(id="meter_id", type="text", placeholder="Enter Meter ID", value="000000001"),
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

    # 调用 API 进行数据查询
    @query_app.callback(
        [Output("usage_table", "data"), Output("usage_chart", "figure")],
        [Input("get_usage", "n_clicks"),
         Input("meter_id", "value"),
         Input("period", "value")]
    )
    def update_usage(n_clicks, meter_id, period):
        if not meter_id:
            return [], {}
        try:
            params = {'meter_id': meter_id, 'period': period}
            response = requests.get(QUERY_ENDPOINT, params=params)
            result = response.json()
            if result.get('status') != 'success':
                return [], {}
            data = result.get('data', [])
        except Exception as e:
            return [], {}

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
