"""LuomiNest STT 端口定义（L1 能力内核）。

语音识别能力的协议抽象；各引擎实现位于本包其他模块，向内实现本端口。
"""
from abc import ABC, abstractmethod


class STTProvider(ABC):
    provider_name: str = "base"

    @abstractmethod
    async def transcribe(self, audio_data: bytes, format: str = "wav") -> str:
        ...
