import os
import time
import random
import requests
import redis
import argparse
from datetime import datetime, timedelta

BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8050")

REGISTER_URL    = f"{BASE_URL}/api/user/register"
METER_READ_URL  = f"{BASE_URL}/meter/reading"
USER_QUERY_URL  = f"{BASE_URL}/api/user/query"
STOPSERVER_URL  = f"{BASE_URL}/stopserver"
BACKUP_URL      = f"{BASE_URL}/get_backup"
LOGS_URL        = f"{BASE_URL}/get_logs"
BILLING_URL     = f"{BASE_URL}/api/billing"  # 新增：月度账单API

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

TEST_METER_IDS = [
    "100000001", "100000002", "100000003", "100000004", "100000005",
    "100000006", "100000007", "100000008", "100000009", "100000010",
    "100000011", "100000012", "100000013", "100000014", "100000015",
    "100000016", "100000017", "100000018", "100000019", "100000020"
]
READ_TIMES = 3
MAINTENANCE_WAIT = 60  # Maintenance mode wait time in seconds

# Global variable to store the last reading for each meter
last_readings = {}

def clear_test_data():
    """
    Delete Redis keys for all_users, meter:* and user_data:*
    """
    if r.exists("all_users"):
        r.delete("all_users")
    meter_keys = list(r.scan_iter("meter:*"))
    for mk in meter_keys:
        r.delete(mk)
    user_keys = list(r.scan_iter("user_data:*"))
    for uk in user_keys:
        r.delete(uk)
    # r.flushall()  # Use with caution, this deletes all data

def register_meter(meter_id):
    payload = {
        "meter_id": meter_id,
        "region": "Central Region",
        "area": "Bishan",
        "dwelling_type": "3-room"
    }
    resp = requests.post(REGISTER_URL, json=payload)
    return resp.json()

def send_meter_reading(meter_id, timestamp=None):
    """
    Send a meter reading. Each reading increases randomly based on the previous reading.
    Parameters:
      - meter_id: Meter identifier
      - timestamp: Optional, specify the reporting time (accepts a datetime object or an ISO format string);
                   if not provided, current time is used.
    """
    # Initialize or update the reading
    if meter_id not in last_readings:
        last_readings[meter_id] = round(random.uniform(100, 200), 2)
    else:
        # Increase from the previous reading by a random increment (between 0 and 10)
        increment = round(random.uniform(0, 10), 2)
        last_readings[meter_id] = round(last_readings[meter_id] + increment, 2)
    reading = last_readings[meter_id]

    # Set the timestamp; support custom time
    if timestamp is None:
        ts = datetime.now().isoformat()
    else:
        ts = timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp

    payload = {
        "meter_id": meter_id,
        "timestamp": ts,
        "reading": reading
    }
    resp = requests.post(METER_READ_URL, json=payload)
    return resp.json()

def send_multiple_meter_readings(meter_id, start_time, count=5, interval_seconds=600):
    """
    Batch send meter readings for the specified meter, starting from start_time,
    with an interval of interval_seconds between each record.
    If start_time is a string, it will be converted to a datetime object.
    Returns a list of tuples (timestamp, API response).
    """
    from datetime import datetime, timedelta
    
    # If start_time is a string, convert it
    if isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time)
        except Exception as e:
            raise ValueError(f"Invalid start_time format: {start_time}. Error: {e}")

    responses = []
    current_time = start_time
    for i in range(count):
        resp = send_meter_reading(meter_id, timestamp=current_time)
        responses.append((current_time.isoformat(), resp))
        current_time += timedelta(seconds=interval_seconds)
        time.sleep(0.1)  # Simulate a short delay to avoid sending too quickly
    return responses

def query_meter(meter_id, period):
    params = {"meter_id": meter_id, "period": period}
    resp = requests.get(USER_QUERY_URL, params=params)
    return resp.json()

def stop_server():
    resp = requests.get(STOPSERVER_URL)
    return resp.json()

