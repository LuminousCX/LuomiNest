from loguru import logger

_mqtt_client = None


async def init_mqtt():
    global _mqtt_client
    try:
        import aiomqtt

        from app.core.config import settings

        _mqtt_client = aiomqtt.Client(
            hostname=settings.MQTT_BROKER_HOST,
            port=settings.MQTT_BROKER_PORT,
            username=settings.MQTT_USERNAME or None,
            password=settings.MQTT_PASSWORD or None,
        )
        logger.info("MQTT client initialized")
    except Exception as e:
        logger.warning(f"MQTT initialization failed: {e}. Running without MQTT.")
        _mqtt_client = None


async def close_mqtt():
    global _mqtt_client
    if _mqtt_client:
        try:
            await _mqtt_client.__aexit__(None, None, None)
        except Exception:
            pass
        _mqtt_client = None
        logger.info("MQTT connection closed")


def get_mqtt_client():
    return _mqtt_client
