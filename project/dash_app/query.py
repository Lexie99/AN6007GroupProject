# dash/dash_query.py

import os
import dash
from dash import dcc, html, Input, Output, State, dash_table
import requests
import pandas as pd

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")
QUERY_ENDPOINT = f"{API_BASE_URL}/api/user/query"

def create_query_app(flask_server):
    query_app = dash.Dash("query_app", server=flask_server, url_base_pathname='/query/')
    
    query_app.layout = html.Div([
        html.H2("Electricity Usage Query", style={'textAlign':'center'}),

        html.Label("Meter ID:"),
        dcc.Input(id="meter_id", type="text", placeholder="Enter 9-digit Meter ID",
                  style={"width":"100%","height":"30px"}),
        html.Br(), html.Br(),

        html.Label("Select Time Period:"),
        dcc.Dropdown(
            id="period",
            options=[
                {"label": "Last 30 Minutes", "value": "30m"},
                {"label": "Last 1 Day", "value": "1d"},
                {"label": "Last 1 Week", "value": "1w"},
                {"label": "Last 1 Month", "value": "1m"},
                {"label": "This Year", "value": "1y"}
            ],
            value="1d",
            style={"width": "100%"}
        ),
        html.Br(),
        html.Button("Get Usage", id="get_usage", n_clicks=0,
                    style={"width": "10%", "padding": "10px", "fontSize": "16px"}),
        html.Br(),

        html.Div(id="error_message", style={"color": "red", "textAlign": "center"}),

        dcc.Graph(id="usage_chart"),
        dash_table.DataTable(
            id="usage_table",
            columns=[
                {"name": "Date", "id": "date"},
                {"name": "Consumption (kWh)", "id": "consumption"}
            ],
            style_table={"overflowX": "auto"}
        )
    ])

    @query_app.callback(
        [Output("usage_table", "data"),
         Output("usage_chart", "figure"),
         Output("error_message", "children")],
        [Input("get_usage", "n_clicks")],
        [State("meter_id", "value"), State("period", "value")]
    )
    def update_usage(n_clicks, meter_id, period):
        if not meter_id or not meter_id.isdigit() or len(meter_id) != 9:
            return [], {}, "Invalid Meter ID (must be 9-digit)!"

        try:
            params = {"meter_id": meter_id, "period": period}
            resp = requests.get(QUERY_ENDPOINT, params=params)
            resp.raise_for_status()
            result = resp.json()
            if result.get("status") != "success":
                return [], {}, f"Error: {result.get('message', 'Unknown error')}"
        except requests.exceptions.RequestException as e:
            return [], {}, f"Request error: {e}"
        except Exception as e:
            return [], {}, f"Exception: {str(e)}"

        # 处理返回数据，根据不同 period 绘图和表格展示数据

        # 1) 30分钟：直接累计该时间段内的 consumption
        if "increment_last_30m" in result:
            inc = result["increment_last_30m"]
            table_data = [{"date": "Last 30 min", "consumption": inc}]
            fig = {
                "data": [{"x": ["Last 30 min"], "y": [inc], "type": "bar"}],
                "layout": {"title": "Usage in Last 30 Minutes"}
            }
            return table_data, fig, ""

        # 2) 1d：返回半小时增量数据列表（每条记录包含 time 与 consumption）
        if "usage_list" in result:
            usage_list = result["usage_list"]
            df = pd.DataFrame(usage_list)  # 每条记录格式：{"time": "...", "consumption": ...}
            if df.empty:
                return [], {}, "No usage data available"
            fig = {
                "data": [{
                    "x": df["time"],
                    "y": df["consumption"],
                    "type": "bar",
                    "name": "Half-Hour Usage"
                }],
                "layout": {"title": f"1-Day Usage (Total: {result.get('total_usage', 0):.2f} kWh)"}
            }
            table_data = [{"date": row["time"], "consumption": row["consumption"]} for _, row in df.iterrows()]
            return table_data, fig, ""

        # 3) 1w/1m：按天聚合数据，返回每日总消费
        if "daily_usage" in result:
            daily_list = result["daily_usage"]
            df = pd.DataFrame(daily_list)  # 每条记录格式：{"date": "YYYY-MM-DD", "consumption": ...}
            if df.empty:
                return [], {}, "No daily usage data available"
            fig = {
                "data": [{"x": df["date"], "y": df["consumption"], "type": "bar"}],
                "layout": {"title": f"Daily Usage (Total: {result.get('total_usage', 0):.2f} kWh)"}
            }
            table_data = [{"date": row["date"], "consumption": row["consumption"]} for _, row in df.iterrows()]
            return table_data, fig, ""

        # 4) 1y：按月份聚合数据，返回每月总消费
        if "monthly_usage" in result:
            monthly_list = result["monthly_usage"]
            df = pd.DataFrame(monthly_list)  # 每条记录格式：{"month": "YYYY-MM", "consumption": ...}
            if df.empty:
                return [], {}, "No monthly usage data available"
            fig = {
                "data": [{"x": df["month"], "y": df["consumption"], "type": "bar"}],
                "layout": {"title": f"Monthly Usage (Total: {result.get('total_usage', 0):.2f} kWh)"}
            }
            table_data = [{"date": row["month"], "consumption": row["consumption"]} for _, row in df.iterrows()]
            return table_data, fig, ""

        return [], {}, "Unsupported data format."

    return query_app
