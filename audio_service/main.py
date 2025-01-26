import threading
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
    from core.mq import listen_to_queues
    from audio_service.services.health_service import listen_for_health_checks
    from audio_service.config import  TASK_QUEUES
    from audio_service.utils.redis_utils import redis_client_db_task

    """
    Main entry point for the TTS service.
    """
    logger.info("Starting TTS Service...")

    # Signal handling for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Start health check listener in a separate thread
    health_check_thread = threading.Thread(target=listen_for_health_checks, daemon=True)
    health_check_thread.start()
    logger.info("Health check listener started.")

    # Start queue listener for task processing
    try:
        listen_to_queues(redis_client_db_task, TASK_QUEUES)
    except Exception as e:
        logger.error(f"Error while listening to queues: {e}")

    finally:
        logger.info("TTS Service stopped.")


if __name__ == "__main__":
    main()
