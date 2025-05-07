import json
import os
from datetime import datetime

class CacheManager:
    def __init__(self):
        self.cache_file = "data/cache.json"
        self.cache = self._load_cache()
        
    def _load_cache(self):
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Error loading cache: {e}")
                return {"contractors": {}, "last_update": {}}
        return {"contractors": {}, "last_update": {}}
        
    def _save_cache(self):
        os.makedirs(os.path.dirname(self.cache_file), exist_ok=True)
        with open(self.cache_file, 'w') as f:
            json.dump(self.cache, f, indent=2)
            
    def get_contractor_last_modified(self, contractor_id):
        return self.cache["contractors"].get(contractor_id, {}).get("last_modified")
        
    def update_contractor_cache(self, contractor_id, last_modified):
        if contractor_id not in self.cache["contractors"]:
            self.cache["contractors"][contractor_id] = {}
        self.cache["contractors"][contractor_id]["last_modified"] = last_modified
        self._save_cache()
        
    def needs_update(self, contractor_id, current_last_modified):
        cached_last_modified = self.get_contractor_last_modified(contractor_id)
        if not cached_last_modified:
            return True
        return cached_last_modified != current_last_modified
        
    def get_all_contractors(self):
        return self.cache["contractors"]
        
    def clear_cache(self):
        self.cache = {"contractors": {}, "last_update": {}}
        self._save_cache() 