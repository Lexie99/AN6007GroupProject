import os
import dash
from dash import dcc, html, Input, Output, State
import requests
from api.user_management import region_area_mapping, dwelling_data  # 从项目中导入数据

# 从环境变量中读取 API 基础 URL，如果未设置则默认使用 http://127.0.0.1:8050
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8050")
REGISTER_ENDPOINT = f"{API_BASE_URL}/api/user/register"

def create_registration_app(flask_server):
    reg_app = dash.Dash("registration_app", server=flask_server, url_base_pathname='/register/')

    # **🔹 更新 Layout**
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
                options=[{'label': dt, 'value': dt} for dt in dwelling_data.values()],
                placeholder='Select a Dwelling Type',
                style={'width': '100%'}
            ),
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
    ])

    # **🔹 根据 `region` 选择更新 `area` 选项**
    @reg_app.callback(
        [Output('area', 'options'), Output('area', 'disabled')],
        Input('region', 'value')
    )
    def update_area_options(selected_region):
        if selected_region:
            return ([{'label': area, 'value': area} for area in region_area_mapping[selected_region]], False)
        return ([], True)

    # **🔹 处理用户注册**
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
