import redis
import logging
from config import REDIS_HOST, REDIS_PORT, REDIS_DB_TTS

logger = logging.getLogger("RedisUtils")

def initialize_redis(host, port, db):
    retries = 5
    while retries > 0:
        try:
            return redis.StrictRedis(host=host, port=port, decode_responses=False, db=db)
        except redis.ConnectionError as e:
            retries -= 1
            logger.warning(f"Redis connection failed. Retrying... ({5 - retries}/5)")
    raise ConnectionError("Failed to connect to Redis after 5 attempts.")

redis_client = initialize_redis(REDIS_HOST, REDIS_PORT, 0)
redis_health_care = initialize_redis(REDIS_HOST, REDIS_PORT, 1)
redis_tts_client = initialize_redis(REDIS_HOST, REDIS_PORT, REDIS_DB_TTS)

from config import REDIS_HOST, REDIS_PORT

def get_redis_client(db: int):
    return redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=db)

def fetch_key(redis_client, key):
    return redis_client.get(key)

def set_key(redis_client, key, value):
    redis_client.set(key, value)
