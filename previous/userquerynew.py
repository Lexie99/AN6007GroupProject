# -*- coding: utf-8 -*-
"""
Created on Fri Feb  7 18:32:05 2025

@author: Dell
"""

import project.dash_app.register as register
from project.dash_app.register import dcc, html, Input, Output, State
import dash_table
import datetime
import pandas as pd
import random

# 初始化 Dash 应用
app = register.Dash(__name__, routes_pathname_prefix="/user/query/")
server = app.server  # 适用于部署

# 生成模拟电表数据，每30分钟记录一次，确保从00:00到23:30
now = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
electricity_data = {
    "000000001": [
        {"timestamp": now + datetime.timedelta(minutes=i*30), "reading": random.randint(100, 500)}
        for i in range(48)  # 每天48个数据点
    ]
}

# Dash 应用布局
app.layout = html.Div([
    html.H2("Electricity Usage Query"),
    html.Label("Meter ID:"),
    dcc.Input(id="meter_id", type="text", placeholder="Enter Meter ID"),
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

# 交互回调
@app.callback(
    [Output("usage_table", "data"), Output("usage_chart", "figure")],
    [Input("get_usage", "n_clicks")],
    [State("meter_id", "value"), State("period", "value")]
)
def update_table(n_clicks, meter_id, period):
    if not meter_id or meter_id not in electricity_data:
        return [], {}
    
    now = datetime.datetime.utcnow()
    if period == "30m":
        start_time = now - datetime.timedelta(minutes=30)
    elif period == "1d":
        start_time = now - datetime.timedelta(days=1)
    elif period == "1w":
        start_time = now - datetime.timedelta(weeks=1)
    elif period == "1m":
        start_time = now - datetime.timedelta(days=30)
    elif period == "1y":
        start_time = now - datetime.timedelta(days=365)
    else:
        return [], {}
    
    # 使用二分查找优化查询
    usage = sorted(electricity_data[meter_id], key=lambda x: x["timestamp"])  # 确保数据按时间排序
    df = pd.DataFrame([entry for entry in usage if entry["timestamp"] >= start_time])
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M")  # 转换时间格式
    
    figure = {
        "data": [
            {"x": df["timestamp"], "y": df["reading"], "type": "bar", "name": "Usage"}
        ],
        "layout": {"title": "Electricity Usage Over Time"}
    }
    
    return df.to_dict("records"), figure

# 运行应用
if __name__ == "__main__":
    app.run_server(debug=True)
