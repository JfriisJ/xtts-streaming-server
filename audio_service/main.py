import json
import threading
import signal
import logging
import time
from task_listener import listen_to_queues
from redis_utils import redis_tts_client, redis_health_care
from config import TASK_QUEUES

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AudioService")

# Graceful shutdown signal handling
stop_event = threading.Event()

# Constants for health check
HEALTH_CHECK_CHANNEL = "health_check"
HEALTH_STATUS_CHANNEL = "health_status"
SERVICE_NAME = "audio_service"
HEALTH_INTERVAL = 5  # Publish health every 5 seconds

def listen_for_health_checks():
    """
    Listen for health check requests and respond with the service's health status.
    """
    pubsub = redis_health_care.pubsub()
    pubsub.subscribe(HEALTH_CHECK_CHANNEL)
    logger.info(f"Subscribed to {HEALTH_CHECK_CHANNEL} for health checks.")

    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    health_request = json.loads(message["data"])
                    if health_request.get("action") == "health_check":
                        # Respond with the service's health status
                        health_status = {"service": SERVICE_NAME, "status": "healthy"}
                        redis_health_care.publish(HEALTH_STATUS_CHANNEL, json.dumps(health_status))
                        logger.info(f"Responded to health check: {health_status}")
                except Exception as e:
                    logger.error(f"Error processing health check: {e}")
    except Exception as e:
        logger.error(f"Health check listener error: {e}")

def publish_health_status():
    """
    Periodically publish the service's health status.
    """
    while not stop_event.is_set():
        try:
            health_status = {"service": SERVICE_NAME, "status": "healthy", "timestamp": time.time()}
            redis_health_care.publish(HEALTH_STATUS_CHANNEL, json.dumps(health_status))
            logger.info(f"Published health status: {health_status}")
        except Exception as e:
            logger.error(f"Error publishing health status: {e}")
        time.sleep(HEALTH_INTERVAL)

def shutdown_handler(signum, frame):
    """
    Handle shutdown signals gracefully.
    """
    logger.info("Shutdown signal received. Stopping threads...")
    stop_event.set()

if __name__ == "__main__":
    logger.info("Starting Audio Service...")

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    try:
        # Start health check listener
        health_listener_thread = threading.Thread(target=listen_for_health_checks, daemon=True)
        health_listener_thread.start()

        # Start periodic health status publishing
        health_publisher_thread = threading.Thread(target=publish_health_status, daemon=True)
        health_publisher_thread.start()

        # Start task queue listener
        listen_to_queues(redis_tts_client, TASK_QUEUES, stop_event)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        stop_event.set()
        logger.info("Audio Service stopped.")
