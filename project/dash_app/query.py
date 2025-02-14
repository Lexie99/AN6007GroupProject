import os
import dash
from dash import dcc, html, Input, Output, State, dash_table
import requests
import pandas as pd

API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8050")
QUERY_ENDPOINT = f"{API_BASE_URL}/api/user/query"

def create_query_app(flask_server):
    query_app = dash.Dash("query_app", server=flask_server, url_base_pathname='/query/')
    
    query_app.layout = html.Div([
        html.H2("Electricity Usage Query", style={'textAlign': 'center'}),

        html.Label("Meter ID:"),
        dcc.Input(id="meter_id", type="text", placeholder="Enter 9-digit Meter ID", 
                  style={"width": "100%", "height": "30px"}),
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
            value="1d",
            style={"width": "100%"}
        ),
        html.Br(),html.Br(),

        html.Button("Get Usage", id="get_usage", n_clicks=0,
                    style={"width": "10%", "padding": "10px", "fontSize": "16px"}),
        html.Br(),

        html.Div(id="error_message", style={'color': 'red', 'textAlign': 'center'}),

        dcc.Graph(id="usage_chart"),
        dash_table.DataTable(
            id="usage_table",
            columns=[
                {"name": "Date", "id": "date"},
                {"name": "Consumption (kWh)", "id": "consumption"}
            ],
            style_table={'overflowX': 'auto'}
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
            return [], {}, "Invalid Meter ID. Please enter a 9-digit number."

        try:
            params = {'meter_id': meter_id, 'period': period}
            response = requests.get(QUERY_ENDPOINT, params=params)
            if response.status_code != 200:
                return [], {}, f"API call failed with status code {response.status_code}"
            
            result = response.json()
            if result.get('status') != 'success':
                msg = result.get('message', 'Unknown Error')
                return [], {}, f"Query failed: {msg}"

            # 如果后端直接返回 data = "No data available"
            if isinstance(result.get('data'), str):
                return [], {}, result['data']

            # ========== 30 分钟增量 ==========
            if "increment_last_30m" in result:
                inc_30m = result["increment_last_30m"]
                data_table = [{"date": "Last 30 min", "consumption": inc_30m}]
                figure = {
                    "data": [{
                        "x": ["Last 30 min"],
                        "y": [inc_30m],
                        "type": "bar",
                        "name": "30m Usage"
                    }],
                    "layout": {"title": "Last 30 Minutes Usage"}
                }
                return data_table, figure, ""

            # ========== 固定时间范围 & 日用电量 ==========
            # 这里我们只读 "daily_usage" 和 "total_usage"
            daily_usage = result.get("daily_usage", {})
            if not daily_usage:
                return [], {}, "No daily usage data found."

            total_usage_str = ""
            if "total_usage" in result:
                total_val = result["total_usage"]
                total_usage_str = f" (Total: {total_val:.2f} kWh)"

            data = [{"date": day, "consumption": val} for day, val in daily_usage.items()]
            if not data:
                return [], {}, "No data to display"

            df = pd.DataFrame(data)
            figure = {
                "data": [{
                    "x": df["date"],
                    "y": df["consumption"],
                    "type": "bar",
                    "name": "Daily Usage"
                }],
                "layout": {"title": f"Electricity Usage Over Time{total_usage_str}"}
            }

            return data, figure, ""

        except Exception as e:
            return [], {}, f"Error: {str(e)}"

    return query_app
