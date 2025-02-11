# -*- coding: utf-8 -*-
"""
Created on Tue Feb 11 15:25:43 2025

@author: ASUS
"""
# user_query.py
import dash
from dash import dcc, html, Input, Output
from dash import dash_table
import pandas as pd
from datetime import datetime, timedelta
import random

# 从内部 API 模块中引入数据获取函数
from MeterReading_api import get_meter_data, meter_data

# 如果没有数据，则初始化模拟数据（每天48个数据点，每30分钟一个）
if "000000001" not in meter_data or not meter_data["000000001"]:
    now = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    meter_data["000000001"] = []
    for i in range(48):
        t = now + timedelta(minutes=i*30)
        meter_data["000000001"].append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M"),
            "reading": random.randint(100, 500)
        })

def create_user_query_app(server):
    query_app = dash.Dash(__name__, server=server, url_base_pathname='/query/')
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
                {"x": df["timestamp"], "y": df["reading"], "type": "bar", "name": "Usage"}
            ],
            "layout": {"title": "Electricity Usage Over Time"}
        }
        return data, figure

    return query_app

if __name__ == '__main__':
    from flask import Flask
    server = Flask(__name__)
    app = create_user_query_app(server)
    app.run_server(debug=True, port=8051)
