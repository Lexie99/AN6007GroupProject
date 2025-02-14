# services/redis_service.py
import os
import redis
import json
from datetime import datetime

class RedisService:
    """
    集中管理 Redis 连接与常用操作
    """
    def __init__(self):
        self.host = os.getenv('REDIS_HOST', 'localhost')
        self.port = int(os.getenv('REDIS_PORT', 6379))
        self.client = redis.Redis(host=self.host, port=self.port, decode_responses=True)

    # ====== 注册用户相关 ======
    def is_meter_registered(self, meter_id):
        return self.client.hexists("all_users", meter_id)

    def register_meter(self, meter_id):
        self.client.hset("all_users", meter_id, 1)

    def set_user_data(self, meter_id, data_dict):
        key = f"user_data:{meter_id}"
        self.client.hset(key, mapping=data_dict)

    # ====== 电表读数相关 ======
    def add_meter_reading(self, meter_id, record_str, score):
        key = f"meter:{meter_id}:history"
        self.client.zadd(key, {record_str: score})

    def get_meter_readings_by_score(self, meter_id, min_score, max_score):
        key = f"meter:{meter_id}:history"
        return self.client.zrangebyscore(key, min_score, max_score)

    # ====== 日志操作 (/get_logs) ======
    def log_event(self, log_type, message, max_len=1000):
        """
        简易日志写入 logs:<log_type> 列表
        """
        key = f"logs:{log_type}"
        self.client.rpush(key, message)
        self.client.ltrim(key, -max_len, -1)

    def get_logs(self, log_type, limit=50):
        key = f"logs:{log_type}"
        return self.client.lrange(key, -limit, -1)
    
    # ====== 备份相关操作 ======
    def store_backup_usage(self, date_str, meter_id, usage):
        """
        将某日某电表的使用量写入 backup:meter_data:{date_str} 哈希中
        usage 可以是数字或字符串, 视需要
        """
        key = f"backup:meter_data:{date_str}"
        self.client.hset(key, meter_id, usage)

    def get_backup_data(self, date_str):
        """
        获取指定日期的备份哈希, 返回 dict[meter_id -> usage_string]
        若没有则返回空dict
        """
        key = f"backup:meter_data:{date_str}"
        return self.client.hgetall(key)

    # ====== 维护模式：move pending to history ======
    def move_pending_to_history(self, meter_id):
        pending_key = f"meter:{meter_id}:pending"
        data_list = self.client.lrange(pending_key, 0, -1)
        if not data_list:
            return 0

        count = 0
        for raw in data_list:
            record = json.loads(raw)
            ts = datetime.fromisoformat(record["timestamp"]).timestamp()
            self.add_meter_reading(meter_id, raw, ts)
            count += 1
        # 清空 pending
        self.client.delete(pending_key)
        return count

# ====== 维护模式：remove old history ======
    def remove_old_history(self, keep_days):
        """
        删除 meter:*:history 中早于 cutoff_timestamp 的读数
        返回删除的总记录数
        """
        from datetime import datetime, timedelta

        cutoff_date = datetime.now() - timedelta(days=keep_days)
        cutoff_ts = cutoff_date.timestamp()

        deleted_records = 0
        for key in self.client.scan_iter("meter:*:history"):
            # zremrangebyscore(key, -inf, cutoff_ts)
            removed = self.client.zremrangebyscore(key, "-inf", cutoff_ts)
            deleted_records += removed

        return deleted_records

    # ====== 测试辅助：清理数据 ======
    def clear_test_data(self):
        """
        仅删除all_users、meter:*、user_data:* 方便测试
        """
        if self.client.exists("all_users"):
            self.client.delete("all_users")
        meter_keys = list(self.client.scan_iter("meter:*"))
        for mk in meter_keys:
            self.client.delete(mk)
        user_keys = list(self.client.scan_iter("user_data:*"))
        for uk in user_keys:
            self.client.delete(uk)
