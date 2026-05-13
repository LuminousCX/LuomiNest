"""
Web 搜索工具 —— 360 搜索优先 + DuckDuckGo 降级

功能：
  接收搜索查询，先走 360 搜索（国内可访问、服务端渲染），
  失败时降级到 DuckDuckGo 或返回空结果。

设计原则：
  1. 360 搜索优先（国内网络友好、结果在 HTML 中）
  2. 失败优雅降级，不抛异常，不中断对话
  3. 单次搜索返回 Top 5 条结果摘要
"""

import asyncio
import re
from urllib.parse import quote

import aiohttp
from loguru import logger


# =============================================================================
# 360 搜索 —— 国内网络友好，结果在 HTML 中
# =============================================================================

_360_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def _extract_360_results(html: str) -> list[str]:
    """从 360 搜索结果 HTML 中提取标题+摘要

    360 结果结构：
      <li class="res-list">
        <h3 class="res-title"><a>...</a></h3>
        <p class="res-list-summary">...</p>
      </li>
    """
    results: list[str] = []

    # 提取所有 res-list 块
    result_blocks = re.findall(
        r'<li[^>]*class="res-list"[^>]*>.*?</li>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    for block in result_blocks[:5]:
        # 提取标题：h3.res-title > a
        title_match = re.search(
            r'<h3[^>]*class="res-title"[^>]*>.*?<a[^>]*>(.*?)</a>.*?</h3>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        title = ""
        if title_match:
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip()
            title = title.replace('&nbsp;', ' ')

        # 提取摘要：span.res-list-summary 或 p.res-list-summary
        snippet_match = re.search(
            r'<(?:span|p)[^>]*class="res-list-summary"[^>]*>(.*?)</(?:span|p)>',
            block,
            re.DOTALL | re.IGNORECASE,
        )
        snippet = ""
        if snippet_match:
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip()
            snippet = snippet.replace('&nbsp;', ' ')

        if title or snippet:
            results.append(f"{title}: {snippet}".strip(": "))

    return results


async def _360_search(query: str) -> str | None:
    """360 搜索 HTML 抓取

    参数:
        query: 搜索查询

    返回:
        搜索结果摘要文本，失败返回 None
    """
    encoded = quote(query)
    url = f"https://www.so.com/s?q={encoded}"

    try:
        async with aiohttp.ClientSession(headers=_360_HEADERS) as session:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=15),
                allow_redirects=True,
            ) as resp:
                if resp.status != 200:
                    logger.debug(f"[WebSearch] 360 状态 {resp.status}")
                    return None
                html = await resp.text()

        results = _extract_360_results(html)
        if results:
            return "\n".join(results[:5])

        return None
    except Exception as e:
        logger.debug(f"[WebSearch] 360 异常: {e}")
        return None


# =============================================================================
# DuckDuckGo Instant Answer —— 降级方案
# =============================================================================

_DDG_IA_URL = "https://api.duckduckgo.com/"


async def _ddg_instant_answer(query: str) -> str | None:
    """DuckDuckGo Instant Answer API —— 免费、无 API Key"""
    params = {
        "q": query,
        "format": "json",
        "no_html": "1",
        "skip_disambig": "1",
        "t": "luominest",
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                _DDG_IA_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as resp:
                if resp.status != 200:
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
    except Exception:
        return None


# =============================================================================
# 对外统一接口
# =============================================================================

async def search_web(query: str) -> str:
    """对外统一接口 —— 搜索并返回最多 5 条结果摘要

    执行策略:
      1. 360 搜索（国内网络友好，结果在 HTML 中）
      2. 降级 → DuckDuckGo Instant Answer
      3. 双降级 → 返回提示文本

    参数:
        query: 搜索查询

    返回:
        搜索结果文本，失败返回 "暂无搜索结果"
    """
    logger.info(f"[WebSearch] 查询: {query}")

    # 第一优先：360 搜索
    result = await _360_search(query)
    if result and len(result) > 20:
        logger.info(f"[WebSearch] 360 结果: {len(result)} 字符")
        return result

    # 降级：DuckDuckGo Instant Answer
    result = await _ddg_instant_answer(query)
    if result and len(result) > 20:
        logger.info(f"[WebSearch] DDG IA 结果: {len(result)} 字符")
        return result

    logger.warning("[WebSearch] 所有搜索源均失败")
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