def get_backup(date=None):
    """
    Retrieve backup data for the specified date.
    Parameter:
      - date: Optional, a date string in the format "YYYY-MM-DD". If not provided, the backend defaults (usually yesterday).
    """
    params = {}
    if date:
        params["date"] = date
    resp = requests.get(BACKUP_URL, params=params)
    return resp.json()

def get_logs(log_type="daily_jobs", limit=5, date=None):
    """
    Retrieve log data.
    Parameters:
      - log_type: Log type (default is "daily_jobs")
      - limit: Limit the number of log entries returned
      - date: Optional, a date string in the format "YYYY-MM-DD" (if the backend supports date filtering).
    """
    params = {"log_type": log_type, "limit": limit}
    if date:
        params["date"] = date
    resp = requests.get(LOGS_URL, params=params)
    return resp.json()

def get_billing(meter_id, month):
    """
    Test the monthly billing API.
    Parameters:
      - meter_id: 9-digit meter identifier.
      - month: Month string in the format "YYYY-MM" (e.g., "2025-02").
    """
    params = {"meter_id": meter_id, "month": month}
    resp = requests.get(BILLING_URL, params=params)
    return resp.json()

if __name__ == "__main__":
    print("===== Test Script Start =====")

    #print("[Test] Clearing old data...")
    #clear_test_data()

    print("[Test] Registering meter IDs...")
    for mid in TEST_METER_IDS:
        res = register_meter(mid)
        print(f"  register {mid} =>", res)

    print("[Test] Batch sending meter readings with multiple timestamps...")
    # Use a custom start time: starting from the custom start time, send one record per minute, for a total of 5 records.
    for mid in TEST_METER_IDS[:]:
        responses = send_multiple_meter_readings(mid, start_time="2025-02-16T11:30:00", count=5, interval_seconds=60)
        for ts, resp in responses:
            print(f"  meter {mid} @ {ts} =>", resp)
        time.sleep(0.5)

    print("[Test] Querying 30-minute and 1-day data")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        print(f"  {mid} 30m =>", r30)
        r1d = query_meter(mid, "1d")
        print(f"  {mid} 1d =>", r1d)

    print("[Test] Testing maintenance mode effect...")
    print("[Test] Calling stop_server to enter maintenance mode")
    ret_maint = stop_server()
    print("  stop_server =>", ret_maint)

    # During maintenance mode, try sending meter readings to verify if they are queued in the pending queue.
    print("[Test] Sending readings during maintenance mode...")
    for mid in TEST_METER_IDS[:3]:
        resp = send_meter_reading(mid)
        print(f"  meter {mid} =>", resp)
    # At the same time, query 30-minute data (pending data may not have been transferred to history yet)
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        print(f"  (Maintenance mode) {mid} 30m =>", r30)

    print(f"[Test] Waiting {MAINTENANCE_WAIT} seconds (maintenance mode duration)...")
    time.sleep(MAINTENANCE_WAIT + 5)  # Wait a few extra seconds to ensure maintenance mode ends

    print("[Test] Sending readings again after maintenance mode ends...")
    for mid in TEST_METER_IDS[:3]:
        resp = send_meter_reading(mid)
        print(f"  meter {mid} =>", resp)

    print("[Test] Querying 30-minute and 1-day data (after maintenance mode)")
    for mid in TEST_METER_IDS[:3]:
        r30 = query_meter(mid, "30m")
        print(f"  {mid} 30m =>", r30)
        r1d = query_meter(mid, "1d")
        print(f"  {mid} 1d =>", r1d)

    print("[Test] Viewing backup data for specified date:")
    print(get_backup(date="2025-02-16"))

    print("[Test] Viewing logs (daily_jobs):")
    print(get_logs("daily_jobs", 5))

    # 新增：测试月度账单 API
    print("[Test] Testing monthly billing API...")
    test_month = "2025-02"
    for mid in TEST_METER_IDS[:3]:
        billing_result = get_billing(mid, test_month)
        print(f"  billing for {mid} in month {test_month} =>", billing_result)

    print("===== Test Script Finished =====")
