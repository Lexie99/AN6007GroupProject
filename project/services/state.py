class MaintenanceState:
    def __init__(self, redis_client):
        self.redis = redis_client

    def enter_maintenance(self, duration=60):
        """原子操作设置维护状态，并设置过期时间（秒）"""
        # 设置 "maintenance_mode" 键，并在 duration 秒后自动失效
        self.redis.set("maintenance_mode", "1", ex=duration)

    def exit_maintenance(self):
        """清除维护状态"""
        self.redis.delete("maintenance_mode")

    def is_maintenance(self):
        """检查当前是否处于维护状态"""
        try:
            return self.redis.exists("maintenance_mode") == 1
        except Exception as e:
            print(f"Redis error: {str(e)}")
            return False
