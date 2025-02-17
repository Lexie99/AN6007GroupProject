# dash/dash_query.py

import os
import dash
from dash import dcc, html, Input, Output, State, dash_table
import requests
import pandas as pd

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")
QUERY_ENDPOINT = f"{API_BASE_URL}/api/user/query"

def create_query_app(flask_server):
    """Create the front-end app for meter usage queries."""
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
                {"name": "Timestamp", "id": "date"},
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
        """Update the meter usage data."""
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

        # Process returned data.
        if "data" in result:
            data_list = result["data"]
            if not data_list:
                return [], {}, "No usage data available"
            if period == "30m":
                # For a 30-minute query, use the timestamp from the latest record.
                inc = result.get("latest_increment", 0)
                # Retrieve the timestamp from the returned data.
                timestamp_value = data_list[0].get("time", "Unknown timestamp")
                table_data = [{"date": timestamp_value, "consumption": inc}]
                fig = {
                    "data": [{"x": [timestamp_value], "y": [inc], "type": "bar"}],
                    "layout": {"title": "Latest Increment in Last 30 Minutes"}
                }
                return table_data, fig, ""
            else:
                df = pd.DataFrame(data_list)
                if df.empty:
                    return [], {}, "No usage data available"
                if period == "1d":
                    fig = {
                        "data": [{"x": df["time"], "y": df["consumption"], "type": "bar"}],
                        "layout": {"title": f"1-Day Usage (Total: {result.get('total_usage', 0):.2f} kWh)"}
                    }
                    table_data = [{"date": row["time"], "consumption": row["consumption"]} for _, row in df.iterrows()]
                    return table_data, fig, ""
                elif period in ["1w", "1m"]:
                    fig = {
                        "data": [{"x": df["date"], "y": df["consumption"], "type": "bar"}],
                        "layout": {"title": f"Daily Usage (Total: {result.get('total_usage', 0):.2f} kWh)"}
                    }
                    table_data = [{"date": row["date"], "consumption": row["consumption"]} for _, row in df.iterrows()]
                    return table_data, fig, ""
                elif period == "1y":
                    fig = {
                        "data": [{"x": df["month"], "y": df["consumption"], "type": "bar"}],
                        "layout": {"title": f"Monthly Usage (Total: {result.get('total_usage', 0):.2f} kWh)"}
                    }
                    table_data = [{"date": row["month"], "consumption": row["consumption"]} for _, row in df.iterrows()]
                    return table_data, fig, ""
                else:
                    return [], {}, "Unsupported data format."
        else:
            return [], {}, "Unsupported data format."

    return query_app
