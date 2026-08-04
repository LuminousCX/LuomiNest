"""一次性诊断脚本：校验插件市场发布源配置与连通性。

直接运行 ``python _verify_registry_sources.py`` 即可打印所有源、当前活跃 URL
及每个源的延迟/健康状态。仅用于本地排障，不参与应用启动流程。
"""
import asyncio

from app.infrastructure.sync.registry_sources import (
    build_registry_url,
    get_registry_sources,
    ping_all_sources,
)


async def main() -> None:
    """打印发布源列表、活跃 URL 及各源 ping 结果。"""
    sources = get_registry_sources()
    print("Sources:", [s["id"] for s in sources])
    print("Active URL:", build_registry_url())

    results = await ping_all_sources(timeout=5.0)
    for r in results:
        print(
            f"{r['id']}: healthy={r['healthy']} latency={r['latencyMs']}ms "
            f"status={r.get('statusCode')}"
        )


if __name__ == "__main__":
    asyncio.run(main())
