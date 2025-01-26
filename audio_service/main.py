import threading
import logging
import signal

from audio_service.utils.logging_utils import setup_logger

# Logging setup
logger = setup_logger(name="Main")


def shutdown_handler(signum, frame):
    """
    Graceful shutdown handler for signals like SIGINT and SIGTERM.
    """
    logger.info("Received shutdown signal. Stopping services...")
    exit(0)


def main():
    from utils.redis_utils import get_redis_client
    from core.mq import listen_to_queues
    from audio_service.services.health_service import listen_for_health_checks
    from audio_service.config import REDIS_HOST, REDIS_PORT, TASK_QUEUES, REDIS_DB_TASK, REDIS_DB_HEALTH

    """
    Main entry point for the TTS service.
    """
    logger.info("Starting TTS Service...")

    # Signal handling for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Initialize Redis client
    redis_client = get_redis_client(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_TASK, decode_responses=True)

    # Start health check listener in a separate thread
    health_check_thread = threading.Thread(target=listen_for_health_checks, daemon=True)
    health_check_thread.start()
    logger.info("Health check listener started.")

    # Start queue listener for task processing
    try:
        listen_to_queues(redis_client, TASK_QUEUES)
    except Exception as e:
        logger.error(f"Error while listening to queues: {e}")

    finally:
        logger.info("TTS Service stopped.")


if __name__ == "__main__":
    main()
