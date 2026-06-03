from loguru import logger

from .models import MemoryData, FactItem
from .store import MemoryStore


class FactManager:
    """事实生命周期管理：CRUD、去重、合并、纠正。"""

    MAX_FACTS = 100

    def __init__(self, store: MemoryStore):
        self._store = store

    def get_facts(self, category: str | None = None) -> list[FactItem]:
        data = self._store.load_data()
        if category:
            return [f for f in data.facts if f.category == category]
        return list(data.facts)

    def add_fact(self, fact: FactItem) -> None:
        data = self._store.load_data()
        self._merge_fact(data, fact)
        self._trim_facts(data)
        self._store.save_data(data)

    def remove_fact(self, fact_id: str) -> bool:
        data = self._store.load_data()
        before = len(data.facts)
        data.facts = [f for f in data.facts if f.id != fact_id]
        if len(data.facts) < before:
            self._store.save_data(data)
            return True
        return False

    def update_fact(
        self,
        fact_id: str,
        content: str | None = None,
        category: str | None = None,
        confidence: float | None = None,
    ) -> bool:
        data = self._store.load_data()
        for fact in data.facts:
            if fact.id == fact_id:
                if content is not None:
                    fact.content = content
                if category is not None:
                    fact.category = category
                if confidence is not None:
                    fact.confidence = confidence
                self._store.save_data(data)
                return True
        return False

    def clear_facts(self) -> None:
        data = self._store.load_data()
        data.facts = []
        self._store.save_data(data)

    def merge_facts(self, data: MemoryData, facts: list[FactItem]) -> None:
        """将新事实列表合并到已有数据中，处理纠正和去重。"""
        for fact in facts:
            if fact.category == "correction" and fact.source_error:
                self._apply_correction(data, fact)
            self._merge_fact(data, fact)
        self._trim_facts(data)

    def deprecate_old_name_facts(self, data: MemoryData, old_name: str, new_name: str) -> None:
        """名字变更时，降低包含旧名字的身份类事实的置信度。"""
        old_name_lower = old_name.strip().casefold()
        for fact in data.facts:
            if fact.confidence < 0.9:
                continue
            fact_lower = fact.content.strip().casefold()
            if old_name_lower not in fact_lower:
                continue
            if any(kw in fact_lower for kw in ("名字", "叫", "名为")):
                fact.confidence = min(fact.confidence, 0.3)

    def _merge_fact(self, data: MemoryData, fact: FactItem) -> None:
        """合并单条事实：存在相似则更新，否则追加。"""
        existing = self._find_similar_fact(data, fact.content)
        if existing:
            if fact.confidence > existing.confidence:
                existing.content = fact.content
                existing.confidence = fact.confidence
                existing.category = fact.category
                existing.source_error = fact.source_error
        else:
            data.facts.append(fact)

    def _trim_facts(self, data: MemoryData) -> None:
        if len(data.facts) > self.MAX_FACTS:
            data.facts.sort(key=lambda f: f.confidence, reverse=True)
            data.facts = data.facts[: self.MAX_FACTS]

    @staticmethod
    def _find_similar_fact(data: MemoryData, content: str) -> FactItem | None:
        normalized = content.strip().casefold()
        for fact in data.facts:
            if fact.content.strip().casefold() == normalized:
                return fact
        return None

    @staticmethod
    def _apply_correction(data: MemoryData, correction_fact: FactItem) -> None:
        error_text = correction_fact.source_error.strip().casefold()
        if not error_text:
            return
        for fact in data.facts:
            if error_text in fact.content.casefold():
                fact.confidence = min(fact.confidence, 0.3)
