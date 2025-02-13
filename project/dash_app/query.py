import os
import dash
from dash import dcc, html, Input, Output, State, dash_table
import requests
import pandas as pd

# 从环境变量中读取 API 基础 URL，如果未设置则默认使用 http://127.0.0.1:8050
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8050")
QUERY_ENDPOINT = f"{API_BASE_URL}/api/meter/query"

def create_query_app(flask_server):
    query_app = dash.Dash("query_app", server=flask_server, url_base_pathname='/query/')
    
    query_app.layout = html.Div([
        html.H2("Electricity Usage Query"),

        html.Label("Meter ID:"),
        dcc.Input(id="meter_id", type="text", placeholder="Enter 9-digit Meter ID"),

        html.Label("Select Time Period:"),
        dcc.Dropdown(
            id="period",
            options=[
                {"label": "Last 30 Minutes", "value": "30m"},
                {"label": "Last 1 Day", "value": "1d"},
                {"label": "Last 1 Week", "value": "1w"},
                {"label": "Last 1 Month", "value": "1m"},
                {"label": "This Year", "value": "1y"},
                {"label": "Custom Range", "value": "custom"}
            ],
            value="1d"
        ),

        html.Div([
            html.Label("Start Date:"),
            dcc.Input(id="start_date", type="date"),
            html.Label("End Date:"),
            dcc.Input(id="end_date", type="date"),
        ], id="custom_date_inputs", style={"display": "none"}),

        html.Button("Get Usage", id="get_usage", n_clicks=0),

        dcc.Graph(id="usage_chart"),
        dash_table.DataTable(id="usage_table",
                             columns=[
                                 {"name": "Date", "id": "date"},
                                 {"name": "Consumption (kWh)", "id": "consumption"}
                             ],
                             style_table={'overflowX': 'auto'})
    ])

    @query_app.callback(
        [Output("usage_table", "data"), Output("usage_chart", "figure")],
        [Input("get_usage", "n_clicks")],
        [State("meter_id", "value"), State("period", "value"), State("start_date", "value"), State("end_date", "value")]
    )
    def update_usage(n_clicks, meter_id, period, start_date, end_date):
        if not meter_id or not meter_id.isdigit() or len(meter_id) != 9:
            return [], {}

        params = {'meter_id': meter_id}
        if period != "custom":
            params["period"] = period
        else:
            params["start_date"] = start_date
            params["end_date"] = end_date

        response = requests.get(QUERY_ENDPOINT, params=params)
        result = response.json()
        if result.get('status') != 'success':
            return [], {}

        data = [{"date": k, "consumption": v} for k, v in result.get("daily_usage", {}).items()]
        df = pd.DataFrame(data)

        figure = {
            "data": [{"x": df["date"], "y": df["consumption"], "type": "bar", "name": "Daily Usage"}],
            "layout": {"title": "Electricity Usage Over Time"}
        }

        return data, figure

    return query_app
