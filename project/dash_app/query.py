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
        html.Br(),html.Br(),

        html.Label("Select Time Period:"),
        dcc.Dropdown(
            id="period",
            options=[
                {"label":"Last 30 Minutes","value":"30m"},
                {"label":"Last 1 Day","value":"1d"},
                {"label":"Last 1 Week","value":"1w"},
                {"label":"Last 1 Month","value":"1m"},
                {"label":"This Year","value":"1y"}
            ],
            value="1d",
            style={"width":"100%"}
        ),
        html.Br(),
        html.Button("Get Usage", id="get_usage", n_clicks=0,
                    style={"width":"10%","padding":"10px","fontSize":"16px"}),
        html.Br(),

        html.Div(id="error_message", style={"color":"red","textAlign":"center"}),

        dcc.Graph(id="usage_chart"),
        dash_table.DataTable(
            id="usage_table",
            columns=[
                {"name":"Date","id":"date"},
                {"name":"Consumption (kWh)","id":"consumption"}
            ],
            style_table={"overflowX":"auto"}
        )
    ])

    @query_app.callback(
        [Output("usage_table","data"),
         Output("usage_chart","figure"),
         Output("error_message","children")],
        [Input("get_usage","n_clicks")],
        [State("meter_id","value"), State("period","value")]
    )
    def update_usage(n_clicks, meter_id, period):
        if not meter_id or not meter_id.isdigit() or len(meter_id)!=9:
            return [], {}, "Invalid Meter ID(9-digit)!"

        try:
            params = {"meter_id": meter_id, "period": period}
            resp = requests.get(QUERY_ENDPOINT, params=params)
            if resp.status_code != 200:
                return [], {}, f"API error: {resp.status_code}"

            result = resp.json()
            if result.get("status")!="success":
                return [], {}, f"Error: {result.get('message')}"

            # 30m
            if "increment_last_30m" in result:
                inc = result["increment_last_30m"]
                dt_data = [{"date":"Last 30 min","consumption":inc}]
                fig = {
                    "data":[{"x":["Last 30 min"],"y":[inc],"type":"bar"}],
                    "layout":{"title":"Usage in last 30 minutes"}
                }
                return dt_data, fig, ""

            if isinstance(result.get('data'),str):
                return [], {}, result['data']

            daily_usage = result.get("daily_usage",{})
            if not daily_usage:
                return [], {}, "No daily usage data found."

            total_usage = result.get("total_usage",0)
            data_list = [{"date":d,"consumption":v} for d,v in daily_usage.items()]

            df = pd.DataFrame(data_list)
            fig = {
                "data":[{"x":df["date"],"y":df["consumption"],"type":"bar","name":"Daily Usage"}],
                "layout":{"title":f"Electricity Usage (Total: {total_usage:.2f} kWh)"}
            }
            return data_list, fig, ""
        except Exception as e:
            return [], {}, f"Exception: {str(e)}"

    return query_app
