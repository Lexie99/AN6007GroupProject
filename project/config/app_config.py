# config/app_config.py

import json
import os
from collections import defaultdict

class AppConfig:
    """
    负责加载 config.json,提供 region_area_mapping / dwelling_type_set 等配置信息。
    """

    def __init__(self, config_path=None):
        if not config_path:
            config_path = os.path.join("project/config/config.json")
        self.config_path = config_path

        self.region_area_mapping = defaultdict(set)  # region -> set(area)
        self.dwelling_type_set = set()               # 用于校验 Dwelling Type

        self.load_config()

    def load_config(self):
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            
            area_data = config.get("area_data", {})
            areas   = area_data.get("Area", [])
            regions = area_data.get("Region", [])
            for region, area in zip(regions, areas):
                self.region_area_mapping[region].add(area)

            dwelling_info = config.get("dwelling_data", {})
            dwelling_list = dwelling_info.get("DwellingType", [])
            for d in dwelling_list:
                self.dwelling_type_set.add(d)

            print("[AppConfig] Loaded config.json successfully.")
        except Exception as e:
            print(f"[AppConfig] Failed to load config: {e}")
