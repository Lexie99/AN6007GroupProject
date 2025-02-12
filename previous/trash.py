# -*- coding: utf-8 -*-
"""
Created on Tue Feb 11 14:57:06 2025

@author: ASUS
"""
from flask import Flask
from MeterReading_api import meter_api
from Registration_frontend_v2 import create_registration_app
from user_query import create_user_query_app
from dash_app import Dash, html, dcc

server = Flask(__name__)

# 注册电表读数 API 蓝图
# （注意：虽然注册了该路由，但该接口仅供内部调用，不建议前端直接访问）
server.register_blueprint(meter_api)

landing_app = Dash(__name__, server=server, url_base_pathname='/')
landing_app.layout = html.Div([
    html.H1("Welcome to our App!"),
    html.Br(),
    dcc.Link("Go to Registration", href="/register/", style={'fontSize': '20px', 'margin': '10px'}),
    dcc.Link("Go to User Query", href="/query/", style={'fontSize': '20px', 'margin': '10px'})
])

# 创建两个 Dash 应用：注册和电力使用查询
registration_app = create_registration_app(server)
user_query_app = create_user_query_app(server)

if __name__ == '__main__':
    server.run(host='0.0.0.0', port=8000, debug=True)
