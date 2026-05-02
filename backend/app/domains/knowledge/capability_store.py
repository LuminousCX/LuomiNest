import json
import hashlib
import threading
import time
from pathlib import Path
from loguru import logger


from app.core.config import settings

_CAPABILITY_STORE_PATH = Path(settings.DATA_DIR) / "capability_store.json"


class CapabilityStore:
    
    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or _CAPABILITY_STORE_PATH
        self._lock = threading.Lock()
        self._ensure_store()
    
    def _ensure_store(self) -> None:
        if not self.store_path.exists():
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_store({
                "capabilities": {},
                "patterns": {},
                "experiences": [],
                "updated_at": time.time(),
            })
    
    def _load_store(self) -> dict:
        try:
            with open(self.store_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"[CapabilityStore] Failed to load store: {e}")
            return {
                "capabilities": {},
                "patterns": {},
                "experiences": [],
                "updated_at": time.time(),
            }
    
    def _save_store(self, data: dict) -> None:
        try:
            with open(self.store_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[CapabilityStore] Failed to save store: {e}")
    
    def _generate_key(self, task_type: str, context: str) -> str:
        content = f"{task_type}:{context}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def save_capability(self, task_type: str, capability: dict) -> str:
        with self._lock:
            store = self._load_store()
            
            context = json.dumps(capability.get("context", {}), sort_keys=True)
            key = self._generate_key(task_type, context)
            
            existing = store["capabilities"].get(key)
            capability["task_type"] = task_type
            if existing:
                capability["use_count"] = existing.get("use_count", 0)
                capability["created_at"] = existing.get("created_at", time.time())
            else:
                capability["use_count"] = 0
                capability["created_at"] = time.time()
            
            store["capabilities"][key] = capability
            store["updated_at"] = time.time()
            
            self._save_store(store)
            logger.info(f"[CapabilityStore] Saved capability: {key} for {task_type}")
            
            return key
    
    def get_capability(self, key: str) -> dict | None:
        with self._lock:
            store = self._load_store()
            capability = store["capabilities"].get(key)
            
            if capability:
                capability["use_count"] = capability.get("use_count", 0) + 1
                capability["last_used"] = time.time()
                store["capabilities"][key] = capability
                self._save_store(store)
            
            return capability
    
    def find_capabilities(self, task_type: str) -> list[dict]:
        with self._lock:
            store = self._load_store()
            results = []
            
            for key, capability in store["capabilities"].items():
                if capability.get("task_type") == task_type:
                    results.append({"key": key, **capability})
            
            results.sort(key=lambda x: x.get("use_count", 0), reverse=True)
            
            return results
    
    def save_pattern(self, pattern_type: str, pattern: dict) -> None:
        with self._lock:
            store = self._load_store()
            
            if pattern_type not in store["patterns"]:
                store["patterns"][pattern_type] = []
            
            pattern["created_at"] = time.time()
            store["patterns"][pattern_type].append(pattern)
            store["patterns"][pattern_type] = store["patterns"][pattern_type][-100:]
            store["updated_at"] = time.time()
            
            self._save_store(store)
            logger.info(f"[CapabilityStore] Saved pattern: {pattern_type}")
    
    def get_patterns(self, pattern_type: str) -> list[dict]:
        with self._lock:
            store = self._load_store()
            return store["patterns"].get(pattern_type, [])
    
    def save_experience(self, experience: dict) -> None:
        with self._lock:
            store = self._load_store()
            
            experience["created_at"] = time.time()
            store["experiences"].append(experience)
            
            if len(store["experiences"]) > 100:
                store["experiences"] = store["experiences"][-100:]
            
            store["updated_at"] = time.time()
            self._save_store(store)
            logger.info(f"[CapabilityStore] Saved experience: {experience.get('task_type', 'unknown')}")
    
    def find_similar_experiences(self, task_type: str, limit: int = 5) -> list[dict]:
        with self._lock:
            store = self._load_store()
            
            similar = [
                exp for exp in store["experiences"]
                if exp.get("task_type") == task_type
            ]
            
            similar.sort(key=lambda x: (
                x.get("success", False),
                x.get("created_at", 0)
            ), reverse=True)
            
            return similar[:limit]


_capability_store: CapabilityStore | None = None
_capability_store_lock = threading.Lock()


def get_capability_store() -> CapabilityStore:
    global _capability_store
    if _capability_store is None:
        with _capability_store_lock:
            if _capability_store is None:
                _capability_store = CapabilityStore()
    return _capability_store


def prune_context_for_storage(messages: list[dict]) -> list[dict]:
    pruned = []
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content")
        
        if role == "system":
            continue
        
        if not isinstance(content, str):
            content = "" if content is None else str(content)
        
        if "<tool_call" in content:
            continue
        
        if "[Tool:" in content or "工具执行结果" in content:
            continue
        
        if content.startswith("[Error]") or content.startswith("Error:"):
            continue
        
        pruned.append(msg)
    
    return pruned


def extract_task_conclusion(messages: list[dict]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content")
            if not isinstance(content, str):
                content = "" if content is None else str(content)
            if len(content) > 200:
                return content[:200] + "..."
            return content
    
    return ""
