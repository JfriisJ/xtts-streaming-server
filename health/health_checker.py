import json
import logging
import redis
import os

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealthChecker")

# Redis configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
HEALTH_CHECK_CHANNEL = "health_check"
HEALTH_STATUS_CHANNEL = "health_status"
SERVICE_NAME = os.getenv("SERVICE_NAME", "audio_service")

# Redis client for health checks
redis_health_care = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=1)


def listen_for_health_checks():
    """
    Listen for health check requests and respond with the service's health status.
    """
    pubsub = redis_health_care.pubsub()
    pubsub.subscribe(HEALTH_CHECK_CHANNEL)
    logger.info(f"Subscribed to channel '{HEALTH_CHECK_CHANNEL}' for health checks.")

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
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON in health check message: {message['data']} - {e}")
                except Exception as e:
                    logger.error(f"Error processing health check: {e}")
    except KeyboardInterrupt:
        logger.info("Shutting down health check listener.")
    except Exception as e:
        logger.error(f"Unexpected error in health check listener: {e}")


if __name__ == "__main__":
    logger.info("Starting health check responder.")
    listen_for_health_checks()
