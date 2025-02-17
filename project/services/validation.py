import re
from datetime import datetime

def validate_meter_id(meter_id):
    """统一校验Meter ID格式"""
    return re.fullmatch(r"\d{9}", meter_id) is not None

def validate_timestamp(ts_str):
    """校验时间戳格式"""
    try:
        datetime.fromisoformat(ts_str)
        return True
    except ValueError:
        return False
