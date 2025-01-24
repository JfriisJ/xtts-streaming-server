import json
import logging
import os
import time

import redis
import requests

# TTS_SERVER_API = os.getenv("TTS_SERVER_API", "http://localhost:4001")
# CONVERTER_API = os.getenv("CONVERTER_API", "http://localhost:5000")
#
#
# # Setup logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s - %(levelname)s - %(message)s",
#     handlers=[logging.StreamHandler()]
# )
# logger = logging.getLogger(__name__)
#
# def check_service_health():
#     services = {"Converter Service": CONVERTER_API, "Xtts Service": TTS_SERVER_API}
#     status = {}
#
#     for service_name, url in services.items():
#         try:
#             response = requests.get(f"{url}/health", timeout=10)
#             response.raise_for_status()
#             status[service_name] = {"status": "Connected"}
#         except requests.RequestException as e:
#             logger.error(f"{service_name} health check failed: {e}")
#             status[service_name] = {"status": "Disconnected", "error": str(e)}
#
#     return status

TTS_SERVER_API = os.getenv("TTS_SERVER_API", "http://localhost:4001")
CONVERTER_API = os.getenv("CONVERTER_API", "http://localhost:5000")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)
redis_status_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=0)


def check_service_health():
    """
    Check the health of the services and store the results in Redis.
    """
    services = {"Converter Service": CONVERTER_API, "TTS Service": TTS_SERVER_API}
    status = {}

    for service_name, url in services.items():
        try:
            response = requests.get(f"{url}/health", timeout=10)
            response.raise_for_status()
            health_status = {"status": "Connected"}
        except requests.RequestException as e:
            logger.error(f"{service_name} health check failed: {e}")
            health_status = {"status": "Disconnected", "error": str(e)}

        # Update Redis
        redis_status_client.set(f"health:{service_name}", json.dumps(health_status))
        status[service_name] = health_status

    return status

def fetch_and_store_data():
    """
    Fetch data from TTS_SERVER_API and store it in Redis.
    Includes studio speakers, languages, and other necessary configurations.
    """
    try:
        # Fetch speakers from /studio_speakers
        response = requests.get(f"{TTS_SERVER_API}/studio_speakers", timeout=10)
        response.raise_for_status()
        studio_speakers = response.json()
        redis_status_client.set("data:tts:studio_speakers", json.dumps(studio_speakers))
        logger.info("Updated studio speakers in Redis.")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch studio speakers from TTS_SERVER_API: {e}")

    try:
        # Fetch languages from /languages
        response = requests.get(f"{TTS_SERVER_API}/languages", timeout=10)
        response.raise_for_status()
        languages = response.json()
        redis_status_client.set("data:tts:languages", json.dumps(languages))
        logger.info("Updated languages in Redis.")
    except requests.RequestException as e:
        logger.error(f"Failed to fetch languages from TTS_SERVER_API: {e}")



if __name__ == "__main__":
    logger.info("Starting health and data service...")

    while True:
        try:
            # Perform health check
            health_status = check_service_health()
            logger.info(f"Health Status: {health_status}")

            # Fetch and store data
            fetch_and_store_data()

            # Sleep for 30 seconds
            time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Service interrupted by user. Exiting...")
            break
        except Exception as e:
            logger.error(f"An error occurred: {e}")