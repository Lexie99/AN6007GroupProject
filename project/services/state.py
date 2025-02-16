import redis

class MaintenanceState:
    def __init__(self, redis_client):
        self.redis = redis_client

    def enter_maintenance(self):
        """原子操作设置维护状态"""
        self.redis.set("maintenance_mode", "1")

    def exit_maintenance(self):
        """清除维护状态"""
        self.redis.delete("maintenance_mode")

    def is_maintenance(self):
        """检查当前是否处于维护状态"""
        return self.redis.exists("maintenance_mode") == 1