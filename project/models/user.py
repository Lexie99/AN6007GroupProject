# models/user.py

from datetime import datetime

class User:
    """
    用于封装“用户电表注册信息”的数据结构
    """
    def __init__(self, meter_id, region, area, dwelling_type):
        self.meter_id = meter_id
        self.region = region
        self.area = area
        self.dwelling_type = dwelling_type
        self.timestamp = datetime.now().isoformat()

    def to_dict(self):
        return {
            "MeterID": self.meter_id,
            "Region": self.region,
            "Area": self.area,
            "DwellingType": self.dwelling_type,
            "TimeStamp": self.timestamp
        }
