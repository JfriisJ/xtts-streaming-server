
import redis
import json
import logging

from audio_service.config import REDIS_HOST, REDIS_PORT, REDIS_DB_DATA_MODEL, REDIS_DB_STATUS
from audio_service.utils.logging_utils import setup_logger

# Logging setup
logger = setup_logger(name="RedisUtils")


def get_redis_client(host: str = "localhost", port: int = 6379, db: int = 0,decode_responses=False) -> redis.StrictRedis:
    """
    Opretter og returnerer en Redis-forbindelse.

    :param host: Redis-serverens værtsnavn.
    :param port: Redis-serverens port.
    :param db: Redis-databasenummer.
    :return: Redis-forbindelsesobjekt.
    """
    try:
        client = redis.StrictRedis(host=host, port=port, decode_responses=decode_responses, db=db)
        logger.info(f"Connected to Redis at {host}:{port}, DB: {db}")
        return client
    except redis.ConnectionError as e:
        logger.error(f"Failed to connect to Redis: {e}")
        raise


def push_to_queue(redis_client, queue_name, task):
    """
    Push a task to a Redis queue.
    """
    try:
        redis_client.rpush(queue_name, json.dumps(task))
        logger.info(f"Task added to queue {queue_name}: {task['task_id']}")
    except Exception as e:
        logger.error(f"Error adding task to queue {queue_name}: {e}")

def pop_from_queue(redis_client, queue_name):
    """
    Pop a task result from a Redis queue.
    """
    try:
        result_data = redis_client.blpop(queue_name, timeout=10)
        if result_data:
            return json.loads(result_data[1])
    except Exception as e:
        logger.error(f"Error popping task from queue {queue_name}: {e}")
    return None


def save_to_redis(redis_client: redis.StrictRedis, key: str, value: dict, expire: int = None) -> None:
    """
    Gemmer data i Redis med en valgfri udløbstid.

    :param redis_client: Redis-forbindelsesobjekt.
    :param key: Nøglen til værdien.
    :param value: Data som dictionary.
    :param expire: Udløbstid i sekunder (valgfri).
    """
    try:
        redis_client.set(key, json.dumps(value))
        if expire:
            redis_client.expire(key, expire)
        logger.info(f"Data saved to Redis under key '{key}'.")
    except redis.RedisError as e:
        logger.error(f"Failed to save data to Redis under key '{key}': {e}")

def fetch_from_redis(redis_client: redis.StrictRedis, key: str) -> dict:
    """
    Henter data fra Redis.

    :param redis_client: Redis-forbindelsesobjekt.
    :param key: Nøglen til dataen.
    :return: Data som dictionary, eller None hvis nøglen ikke findes.
    """
    try:
        value = redis_client.get(key)
        return json.loads(value) if value else None
    except redis.RedisError as e:
        logger.error(f"Failed to fetch data from Redis for key '{key}': {e}")
        return None


def publish_message(redis_client: redis.StrictRedis, channel: str, message: dict) -> None:
    """
    Udsender en besked til en Redis-kanal.

    :param redis_client: Redis-forbindelsesobjekt.
    :param channel: Navnet på kanalen.
    :param message: Beskeden som dictionary.
    """
    try:
        redis_client.publish(channel, json.dumps(message))
        logger.info(f"Message published to channel '{channel}': {message}")
    except redis.RedisError as e:
        logger.error(f"Failed to publish message to channel '{channel}': {e}")

def subscribe_to_channel(redis_client: redis.StrictRedis, channel: str):
    """
    Lytter til beskeder på en Redis-kanal.

    :param redis_client: Redis-forbindelsesobjekt.
    :param channel: Navnet på kanalen.
    :yield: Beskeder modtaget på kanalen.
    """
    try:
        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel)
        logger.info(f"Subscribed to channel '{channel}'.")

        for message in pubsub.listen():
            if message["type"] == "message":
                yield json.loads(message["data"])
    except redis.RedisError as e:
        logger.error(f"Failed to subscribe to channel '{channel}': {e}")


def key_exists(redis_client: redis.StrictRedis, key: str) -> bool:
    """
    Kontrollerer om en nøgle findes i Redis.

    :param redis_client: Redis-forbindelsesobjekt.
    :param key: Nøglen, der skal kontrolleres.
    :return: `True` hvis nøglen findes, ellers `False`.
    """
    try:
        return redis_client.exists(key) > 0
    except redis.RedisError as e:
        logger.error(f"Failed to check if key exists in Redis: {e}")
        return False


def get_all_keys(redis_client: redis.StrictRedis, pattern: str = "*") -> list:
    """
    Henter alle nøgler fra Redis baseret på et mønster.

    :param redis_client: Redis-forbindelsesobjekt.
    :param pattern: Mønster til at matche nøgler (default er "*", der matcher alle).
    :return: Liste over nøgler, der matcher mønsteret.
    """
    try:
        keys = redis_client.keys(pattern)
        decoded_keys = [key.decode('utf-8') for key in keys]  # Decodér bytes til str
        return decoded_keys
    except redis.RedisError as e:
        logger.error(f"Failed to get keys with pattern '{pattern}': {e}")
        return []


def fetch_languages_and_speakers():
    """Fetch languages and speakers from Redis."""
    try:
        redis_client = get_redis_client(REDIS_HOST, REDIS_PORT, REDIS_DB_DATA_MODEL)
        languages = redis_client.get("data:xtts:languages")
        studio_speakers = redis_client.get("data:xtts:studio_speakers")
        cloned_speakers = redis_client.get("data:xtts:cloned_speakers")

        return (
            json.loads(languages) if languages else [],
            json.loads(studio_speakers) if studio_speakers else {},
            json.loads(cloned_speakers) if cloned_speakers else {},
        )
    except Exception as e:
        logger.error(f"Error fetching languages and speakers: {e}")
        return [], {}, {}


def update_status_in_redis(job_id, status):
    """
    Updates the status of a job in Redis.

    Args:
        redis_client: Redis client instance.
        job_id (str): The ID of the job.
        status (str): The status to be updated (e.g., 'processing', 'converting').

    Returns:
        bool: True if the update was successful, False otherwise.
    """
    redis_client = get_redis_client(REDIS_HOST, REDIS_PORT, REDIS_DB_STATUS)
    if not job_id or not status:
        logger.error("Job ID and status are required.")
        return False

    redis_key = f"{job_id}:status"
    try:
        redis_client.set(redis_key, status)
        logger.info(f"Updated Redis: {redis_key} -> {status}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Redis for {redis_key}: {e}")
        return False
