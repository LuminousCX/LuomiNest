"""附件上传 PDF/DOCX 解析不阻塞事件循环回归测试（09-11 调研遗留 P0）。

`/upload/forward` 的 PDF（PyMuPDF）/ DOCX（python-docx）解析是 CPU 密集的
同步调用，原先直接在事件循环内执行，大文件会阻塞所有并发请求。
修复：解析经 `asyncio.to_thread` 移入工作线程，接口行为不变。

验证方式：
1. 用阻塞 sleep 模拟慢解析，并发心跳任务仍能在事件循环上持续推进
   （若回退为同步调用，解析期间心跳完全停摆）；
2. 解析函数在工作线程执行（线程名非 MainThread）；
3. 成功/失败信封行为不变。
"""

import asyncio
import io
import threading
import time

import pytest
from fastapi import UploadFile

from app.api import attachment_api


class _StubRequest:
    """仅提供 forward_file 用到的 headers 视图。"""

    def __init__(self) -> None:
        self.headers = {}


def _make_upload(filename: str, payload: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(payload), filename=filename)


@pytest.mark.asyncio
async def test_pdf_parse_does_not_block_event_loop(monkeypatch):
    """PDF 解析期间事件循环必须保持可调度（to_thread 生效）。"""
    ticks = 0
    stop = asyncio.Event()

    async def heartbeat():
        nonlocal ticks
        while not stop.is_set():
            await asyncio.sleep(0.01)
            ticks += 1

    ran_threads: list[str] = []

    def slow_extract(file_bytes: bytes):
        ran_threads.append(threading.current_thread().name)
        time.sleep(0.6)  # 模拟 PyMuPDF 同步解析：阻塞当前线程
        return "pdf text", ""

    monkeypatch.setattr(attachment_api, "_extract_pdf_text", slow_extract)

    hb = asyncio.create_task(heartbeat())
    try:
        resp = await attachment_api.forward_file(
            _StubRequest(), _make_upload("doc.pdf", b"%PDF-1.4 fake")
        )
    finally:
        stop.set()
        await hb

    # 解析在工作线程执行
    assert ran_threads and ran_threads[0] != threading.main_thread().name
    # 0.6s 解析窗口内心跳持续推进：to_thread 生效（同步执行则 <5 tick）
    assert ticks >= 10, f"事件循环疑似被阻塞，心跳仅 {ticks} tick"
    assert resp["code"] == 0
    assert resp["data"] == {
        "content": "pdf text",
        "type": "text",
        "filename": "doc.pdf",
    }


@pytest.mark.asyncio
async def test_docx_parse_does_not_block_event_loop(monkeypatch):
    """DOCX 解析同走 to_thread，且成功信封行为不变。"""
    ran_threads: list[str] = []

    def fake_extract(file_bytes: bytes):
        ran_threads.append(threading.current_thread().name)
        return "docx text", ""

    monkeypatch.setattr(attachment_api, "_extract_docx_text", fake_extract)

    resp = await attachment_api.forward_file(
        _StubRequest(), _make_upload("doc.docx", b"PK fake docx")
    )

    assert ran_threads and ran_threads[0] != threading.main_thread().name
    assert resp["code"] == 0
    assert resp["data"] == {
        "content": "docx text",
        "type": "text",
        "filename": "doc.docx",
    }


@pytest.mark.asyncio
async def test_pdf_extract_failure_envelope_unchanged(monkeypatch):
    """解析失败时错误信封与错误码保持不变（行为兼容）。"""
    from fastapi.responses import JSONResponse

    monkeypatch.setattr(
        attachment_api, "_extract_pdf_text",
        lambda b: (None, "PDF文件解析失败: mocked"),
    )
    resp = await attachment_api.forward_file(
        _StubRequest(), _make_upload("bad.pdf", b"%PDF-1.4 broken")
    )
    assert isinstance(resp, JSONResponse)
    assert resp.status_code == 400
    assert resp.body is not None
    assert b"PDF_EXTRACT_FAILED" in resp.body
