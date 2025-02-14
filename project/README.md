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

7. **后台 Worker**(可选)  
   - 在单独的 `background_worker.py` 中，通过线程处理 Redis 列表，将数据批量写入电表历史。

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
│   └── background_worker.py  # 后台 Worker (函数式)
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
详见requirements.txt:
    - dash==2.18.2
    - Flask==3.0.3
    - pandas==2.2.2
    - redis==5.2.1
    - Requests==2.32.3


---

## 运行步骤

1. **启动 Redis**  
   - 本地或远程均可，确认 `REDIS_HOST`, `REDIS_PORT` 环境变量，如未设置则默认 `localhost:6379`。

2. **安装依赖**  
   ```bash
   pip install -r requirements.txt
   ```

3. **配置**  
   - 打开 `config/config.json`，确认里面的 `region_area_mapping`、`dwelling_data` 是否符合需求；  
   - 如需修改 Redis 连接，也可设置环境变量 `REDIS_HOST`、`REDIS_PORT`。  

4. **运行 Flask + Dash**  
   ```bash
   python app.py
   ```
   - 服务默认启动在 `http://127.0.0.1:8050`，若 `host=0.0.0.0` 则外部也可访问。

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

### 1. `AppConfig` (加载配置)

- 位于 `config/app_config.py`，**面向对象**封装。  
- 通过 `config.json` 读取**Region->Area** 映射、**DwellingType** 集合，用于**校验**用户注册时提交的 region/area/dwelling_type。  
- 在运行时通过 `AppConfig()` 实例化，供 Flask 路由/ Dash前端使用。

### 2. `RedisService` (Redis 操作封装)

- 位于 `services/redis_service.py`。  
- 统一管理 Redis 连接，封装常见操作：`is_meter_registered`, `register_meter`, `add_meter_reading`, `move_pending_to_history` 等。  
- 避免在各处重复写 `redis.Redis(...)` 并做相似命令，提高可维护性。

### 3. `User` (电表用户信息模型)

- 位于 `models/user.py`。  
- 代表一个**电表注册信息**：包含 meter_id、region、area、dwelling_type 以及注册时间戳。  
- 提供 `to_dict()` 方法，方便存入 Redis 的 `hset`。

### 4. 后台 Worker (`background_worker.py`)

- 位于 `services/background_worker.py`，**函数式**写法并未封装成类；在 `app.py` 启动时可调用 `start_background_worker()` 开启一个**守护线程**。  
- 默认从 Redis 列表 `meter:readings_queue` 中取批量数据，并写入 `meter:{id}:history`。  
- 若你想模拟“队列式写法”，在前端或 API 里把电表读数写入 `meter:readings_queue`，然后由 Worker 后台批量处理。

### 5. API 模块 (Flask Blueprints)

- **`user_register_api.py`**:  
  - `/api/user/register` 接口，用 `AppConfig` 校验 region/area/dwelling_type，用 `RedisService` 写 `all_users` 与 `user_data:{meter_id}`。  
- **`meter_reading_api.py`**:  
  - `/meter/reading` 接口，上报电表读数写 `meter:{id}:history`。  
- **`user_query_api.py`**:  
  - `/api/user/query` 接口，支持 30分钟增量 / 固定时间区间查询。  
- **`daily_jobs_api.py`**:  
  - `/stopserver` 接口，进入维护模式，执行**昨日数据备份**与**pending数据处理**。  
- **`logs_backup_api.py`**:  
  - `/get_logs`, `/get_backup` 等接口，查看最近日志或备份结果。

### 6. Dash 前端

- **`dash_register.py`**:  
  - 地址：`/register/`  
  - 提供“电表注册”表单。可**直接**导入 `AppConfig` 生成 Region/Area/DwellingType 下拉选项，或调用后端 API 获取。  
  - 提交后端 `/api/user/register`。  
- **`dash_query.py`**:  
  - 地址：`/query/`  
  - 提供“电表查询”表单。输入 meter_id、选择时间范围后，从后端 `/api/user/query` 获取数据并在前端图表显示。

---

## 测试脚本

- `test.py`  
  - 集成测试多个接口：  
    1. **清理** Redis 旧数据；  
    2. **注册**电表 ID；  
    3. **提交**读数；  
    4. **查询** 30m / 1d；  
    5. **触发** `/stopserver` 进入维护模式；  
    6. **查看** 备份 `/get_backup` 与日志 `/get_logs` 等。  
  - 运行： `python test.py`

观察输出即可验证项目主要功能是否正常。

---


## 结语

本系统通过**面向对象**的设计，将 **`AppConfig`** (配置加载)、**`RedisService`** (数据库操作封装)、**`User`** (电表用户模型) 等独立模块化；并配合 **Flask** (API 路由) + **Dash** (前端界面) + **Redis** (数据存储) 构建了一个相对完善的电表管理方案