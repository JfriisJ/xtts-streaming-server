import time
import redis
import json
import logging
import threading
import os

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Monitor")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
HEALTH_STATUS_CHANNEL = "health_status"
HEALTH_TIMEOUT = 10  # Time (seconds) to consider a service disconnected if no update

# Redis client for monitoring
redis_health_care = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=1)

# Track last update timestamps for services
last_updates = {}


def monitor_health_status():
    """
    Monitor health status updates from services.
    """
    pubsub = redis_health_care.pubsub()
    pubsub.subscribe(HEALTH_STATUS_CHANNEL)
    logger.info(f"Subscribed to channel '{HEALTH_STATUS_CHANNEL}' for health status monitoring.")

    try:
        for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    health_update = json.loads(message["data"])
                    service_name = health_update["service"]
                    status = health_update["status"]

                    # Update the last known time for the service
                    last_updates[service_name] = time.time()
                    redis_health_care.set(f"status:{service_name}", status)
                    logger.info(f"Updated health status: {service_name} -> {status}")
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in health status message: {message['data']} - {e}")
                except Exception as e:
                    logger.error(f"Error processing health status: {e}")
    except KeyboardInterrupt:
        logger.info("Shutting down health status monitor.")
    except Exception as e:
        logger.error(f"Unexpected error in health status monitor: {e}")


def check_disconnected_services():
    """
    Periodically check for services that haven't updated their status within the timeout period.
    """
    while True:
        current_time = time.time()
        for service, last_update in list(last_updates.items()):
            if current_time - last_update > HEALTH_TIMEOUT:
                redis_health_care.set(f"status:{service}", "disconnected")
                logger.warning(f"Service '{service}' is marked as disconnected.")
            else:
                redis_health_care.set(f"status:{service}", "connected")
        time.sleep(HEALTH_TIMEOUT)


if __name__ == "__main__":
    logger.info("Starting health monitor.")

    # Run health monitoring and periodic checks in separate threads
    threading.Thread(target=monitor_health_status, daemon=True).start()
    threading.Thread(target=check_disconnected_services, daemon=True).start()

    # Keep the main thread alive
    while True:
        time.sleep(1)
