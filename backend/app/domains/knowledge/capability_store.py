"""
长期能力库 - 沉淀高价值的工具流程、数据、优化方案

特性：
1. 与对话上下文隔离，不污染对话历史
2. 支持能力沉淀和检索
3. 后续同类任务可直接调用
"""

import json
import hashlib
import time
from pathlib import Path
from loguru import logger


# 能力库存储路径
_CAPABILITY_STORE_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "capability_store.json"


class CapabilityStore:
    """长期能力库
    
    用于存储和检索高价值的能力沉淀，包括：
    - 工具流程模板
    - 常见问题的解决方案
    - 用户偏好设置
    - 任务执行经验
    """
    
    def __init__(self, store_path: Path | None = None):
        self.store_path = store_path or _CAPABILITY_STORE_PATH
        self._ensure_store()
    
    def _ensure_store(self) -> None:
        """确保存储文件存在"""
        if not self.store_path.exists():
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            self._save_store({
                "capabilities": {},
                "patterns": {},
                "experiences": [],
                "updated_at": time.time(),
            })
    
    def _load_store(self) -> dict:
        """加载存储数据"""
        try:
            with open(self.store_path, 'r', encoding='utf-8') as f:
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
        """保存存储数据"""
        try:
            with open(self.store_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[CapabilityStore] Failed to save store: {e}")
    
    def _generate_key(self, task_type: str, context: str) -> str:
        """生成能力键"""
        content = f"{task_type}:{context}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def save_capability(self, task_type: str, capability: dict) -> str:
        """保存能力
        
        参数：
        - task_type: 任务类型（如：weather_query, travel_planning）
        - capability: 能力数据，包含流程、参数、结果模板等
        
        返回：
        - 能力键
        """
        store = self._load_store()
        
        # 生成能力键
        context = json.dumps(capability.get("context", {}), sort_keys=True)
        key = self._generate_key(task_type, context)
        
        # 保存能力
        capability["task_type"] = task_type
        capability["created_at"] = time.time()
        capability["use_count"] = 0
        
        store["capabilities"][key] = capability
        store["updated_at"] = time.time()
        
        self._save_store(store)
        logger.info(f"[CapabilityStore] Saved capability: {key} for {task_type}")
        
        return key
    
    def get_capability(self, key: str) -> dict | None:
        """获取能力"""
        store = self._load_store()
        capability = store["capabilities"].get(key)
        
        if capability:
            # 更新使用次数
            capability["use_count"] = capability.get("use_count", 0) + 1
            capability["last_used"] = time.time()
            store["capabilities"][key] = capability
            self._save_store(store)
        
        return capability
    
    def find_capabilities(self, task_type: str) -> list[dict]:
        """查找指定类型的所有能力"""
        store = self._load_store()
        results = []
        
        for key, capability in store["capabilities"].items():
            if capability.get("task_type") == task_type:
                results.append({"key": key, **capability})
        
        # 按使用次数排序
        results.sort(key=lambda x: x.get("use_count", 0), reverse=True)
        
        return results
    
    def save_pattern(self, pattern_type: str, pattern: dict) -> None:
        """保存执行模式
        
        参数：
        - pattern_type: 模式类型（如：error_recovery, tool_sequence）
        - pattern: 模式数据
        """
        store = self._load_store()
        
        if pattern_type not in store["patterns"]:
            store["patterns"][pattern_type] = []
        
        pattern["created_at"] = time.time()
        store["patterns"][pattern_type].append(pattern)
        store["updated_at"] = time.time()
        
        self._save_store(store)
        logger.info(f"[CapabilityStore] Saved pattern: {pattern_type}")
    
    def get_patterns(self, pattern_type: str) -> list[dict]:
        """获取指定类型的所有模式"""
        store = self._load_store()
        return store["patterns"].get(pattern_type, [])
    
    def save_experience(self, experience: dict) -> None:
        """保存执行经验
        
        参数：
        - experience: 经验数据，包含任务类型、成功/失败、解决方案等
        """
        store = self._load_store()
        
        experience["created_at"] = time.time()
        store["experiences"].append(experience)
        
        # 限制经验数量，保留最近的100条
        if len(store["experiences"]) > 100:
            store["experiences"] = store["experiences"][-100:]
        
        store["updated_at"] = time.time()
        self._save_store(store)
        logger.info(f"[CapabilityStore] Saved experience: {experience.get('task_type', 'unknown')}")
    
    def find_similar_experiences(self, task_type: str, limit: int = 5) -> list[dict]:
        """查找相似任务的经验"""
        store = self._load_store()
        
        # 筛选相同任务类型的经验
        similar = [
            exp for exp in store["experiences"]
            if exp.get("task_type") == task_type
        ]
        
        # 优先返回成功的经验
        similar.sort(key=lambda x: (
            x.get("success", False),
            x.get("created_at", 0)
        ), reverse=True)
        
        return similar[:limit]


# 全局能力库实例
_capability_store: CapabilityStore | None = None


def get_capability_store() -> CapabilityStore:
    """获取能力库实例"""
    global _capability_store
    if _capability_store is None:
        _capability_store = CapabilityStore()
    return _capability_store


def prune_context_for_storage(messages: list[dict]) -> list[dict]:
    """剪枝上下文用于存储
    
    短期任务上下文剪枝规则：
    1. 仅保留核心需求与结论
    2. 移除工具调用、试错、部署的细节
    3. 保留用户的原始问题和AI的最终回复
    """
    pruned = []
    
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        
        # 跳过系统消息
        if role == "system":
            continue
        
        # 跳过工具调用细节
        if "<tool_call" in content:
            continue
        
        # 跳过工具执行结果
        if "[Tool:" in content or "工具执行结果" in content:
            continue
        
        # 跳过错误信息（仅跳过明显的错误标记，保留正常内容）
        if content.startswith("[Error]") or content.startswith("Error:"):
            continue
        
        pruned.append(msg)
    
    return pruned


def extract_task_conclusion(messages: list[dict]) -> str:
    """从对话中提取任务结论
    
    用于在任务完成后提取核心结论，存入长期能力库
    """
    # 获取最后一条助手消息作为结论
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", "")
            # 截取前200字符作为结论摘要
            if len(content) > 200:
                return content[:200] + "..."
            return content
    
    return ""
