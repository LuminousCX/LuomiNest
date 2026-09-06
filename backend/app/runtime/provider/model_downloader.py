"""sherpa-onnx 模型下载器（STT/TTS 共用）.

原先 sherpa_onnx_stt / sherpa_onnx_tts 各自维护一份几乎逐行相同的
"下载 + 解压 + 重试" 实现，本模块将其收口为单一入口
`download_and_extract_model`，通过参数保留两处的日志前缀、
提示文案、解压目录名与校验文件差异。
"""

import asyncio
import shutil
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path

import httpx
from loguru import logger


async def download_and_extract_model(
    url: str,
    target_dir: Path,
    *,
    log_prefix: str,
    download_label: str,
    size_hint: str,
    timeout: float,
    archive_name: str,
    tmp_prefix: str = "sherpa_",
    extracted_dirname: str | None = None,
    expected_files: tuple[str, ...] = ("model.onnx",),
    missing_error: Callable[[Path], str] | None = None,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> None:
    """自动下载并解压模型压缩包（失败自动重试）.

    Args:
        url: 模型压缩包下载地址
        target_dir: 模型目标目录（解压后应包含 expected_files 中的文件）
        log_prefix: 日志前缀（如 "[SherpaOnnxSTT]"）
        download_label: 下载日志中的模型名称（如 "SenseVoice 模型" / "模型"）
        size_hint: 体积提示（如 "约 220MB"）
        timeout: httpx 下载超时（秒）
        archive_name: 临时目录中的压缩包文件名
        tmp_prefix: 临时目录前缀
        extracted_dirname: 解压后的目录名；None 时使用 target_dir.name
        expected_files: 解压后必须存在其一的关键文件（相对于 target_dir）
        missing_error: 关键文件缺失时的错误消息构造函数（入参为 target_dir）
        max_retries: 最大尝试次数
        retry_delay: 两次尝试之间的等待秒数
    """
    if missing_error is None:
        missing_error = lambda d: f"解压后未找到模型文件: {d}"  # noqa: E731

    target_dir.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"{log_prefix} 开始下载 {download_label}: {url}")
    logger.info(f"{log_prefix} 目标目录: {target_dir}")
    logger.info(f"{log_prefix} 模型{size_hint}，请耐心等待...")

    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            await _download_and_extract_once(
                url,
                target_dir,
                log_prefix=log_prefix,
                timeout=timeout,
                tmp_prefix=tmp_prefix,
                archive_name=archive_name,
                extracted_dirname=extracted_dirname,
                expected_files=expected_files,
                missing_error=missing_error,
            )
            logger.info(f"{log_prefix} 模型下载完成（第 {attempt} 次尝试）")
            return
        except Exception as e:
            last_error = e
            logger.warning(f"{log_prefix} 下载失败（第 {attempt}/{max_retries} 次）: {e}")
            if attempt < max_retries:
                logger.info(f"{log_prefix} 等待 {retry_delay:g} 秒后重试...")
                await asyncio.sleep(retry_delay)

    raise RuntimeError(
        f"模型自动下载失败（已重试 {max_retries} 次）: {last_error}. "
        f"请手动下载 {url} 并解压到 {target_dir}"
    )


async def _download_and_extract_once(
    url: str,
    target_dir: Path,
    *,
    log_prefix: str,
    timeout: float,
    tmp_prefix: str,
    archive_name: str,
    extracted_dirname: str | None,
    expected_files: tuple[str, ...],
    missing_error: Callable[[Path], str],
) -> None:
    """执行一次下载+解压流程."""
    with tempfile.TemporaryDirectory(prefix=tmp_prefix) as tmp_dir:
        tmp_path = Path(tmp_dir)
        archive_path = tmp_path / archive_name

        # 流式下载，显示进度
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            async with client.stream("GET", url) as resp:
                resp.raise_for_status()
                total = int(resp.headers.get("content-length", 0))
                downloaded = 0
                last_log_pct = 0

                with open(archive_path, "wb") as f:
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = int(downloaded * 100 / total)
                            if pct >= last_log_pct + 10:
                                last_log_pct = pct
                                logger.info(
                                    f"{log_prefix} 下载进度: {pct}% "
                                    f"({downloaded // 1048576}MB / {total // 1048576}MB)"
                                )

        logger.info(f"{log_prefix} 下载完成，开始解压...")

        # 解压 tar.bz2
        with tarfile.open(archive_path, "r:bz2") as tar:
            tar.extractall(path=tmp_path)

        # 解压后的目录名（回退查找任意解压目录）
        extracted_dir = tmp_path / (extracted_dirname or target_dir.name)
        if not extracted_dir.exists():
            extracted_dirs = [d for d in tmp_path.iterdir() if d.is_dir() and d.name != ""]
            if extracted_dirs:
                extracted_dir = extracted_dirs[0]
            else:
                raise RuntimeError("解压后未找到模型目录")

        # 移动到目标目录
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extracted_dir), str(target_dir))

        # 验证关键文件（任一存在即可）
        for candidate in (target_dir / name for name in expected_files):
            if candidate.exists():
                break
        else:
            raise FileNotFoundError(missing_error(target_dir))

        logger.info(f"{log_prefix} 解压完成: {target_dir}")
