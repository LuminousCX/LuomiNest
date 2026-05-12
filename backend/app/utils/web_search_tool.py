"""
Web 搜索工具 —— DuckDuckGo Instant Answer + 降级抓取

功能：
  接收搜索查询，先走 DuckDuckGo Instant Answer API（免费无 key），
  失败时降级到 HTML 抓取或返回空结果。

设计原则：
  1. DuckDuckGo 优先（免费、结构化、隐私友好）
  2. 失败优雅降级，不抛异常，不中断对话
  3. 单次搜索返回 Top 3 条结果摘要
"""

import asyncio
import json
from datetime import datetime
from loguru import logger

import aiohttp


_DDG_IA_URL = "https://api.duckduckgo.com/"


async def _ddg_instant_answer(query: str) -> str | None:
    """DuckDuckGo Instant Answer API —— 免费、无 API Key

    参数:
        query: 搜索查询

    返回:
        摘要文本，失败返回 None
    """
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
        "t": "luominest",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(_DDG_IA_URL, params=params, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status != 200:
                    logger.debug(f"[WebSearch] DDG IA 状态 {resp.status}")
                    return None
                data = await resp.json()

        parts = []
        if data.get("AbstractText"):
            parts.append(data["AbstractText"])
            if data.get("AbstractURL"):
                parts.append(f"来源: {data['AbstractURL']}")
        if data.get("Answer"):
            parts.insert(0, f"直接答案: {data['Answer']}")
        if data.get("RelatedTopics"):
            for topic in data["RelatedTopics"][:3]:
                if isinstance(topic, dict) and topic.get("Text"):
                    parts.append(f"- {topic['Text']}")

        if not parts:
            return None

        return "\n".join(parts)
    except Exception as e:
        logger.debug(f"[WebSearch] DDG IA 异常: {e}")
        return None


async def _ddg_html_search(query: str) -> str | None:
    """DuckDuckGo HTML 搜索结果抓取（降级方案）

    参数:
        query: 搜索查询

    返回:
        搜索结果摘要，失败返回 None
    """
    params = {
        "q": query,
        "kl": "cn-zh",  # 中国中文区域
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://html.duckduckgo.com/html/",
                params=params,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    return None
                html = await resp.text()

        from html.parser import HTMLParser as _HTMLParser

        results: list[str] = []

        class ResultParser(_HTMLParser):
            def __init__(self):
                super().__init__()
                self.in_snippet = False
                self.in_title = False
                self.current_title = ""
                self.current_snippet = ""

            def handle_starttag(self, tag, attrs):
                attrs_dict = dict(attrs)
                cls = attrs_dict.get("class", "")
                if tag == "a" and "result__a" in cls:
                    self.in_title = True
                elif tag == "a" and "result__snippet" in cls:
                    self.in_snippet = True

            def handle_endtag(self, tag):
                if tag == "a" and self.in_title:
                    self.in_title = False
                elif tag == "a" and self.in_snippet:
                    self.in_snippet = False
                    if self.current_title or self.current_snippet:
                        results.append(
                            f"{self.current_title.strip()}: {self.current_snippet.strip()}"
                        )
                    self.current_title = ""
                    self.current_snippet = ""

            def handle_data(self, data):
                if self.in_title:
                    self.current_title += data
                elif self.in_snippet:
                    self.current_snippet += data

        parser = ResultParser()
        parser.feed(html)
        parser.close()

        if not results:
            return None

        return "\n".join(results[:5])
    except Exception as e:
        logger.debug(f"[WebSearch] DDG HTML 异常: {e}")
        return None


async def search_web(query: str) -> str:
    """对外统一接口 —— 搜索并返回最多 3 条结果摘要

    执行策略:
      1. DuckDuckGo Instant Answer API（快速、结构化）
      2. 降级 → DuckDuckGo HTML 抓取
      3. 双降级 → 返回提示文本

    参数:
        query: 搜索查询

    返回:
        搜索结果文本，失败返回 "暂无搜索结果"
    """
    logger.info(f"[WebSearch] 查询: {query}")

    # 第一优先：Instant Answer API
    result = await _ddg_instant_answer(query)
    if result and len(result) > 20:
        elapsed_str = f"[WebSearch] DDG IA 结果: {len(result)} 字符"
        logger.info(elapsed_str)
        return result

    # 降级：HTML 抓取
    result = await _ddg_html_search(query)
    if result and len(result) > 20:
        logger.info(f"[WebSearch] DDG HTML 结果: {len(result)} 字符")
        return result

    return "暂无搜索结果"


# =============================================================================
# 直接运行测试
# =============================================================================
if __name__ == "__main__":
    import sys

    async def main():
        query = sys.argv[1] if len(sys.argv) > 1 else "2026年软考时间"
        result = await search_web(query)
        print(f"Query: {query}")
        print(f"Result:\n{result}")

    asyncio.run(main())