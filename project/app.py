from flask import Flask
from api import register_meter_api, register_user_api, register_daily_jobs, register_log_backup_api, register_query_api
from dash_app import create_registration_app, create_query_app

app = Flask(__name__)

# 注册 API
register_meter_api(app)
register_user_api(app)
register_daily_jobs(app)
register_log_backup_api(app)
register_query_api(app)  # 添加查询 API

# 绑定 Dash 页面
create_registration_app(app)
create_query_app(app)

if __name__ == '__main__':
    app.run(debug=True, port=8050)
