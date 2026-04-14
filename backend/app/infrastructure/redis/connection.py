from loguru import logger

_redis_pool = None


async def init_redis():
    global _redis_pool
    try:
        import redis.asyncio as aioredis
        from app.core.config import settings

        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        await _redis_pool.ping()
        logger.info("Redis connected successfully")
    except Exception as e:
        logger.warning(f"Redis connection failed: {e}. Running without Redis.")
        _redis_pool = None


async def close_redis():
    global _redis_pool
    if _redis_pool:
        await _redis_pool.close()
        logger.info("Redis connection closed")
        _redis_pool = None


def get_redis():
    return _redis_pool
