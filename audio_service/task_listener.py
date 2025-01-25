import json
import logging
from task_handlers.audio_task import process_audio_task
from task_handlers.speaker_task import process_speaker_task
from task_handlers.text_task import process_text_task

logger = logging.getLogger("TaskListener")


def listen_to_queues(redis_client, queues, stop_event):
    """Listen to multiple Redis queues and process tasks."""
    logger.info(f"Listening to queues: {queues}")
    while True:
        try:
            queue, task_data = redis_client.blpop(queues)
            task = json.loads(task_data)
            logger.info(f"Received task from {queue}: {task}")

            # Route task to appropriate handler
            if queue == "audio_tasks":
                process_audio_task(task) # Pass redis_client for Redis operations
            elif queue == "speaker_tasks":
                process_speaker_task(task, redis_client)  # Pass redis_client for Redis operations
            elif queue == "text_tasks":
                process_text_task(task)  # Pass redis_client for Redis operations
            else:
                logger.warning(f"Unhandled queue: {queue}")
        except Exception as e:
            logger.error(f"Error while processing task: {e}")

