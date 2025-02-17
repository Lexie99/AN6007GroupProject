from flask import Flask,request,jsonify
from config.app_config import AppConfig
from services.redis_service import RedisService
from services.background_worker import start_background_worker
import os

# 导入所有 create_xxx_blueprint 函数
from api.user_register import create_user_register_blueprint
from api.meter_reading import create_meter_reading_blueprint
from api.user_query import create_user_query_blueprint
from api.daily_jobs import create_daily_jobs_blueprint
from api.logs_backup import create_logs_backup_blueprint

# Dash front-end
from dash_app.query import create_query_app
from dash_app.register import create_registration_app

config_path = os.getenv("CONFIG_PATH", "project/config/config.json")


def create_app():
    app = Flask(__name__)

    # 初始化配置与 RedisService
    app_config = AppConfig(config_path=config_path)
    redis_service = RedisService()
    redis_service.log_event("system", "Application initialized")  # 启动日志

    # 注册API路由
    app.register_blueprint(create_user_register_blueprint(app_config, redis_service))
    app.register_blueprint(create_meter_reading_blueprint(redis_service))
    app.register_blueprint(create_user_query_blueprint(redis_service))
    app.register_blueprint(create_daily_jobs_blueprint(redis_service))
    app.register_blueprint(create_logs_backup_blueprint(redis_service))
    
    # 启动后台worker (如需测试队列式读数, 否则可注释)
    start_background_worker(redis_service)

    # 初始化Dash
    dash_query = create_query_app(app)
    dash_register = create_registration_app(app)

    @app.route('/')
    def index():
        return "Main Index => /query/ for usage query, /register/ for user register."
    
    return app

if __name__=="__main__":
    application = create_app()
    application.run(port=8050,debug=True)
