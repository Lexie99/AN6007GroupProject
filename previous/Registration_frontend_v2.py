# -*- coding: utf-8 -*-
"""
Created on Thu Feb  6 19:09:46 2025

@author: Sherlyds
"""

import project.dash_app.register as register
from project.dash_app.register import dcc, html
from dash.dependencies import Input, Output, State
import pandas as pd
import json
from datetime import datetime
import re
from flask import Flask, request, jsonify




# 读取数据
area_data = pd.DataFrame({
    "AreaID": [
        1001, 1002, 1003, 1004, 1005, 1006, 1007, 1008, 1009, 1010,
        1011, 1012, 1013, 1014, 1015, 1016, 1017, 1018, 1019, 1020,
        1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028, 1029, 1030,
        1031, 1032, 1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040,
        1041, 1042, 1043, 1044, 1045, 1046, 1047
    ],
    "Area": [
        "Bishan", "Sembawang", "Yishun", "Outram", "Kallang", "North Region", "Bukit Batok", "Sengkang", "Clementi", "Woodlands",
        "Choa Chu Kang", "Serangoon", "Central Region", "Tampines", "North East Region", "Ang Mo Kio", "Toa Payoh", "Bedok", "East Region", "Jurong East",
        "Hougang", "Bukit Merah", "West Region", "Queenstown", "Geylang", "Novena", "Jurong West", "Marine Parade", "Rochor", "Pioneer",
        "Pasir Ris", "Paya Lebar", "Mandai", "Downtown", "Seletar", "Sungei Kadut", "Bukit Panjang", "Museum", "Singapore River", "Bukit Timah",
        "Changi", "River Valley", "Tanglin", "Punggol", "Orchard", "Southern Islands", "Newton"
    ],
    "Region": [
        "Central Region", "North Region", "North Region", "Central Region", "Central Region", "North Region", "West Region", "North East Region", "West Region", "North Region",
        "West Region", "North East Region", "Central Region", "East Region", "North East Region", "North East Region", "Central Region", "East Region", "East Region", "West Region",
        "North East Region", "Central Region", "West Region", "Central Region", "Central Region", "Central Region", "West Region", "Central Region", "Central Region", "West Region",
        "East Region", "East Region", "North Region", "Central Region", "North East Region", "North Region", "West Region", "Central Region", "Central Region", "Central Region",
        "East Region", "Central Region", "Central Region", "North East Region", "Central Region", "Central Region", "Central Region"
    ]
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


# 读取存储的用户数据
with open("store_user_data.json", "w") as json_file:
    json.dump({}, json_file, indent=4)  # 写入空字典
try:
    with open("store_user_data.json", "r") as json_file:
        store_user_data = json.load(json_file)
except (FileNotFoundError, json.JSONDecodeError):
    store_user_data = {}

# 确定 current_id（从最大 ID +1 开始）
current_id = max(map(int, store_user_data.keys()), default=0) + 1 if store_user_data else 0

# 构建 Region 和 Area 的映射关系
region_area_mapping = area_data.groupby('Region')['Area'].apply(list).to_dict()



# 定义布局
def register(flask_app):
    app = register.Dash(server = flask_app, name = 'register', url_base_pathname='/register/')
    app.layout = html.Div([
        html.Div([
            html.H2("New User Registration", style={'textAlign': 'center'}),
            html.Label("MeterID:"),
            dcc.Input(id='meter-id', type='text', placeholder='Enter 9 digits MeterID', style={'width': '100%'}),
            html.Br(),
            html.Label("Region:"),
            dcc.Dropdown(
                id='region',
                options=[{'label': region, 'value': region} for region in region_area_mapping.keys()],
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
                options=[{'label': dt, 'value': dt} for dt in dwelling_data['DwellingType']],
                placeholder='Select a Dwelling Type',
                style={'width': '100%'}
            ),
            html.Br(),
            html.Button("Submit", id='submit-btn', n_clicks=0, style={'width': '100%', 'padding': '10px', 'fontSize': '16px'}),
            html.Br(),
            html.Div(id='output', style={'textAlign': 'center', 'marginTop': '20px'})
        ], style={'maxWidth': '500px', 'margin': 'auto', 'padding': '20px', 'border': '1px solid #ddd',
                  'borderRadius': '10px', 'boxShadow': '2px 2px 10px rgba(0,0,0,0.1)'})
    ])
    # 根据 Region 更新 Area 选项
    @app.callback(
        Output('area', 'options'),
        Output('area', 'disabled'),
        Input('region', 'value')
    )
    def update_area_options(selected_region):
        if selected_region:
            return ([{'label': area, 'value': area} for area in region_area_mapping[selected_region]], False)
        return ([], True)


    # 处理提交按钮
    @app.callback(
        Output('output', 'children'),
        Input('submit-btn', 'n_clicks'),
        State('meter-id', 'value'),
        State('region', 'value'),
        State('area', 'value'),
        State('dwelling-type', 'value')
    )
                  

    def update_output(n_clicks, meter_id, region, area, dwelling_type):
        global current_id
        if n_clicks > 0:
            if not meter_id or not region or not area or not dwelling_type:
                return html.P("Please fill in all fields.", style={'color': 'red'})
            
            if not meter_id or not re.fullmatch(r"\d{9}", meter_id): 
                return html.P("Invalid MeterID format!", style={'color': 'red'}), 
    
            # 检查 MeterID 是否已经存在
            if any(user['MeterID'] == meter_id for user in store_user_data.values()):
                return html.P("This MeterID is already registered. Please use a different one.", style={'color': 'red'})
            #添加时间戳    
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # 存储数据
            user_data = {
                'MeterID': meter_id,
                'Region': region,
                'Area': area,
                'DwellingType': dwelling_type,
                'TimeStamp':timestamp
            }
            current_id += 1 
            store_user_data[current_id] = user_data
             # 递增 ID
    
            # 保存数据到 JSON 文件
            with open("store_user_data.json", "w") as json_file:
                json.dump(store_user_data, json_file, indent=4)
    
            return html.P("Submission successful!", style={'color': 'green'})
    
        return ""
    
    return app


