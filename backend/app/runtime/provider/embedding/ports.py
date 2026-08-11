"""LuomiNest Embedding 端口定义（L1 能力内核）。

文本嵌入能力的协议抽象；各实现向内实现本端口。
"""
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...
