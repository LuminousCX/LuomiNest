"""Fish Audio TTS Provider - 通过 Fish Audio TTS API 调用语音合成.

使用 httpx 调用 REST API（JSON 格式，无需 msgpack 依赖）.
支持通过 reference_id 指定音色，或通过角色名称自动搜索.
"""

import re

import httpx
from loguru import logger

from app.runtime.provider.tts.ports import TTSProvider


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio TTS Provider（通过 REST API 调用，JSON 格式）."""

    provider_name = "fish-audio"

    DEFAULT_VOICES = {
        "zh": "",
        "en": "",
    }

    DEFAULT_BASE_URL = "https://api.fish-audio.cn/v1"

    # reference_id 格式：32 位十六进制字符串
    _REFERENCE_ID_PATTERN = re.compile(r"^[a-fA-F0-9]{32}$")

    @classmethod
    def is_available(cls) -> bool:
        """httpx 是项目核心依赖，始终可用."""
        return True

    def __init__(self, **kwargs):
        self.api_key = kwargs.get("apiKey", "")
        if not self.api_key:
            raise ValueError("Fish Audio TTS 需要 apiKey 配置")

        self.reference_id = kwargs.get("voice") or ""
        self.base_url = (kwargs.get("baseUrl") or self.DEFAULT_BASE_URL).rstrip("/")

    async def synthesize(self, text: str, voice: str = "default") -> bytes:
        # voice 参数优先于构造函数中的 reference_id
        ref_id = voice if voice and voice != "default" else self.reference_id

        # 如果 voice 不是 32 位 hex，则视为角色名称，需要先搜索 reference_id
        if ref_id and not self._REFERENCE_ID_PATTERN.match(ref_id):
            ref_id = await self._search_reference_id(ref_id)

        if not ref_id:
            raise ValueError(
                "Fish Audio TTS 需要有效的 reference_id（32 位十六进制）或角色名称. "
                "请从 https://fish.audio/zh-CN/discovery 获取模型 ID"
            )

        payload = {
            "text": text,
            "chunk_length": 200,
            "format": "wav",
            "mp3_bitrate": 128,
            "references": [],
            "reference_id": ref_id,
            "normalize": True,
            "latency": "normal",
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{self.base_url}/tts",
                json=payload,
                headers=headers,
            )

            content_type = response.headers.get("content-type", "")
            if response.status_code == 200 and content_type.startswith("audio/"):
                audio_bytes = response.content
            else:
                error_text = response.text[:1024]
                raise RuntimeError(
                    f"Fish Audio API 请求失败: 状态码 {response.status_code}, 响应: {error_text}"
                )

        if not audio_bytes:
            raise RuntimeError("Fish Audio TTS 返回空音频数据")

        logger.info(f"[FishAudioTTS] synthesized: {text[:60]}... (ref_id={ref_id})")
        return audio_bytes

    async def _search_reference_id(self, character: str) -> str:
        """通过角色名称搜索 reference_id.

        按 score / task_count / created_at 三种排序尝试查找.
        """
        base = self.base_url.replace("/v1", "")
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=20) as client:
            for sort_by in ["score", "task_count", "created_at"]:
                params = {"title": character, "sort_by": sort_by}
                response = await client.get(
                    f"{base}/model",
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                resp_data = response.json()

                if resp_data.get("total", 0) == 0:
                    continue

                for item in resp_data.get("items", []):
                    if character in item.get("title", ""):
                        return item["_id"]

        return ""
