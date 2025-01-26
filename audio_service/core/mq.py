import json
from typing import List

import redis

from audio_service.core.task_handlers import process_audio_task, process_speaker_task, process_text_task, \
    process_tts_result
from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.task_utils import validate_task


logger = setup_logger(name="MQ")

# Push task to Redis queue
def push_to_queue(redis_client, task, queue_name):
    try:
        if not validate_task(task):
            logger.error(f"Task validation failed. Task not added to queue: {task}")
            return
        task_json = json.dumps(task)
        redis_client.rpush(queue_name, task_json)
        logger.info(f"Task added to queue {queue_name}: {task_json}")
    except redis.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")

# Batch task validation and push to queue
def validate_and_push_tasks(redis_client, tasks, queue_name):
    for task in tasks:
        if validate_task(task):
            push_to_queue(redis_client, task, queue_name)
        else:
            logger.warning(f"Task skipped due to validation failure: {task}")

# Unified Task Listener
def listen_to_queues(redis_client, queues: List[str]):
    """Listen to multiple Redis queues and process tasks."""
    logger.info(f"Listening to queues: {queues}")
    while True:
        try:
            queue, task_data = redis_client.blpop(queues)
            task = json.loads(task_data)
            logger.info(f"Received task from {queue}: {task}")

            # Route task to appropriate handler
            if queue == "audio_tasks":
                process_audio_task(task)
            elif queue == "speaker_tasks":
                process_speaker_task(task)
            elif queue == "text_tasks":
                process_text_task(task)
            elif queue == "tts_results":
                process_tts_result(task)
            else:
                logger.warning(f"Unhandled queue: {queue}")
        except Exception as e:
            logger.error(f"Error while processing task: {e}")