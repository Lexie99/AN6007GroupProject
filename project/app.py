from flask import Flask
from api import daily_jobs_api, log_backup_api, meter_reading_api,user_query_api,user_register_api
from dash_app import create_registration_app, create_query_app


app = Flask(__name__)

# 注册 API
daily_jobs_api(app)
log_backup_api(app)
meter_reading_api(app)
user_query_api(app)
user_register_api(app)

# 绑定 Dash 页面
create_registration_app(app)
create_query_app(app)

if __name__ == '__main__':
    app.run(debug=True, port=8050)



