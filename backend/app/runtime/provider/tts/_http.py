"""云端 TTS 适配器公共 HTTP 模板.

收口 minimax / siliconflow / fish_audio / gemini 四个云 TTS 适配器中
逐字相同的 "httpx.AsyncClient post + raise_for_status + 空音频 RuntimeError"
模板，错误文案通过 error_prefix 保持各适配器可辨识。
"""

import httpx


async def post_json_for_audio(
    url: str,
    payload: dict,
    headers: dict | None,
    timeout: float,
    *,
    error_prefix: str,
    require_content_type: str | None = None,
    empty_error: str | None = None,
) -> bytes:
    """POST JSON 请求并返回音频 bytes.

    Args:
        url: 请求地址
        payload: JSON 请求体
        headers: 请求头（可为 None）
        timeout: httpx 超时（秒）
        error_prefix: 错误消息前缀（如 "SiliconFlow TTS"），保证各适配器文案可辨识
        require_content_type: 若指定，则 200 响应的 content-type 必须以该前缀开头
            （如 "audio/"），否则按失败处理
        empty_error: 覆盖默认的空音频错误消息（默认 f"{error_prefix} 返回空音频数据"）

    Returns:
        响应体 bytes（音频数据）

    Raises:
        httpx.HTTPStatusError: 非 2xx 响应
        RuntimeError: 响应 content-type 不符或音频数据为空
    """
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        if require_content_type is not None:
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith(require_content_type):
                error_text = response.text[:1024]
                raise RuntimeError(
                    f"{error_prefix} API 请求失败: 状态码 {response.status_code}, 响应: {error_text}"
                )

        # 云端 TTS 返回二进制音频数据
        audio_bytes = response.content

    if not audio_bytes:
        raise RuntimeError(empty_error or f"{error_prefix} 返回空音频数据")

    return audio_bytes
