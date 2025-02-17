# AN6007GroupProject
# README: 电表管理系统

## 目录
1. [项目简介](#项目简介)  
2. [主要功能](#主要功能)  
3. [项目结构](#项目结构)  
4. [环境与依赖](#环境与依赖)  
5. [运行步骤](#运行步骤)  
6. [关键模块说明](#关键模块说明)  
   - [1. `AppConfig` (加载配置)](#appconfig-加载配置)  
   - [2. `RedisService` (Redis 操作封装)](#redisservice-redis-操作封装)  
   - [3. `User` (电表用户信息模型)](#user-电表用户信息模型)  
   - [4. 后台 Worker (background_worker.py)](#后台-worker-background_workerpy)  
   - [5. API 模块 (Flask Blueprints)](#api-模块-flask-blueprints)  
   - [6. Dash 前端](#dash-前端)  
7. [测试脚本](#测试脚本)  
8. [注意事项](#注意事项)

---

## 项目简介

本项目是一个**电表管理与查询系统**，使用 Flask + Dash + Redis 构建。核心目标：  
- 提供**用户（电表）注册**、**电表读数上报**、**用电量查询**等基础功能；  
- 支持**维护模式**（停止正常写入，转为 pending；维护结束后再处理）以及**每日备份**；  
- 通过 **Dash** 提供**可视化前端**供用户进行注册和查询操作。

通过**面向对象**的方式封装了以下几个关键组件：  
- `AppConfig`：加载项目配置（包含 Region->Area 对应关系与 DwellingTypes 列表）。  
- `RedisService`：统一管理 Redis 连接与常用操作。  
- `User`：表示电表注册信息模型。

此外还提供一个**后台 Worker**脚本，用于定时或持续处理某些异步队列里的数据。

---

## 主要功能

1. **用户注册**  
   - 接口：`POST /api/user/register`  
   - 提交 `meter_id`, `region`, `area`, `dwelling_type` 等信息后，写入 Redis `all_users` 以及 `user_data:{meter_id}` 结构。  

2. **电表读数上报**  
   - 接口：`POST /meter/reading`  
   - 提交 `meter_id`, `timestamp`, `reading`，写入 Redis SortedSet `meter:{meter_id}:history`。  

3. **用电量查询**  
   - 接口：`GET /api/user/query`  
   - 支持查询**30 分钟增量**或**固定时间段**（1d/1w/1m/1y），返回总用电量、以及按日统计结果。  

4. **维护模式**  
   - 接口：`GET /stopserver`  
   - 模拟服务器停机若干秒，并执行**昨日数据备份** + **处理 pending** 队列。  

5. **日志 / 备份**  
   - 接口：`GET /get_logs` (可选)  
   - 接口：`GET /get_backup` (查询昨日或指定日期的备份数据)。  

6. **Dash 前端**  
   - `/register/`：提供用户注册的可视化表单；  
   - `/query/`：提供查询电表用电量的可视化页面。

7. **后台 Worker**  
   - 在单独的 `background_worker.py` 中，通过线程处理 Redis 列表，将数据批量写入电表历史记录。

---

## 项目结构

```
my_project/
├── config/
│   ├── app_config.py         # AppConfig 类 (加载 config.json)
│   └── config.json           # 存放 Region->Area, DwellingType 等配置
├── models/
│   └── user.py               # User 类 (电表用户信息)
├── services/
│   ├── redis_service.py      # RedisService 类 (管理 Redis 连接与操作)
│   └── background_worker.py  # 后台 Worker (函数式实现)
│   ├── state.py      # MaintenanceState类（管理维护状态）
│   └── validation.py  # 重复的校验内容 (函数式实现)
├── api/
│   ├── user_register_api.py  # /api/user/register
│   ├── meter_reading_api.py  # /meter/reading
│   ├── user_query_api.py     # /api/user/query
│   ├── daily_jobs_api.py     # /stopserver, 维护模式、备份等
│   └── logs_backup_api.py    # /get_logs, /get_backup
├── dash/
│   ├── dash_register.py      # /register/ (Dash 前端)
│   └── dash_query.py         # /query/ (Dash 前端)
├── test.py                   # 测试脚本 (自动化测试多个接口)
└── app.py                    # Flask 启动入口
```

---

## 环境与依赖

- **Python** 3.7+   
- **Redis** 数据库 (服务端必须启动)  
- 主要依赖库：  
  - `Flask` (Web 框架)  
  - `Dash` (前端可视化)  
  - `requests` (测试脚本中使用)  
  - `redis` (Python Redis 客户端)  

详见 requirements.txt：
```
dash==2.18.2
Flask==3.0.3
pandas==2.2.2
redis==5.2.1
Requests==2.32.3
```

---

## 运行步骤

1. **启动 Redis**  
   - 本地或远程均可，确认 `REDIS_HOST`, `REDIS_PORT` 环境变量，如未设置则默认 `localhost:6379`。

2. **安装依赖**  
   ```bash
   pip install -r requirements.txt
   ```

3. **配置**  
   - 打开 `config/config.json`，确认里面的 `region_area_mapping` 与 `dwelling_data` 是否符合需求；  
   - 如需修改 Redis 连接，也可设置环境变量 `REDIS_HOST`、`REDIS_PORT`。

4. **运行 Flask + Dash**  
   ```bash
   python app.py
   ```  
   - 服务默认启动在 `http://127.0.0.1:8050`。

5. **访问**  
   - **Dash 注册页面**：`http://127.0.0.1:8050/register/`  
   - **Dash 查询页面**：`http://127.0.0.1:8050/query/`  
   - **API**：  
     - `/api/user/register`  
     - `/meter/reading`  
     - `/api/user/query`  
     - `/stopserver` (维护模式)  
     - `/get_backup`, `/get_logs` 等。

6. **测试脚本**  
   ```bash
   python test.py
   ```  
   - 脚本会自动清理 Redis 测试数据、注册电表、发送读数、查询用电量、尝试维护模式等，观察输出验证功能。

---

## 关键模块说明

1. **AppConfig (加载配置)**  
   位于 `config/app_config.py`，通过 `config.json` 读取**Region->Area** 映射和**DwellingType** 数据。供 Flask 路由和 Dash 前端使用，确保用户提交数据时校验选项正确。

2. **RedisService (Redis 操作封装)**  
   位于 `services/redis_service.py`。统一管理 Redis 连接，封装常见操作：`is_meter_registered`、`register_meter`、`add_meter_reading`、`move_pending_to_history` 等。详细日志记录及错误处理使系统更易于调试。

3. **User (电表用户信息模型)**  
   位于 `models/user.py`。表示电表注册信息，包含 `meter_id`、`region`、`area`、`dwelling_type` 及注册时间戳。提供 `to_dict()` 方法，便于数据存储。

4. **后台 Worker (background_worker.py)**  
   位于 `services/background_worker.py`，通过守护线程从 Redis 队列中批量处理数据，写入电表历史记录。支持维护模式下的 pending 数据处理与每日备份。

5. **API 模块 (Flask Blueprints)**  
   - `user_register_api.py`: `/api/user/register` 接口，负责用户注册及数据存储。  
   - `meter_reading_api.py`: `/meter/reading` 接口，上报电表读数；已更新验证逻辑，确保时间戳格式正确。  
   - `user_query_api.py`: `/api/user/query` 接口，支持查询 30 分钟增量及固定区间用电量。  
   - `daily_jobs_api.py`: `/stopserver` 接口，用于触发维护模式、执行数据备份与 pending 数据处理。  
   - `logs_backup_api.py`: `/get_logs`、`/get_backup` 接口，便于查看日志和备份数据。

6. **Dash 前端**  
   - `dash_register.py`: 地址：`/register/`，提供用户注册表单，直接与后端 `/api/user/register` 交互。  
   - `dash_query.py`: 地址：`/query/`，提供用电量查询页面，展示查询结果图表。

---

## 测试脚本

`test.py` 集成测试所有主要接口，包括数据清理、用户注册、读数上报、查询、维护模式触发以及备份与日志查询。运行方式：
```bash
python test.py
```
请关注测试输出，验证各项功能是否正常。

---

## 注意事项

- **Python 版本**：请确保使用 Python 3.7 以上版本，避免 `datetime.fromisoformat` 方法不可用的问题。  
- **Redis 数据库**：在测试或生产环境中执行涉及数据清理或 FLUSH 操作时，请务必小心，确保不会误删重要数据。  
- **日志记录**：系统使用结构化日志记录各类操作，便于后续调试。建议在生产环境中配置合适的日志级别和存储策略。

---

## 结语

本系统采用面向对象设计，将 `AppConfig` (配置加载)、`RedisService` (数据库操作封装)、`User` (电表用户模型) 等模块化设计，并结合 Flask (API 路由) + Dash (前端界面) + Redis (数据存储) 构建了一个功能完善的电表管理方案。通过详细的日志记录和后台 Worker 的支持，系统具有较高的可维护性和扩展性。祝你使用愉快!
```