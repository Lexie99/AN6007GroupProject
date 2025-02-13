from flask import Flask
from project.api.api import register_api
from project.dash_app.dash_app import create_registration_app, create_query_app

# 创建 Flask 应用实例
app = Flask(__name__)

# 直接调用 api.py 中的函数，将 API 路由注册到 Flask 应用中
register_api(app)

# 创建并挂载 Dash 子应用（注册页面与查询页面）
registration_app = create_registration_app(app)
query_app = create_query_app(app)

if __name__ == '__main__':
    app.run(debug=True, port=8050)
    
#查看运行结果看  http://127.0.0.1:8050/query/  和   http://127.0.0.1:8050/register/
