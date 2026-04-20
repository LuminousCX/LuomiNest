import json
import os

class Config:
    def __init__(self):
        self.config = {
            "system_name": "汐汐",
            "admin_password": "admin123",
            "memory_limit": 1000,
            "knowledge_base_path": "data/knowledge_base.json",
            "vector_store_path": "data/vector_store.json",
            "memory_path": "data/memory.json"
        }
    
    def get(self, key, default=None):
        return self.config.get(key, default)
    
    def set(self, key, value):
        self.config[key] = value
    
    def load(self, path):
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                self.config.update(json.load(f))
    
    def save(self, path):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

config = Config()