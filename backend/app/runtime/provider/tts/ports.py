"""LuomiNest TTS 端口定义（L1 能力内核）。

语音合成能力的协议抽象；各引擎实现位于本包其他模块，向内实现本端口。
"""
from abc import ABC, abstractmethod


class TTSProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        raise NotImplementedError
