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
        dcc.Input(
            id="meter_id", 
            type="text", 
            placeholder="Enter 9-digit Meter ID",
            style={"width": "100%", "height": "30px"}
        ),
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
        html.Button(
            "Get Usage", 
            id="get_usage", 
            n_clicks=0,
            style={"width": "10%", "padding": "10px", "fontSize": "16px"}
        ),
        html.Br(),
        html.Div(id="error_message", style={"color": "red", "textAlign": "center"}),
        dcc.Graph(id="usage_chart"),
        dash_table.DataTable(
            id="usage_table",
            columns=[
                {"name": "Time Range / Timestamp", "id": "date"},
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
        
        # 检查返回数据中是否包含 data 字段，且不为空
        if "data" not in result or not result["data"]:
            return [], {}, "No usage data available."

        data_field = result["data"]

        if period == "30m":
            # 30m 查询要求 data_field 为非空列表
            if not isinstance(data_field, list) or len(data_field) == 0:
                return [], {}, "No usage data available for the last 30 minutes."
            timestamp_value = data_field[0].get("time", "Unknown timestamp")
            try:
                timestamp_formatted = pd.to_datetime(timestamp_value).strftime("%Y-%m-%d %H:%M")
            except Exception:
                timestamp_formatted = timestamp_value
            inc = float(result.get("latest_increment", 0))
            inc_str = f"{inc:.2f}"
            table_data = [{"date": timestamp_formatted, "consumption": inc_str}]
            fig = {"data": [], "layout": {"title": "Latest Increment in Last 30 Minutes"}}
            return table_data, fig, ""

        elif period == "1d":
            # 1d 查询可能返回字典或列表
            if isinstance(data_field, dict):
                agg = data_field.get("aggregation", {})
                detail = data_field.get("detail", [])
            else:
                if len(data_field) == 0:
                    return [], {}, "No usage data available for 1 day period."
                agg = data_field[0]
                detail = data_field
            total = float(agg.get("consumption", 0))
            total_str = f"{total:.2f}"
            try:
                start_time_fmt = pd.to_datetime(agg.get("start_time", "")).strftime("%Y-%m-%d %H:%M") if agg.get("start_time") else "Unknown"
            except Exception:
                start_time_fmt = "Unknown"
            try:
                end_time_fmt = pd.to_datetime(agg.get("end_time", "")).strftime("%Y-%m-%d %H:%M") if agg.get("end_time") else "Unknown"
            except Exception:
                end_time_fmt = "Unknown"
            table_data = [{
                "date": f"{start_time_fmt} to {end_time_fmt}",
                "consumption": total_str
            }]
            df = pd.DataFrame(detail)
            if not df.empty and "time" in df.columns:
                try:
                    df["time"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    pass
            fig = {
                "data": [{"x": df["time"], "y": df["consumption"].astype(float), "type": "bar"}] if not df.empty else [],
                "layout": {"title": f"Past 24 Hour Usage (Total: {total_str} kWh)"}
            }
            return table_data, fig, ""

        elif period in ["1w", "1m"]:
            df = pd.DataFrame(data_field)
            if df.empty:
                return [], {}, "No usage data available"
            df["consumption"] = df["consumption"].apply(lambda x: f"{float(x):.2f}")
            fig = {
                "data": [{"x": df["date"], "y": df["consumption"].astype(float), "type": "bar"}],
                "layout": {"title": f"Daily Usage (Total: {float(result.get('total_usage', 0)):.2f} kWh)"}
            }
            table_data = [{"date": row["date"], "consumption": row["consumption"]} for _, row in df.iterrows()]
            return table_data, fig, ""

        elif period == "1y":
            df = pd.DataFrame(data_field)
            if df.empty:
                return [], {}, "No usage data available"
            df["consumption"] = df["consumption"].apply(lambda x: f"{float(x):.2f}")
            fig = {
                "data": [{"x": df["month"], "y": df["consumption"].astype(float), "type": "bar"}],
                "layout": {"title": f"Monthly Usage (Total: {float(result.get('total_usage', 0)):.2f} kWh)"}
            }
            table_data = [{"date": row["month"], "consumption": row["consumption"]} for _, row in df.iterrows()]
            return table_data, fig, ""

        else:
            return [], {}, "Unsupported data format."


    return query_app
