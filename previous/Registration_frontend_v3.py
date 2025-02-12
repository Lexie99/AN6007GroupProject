# -*- coding: utf-8 -*-
"""
Created on Tue Feb 11 15:26:20 2025

@author: ASUS
"""
# Registration_frontend_v2.py
import dash_app
from dash_app import dcc, html, Input, Output, State
import pandas as pd
import json
import re
from datetime import datetime

# 模拟区域数据与住宅类型数据
area_data = pd.DataFrame({
    "AreaID": [1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010,
               1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020,
               1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028, 1029, 1030,
               1031, 1032, 1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040,
               1041, 1042, 1043, 1044, 1045, 1046, 1047],
    "Area": ["Bishan", "Sembawang", "Yishun", "Outram", "Kallang", "North Region", "Bukit Batok", "Sengkang", "Clementi", "Woodlands",
             "Choa Chu Kang", "Serangoon", "Central Region", "Tampines", "North East Region", "Ang Mo Kio", "Toa Payoh", "Bedok", "East Region", "Jurong East",
             "Hougang", "Bukit Merah", "West Region", "Queenstown", "Geylang", "Novena", "Jurong West", "Marine Parade", "Rochor", "Pioneer",
             "Pasir Ris", "Paya Lebar", "Mandai", "Downtown", "Seletar", "Sungei Kadut", "Bukit Panjang", "Museum", "Singapore River", "Bukit Timah",
             "Changi", "River Valley", "Tanglin", "Punggol", "Orchard", "Southern Islands", "Newton"],
    "Region": ["Central Region", "North Region", "North Region", "Central Region", "Central Region", "North Region", "West Region", "North East Region", "West Region", "North Region",
               "West Region", "North East Region", "Central Region", "East Region", "North East Region", "North East Region", "Central Region", "East Region", "East Region", "West Region",
               "North East Region", "Central Region", "West Region", "Central Region", "Central Region", "Central Region", "West Region", "Central Region", "Central Region", "West Region",
               "East Region", "East Region", "North Region", "Central Region", "North East Region", "North Region", "West Region", "Central Region", "Central Region", "Central Region",
               "East Region", "Central Region", "Central Region", "North East Region", "Central Region", "Central Region", "Central Region"]
})

dwelling_data = pd.DataFrame({
    "TypeID": [1, 2, 3, 4, 5, 6],
    "DwellingType": [
        "1-room / 2-room",
        "Private Apartments and Condominiums",
        "Landed Properties",
        "5-room and Executive",
        "3-room",
        "4-room"
    ]
})

# 载入或初始化存储的用户数据
try:
    with open("store_user_data.json", "r") as f:
        store_user_data = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    store_user_data = {}
    with open("store_user_data.json", "w") as f:
        json.dump({}, f, indent=4)

current_id = max(map(int, store_user_data.keys()), default=0) + 1 if store_user_data else 0

region_area_mapping = area_data.groupby('Region')['Area'].apply(list).to_dict()

def create_registration_app(server):
    reg_app = dash_app.Dash(__name__, server=server, url_base_pathname='/register/')
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
                options=[{'label': dt_val, 'value': dt_val} for dt_val in dwelling_data['DwellingType']],
                placeholder='Select a Dwelling Type',
                style={'width': '100%'}
            ),
            html.Br(),
            html.Button("Submit", id='submit-btn', n_clicks=0, style={'width': '100%', 'padding': '10px', 'fontSize': '16px'}),
            html.Br(),
            html.Div(id='output', style={'textAlign': 'center', 'marginTop': '20px'})
        ], style={'maxWidth': '500px', 'margin': 'auto', 'padding': '20px',
                  'border': '1px solid #ddd', 'borderRadius': '10px',
                  'boxShadow': '2px 2px 10px rgba(0,0,0,0.1)'})
    ])

    @reg_app.callback(
        [Output('area', 'options'), Output('area', 'disabled')],
        [Input('region', 'value')]
    )
    def update_area_options(selected_region):
        if selected_region:
            return ([{'label': area, 'value': area} for area in region_area_mapping[selected_region]], False)
        return ([], True)

    @reg_app.callback(
        Output('output', 'children'),
        [Input('submit-btn', 'n_clicks')],
        [State('meter-id', 'value'),
         State('region', 'value'),
         State('area', 'value'),
         State('dwelling-type', 'value')]
    )
    def update_output(n_clicks, meter_id, region, area, dwelling_type):
        global current_id, store_user_data
        if n_clicks > 0:
            if not meter_id or not region or not area or not dwelling_type:
                return html.P("Please fill in all fields.", style={'color': 'red'})
            if not re.fullmatch(r"\d{9}", meter_id):
                return html.P("Invalid MeterID format!", style={'color': 'red'})
            if any(user['MeterID'] == meter_id for user in store_user_data.values()):
                return html.P("This MeterID is already registered.", style={'color': 'red'})
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            user_data = {
                'MeterID': meter_id,
                'Region': region,
                'Area': area,
                'DwellingType': dwelling_type,
                'TimeStamp': timestamp
            }
            current_id += 1
            store_user_data[str(current_id)] = user_data
            with open("store_user_data.json", "w") as f:
                json.dump(store_user_data, f, indent=4)
            return html.P("Submission successful!", style={'color': 'green'})
        return ""

    return reg_app

if __name__ == '__main__':
    from flask import Flask
    server = Flask(__name__)
    app = create_registration_app(server)
    app.run_server(debug=True, port=8050)
