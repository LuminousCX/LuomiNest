import asyncio
from app.infrastructure.sync.registry_sources import get_registry_sources, build_registry_url, ping_all_sources

sources = get_registry_sources()
print('Sources:', [s['id'] for s in sources])
print('Active URL:', build_registry_url())

async def main():
    results = await ping_all_sources(timeout=5.0)
    for r in results:
        print(f"{r['id']}: healthy={r['healthy']} latency={r['latencyMs']}ms status={r.get('statusCode')}")

asyncio.run(main())
