from audio_service.config import REDIS_HOST, REDIS_PORT, REDIS_DB_STATUS
from audio_service.services.audio_service import process_clone_speaker_task
from audio_service.utils.audio_utils import generate_audio
from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import get_redis_client, update_status_in_redis
from audio_service.utils.task_utils import validate_task

logger = setup_logger(name="TaskHandlers")

# Collect audio tasks from the audio_tasks queue and process them to generate audio
def process_audio_task(task):
    logger.info(f"Processing audio task: {task}")

    # Validate the task
    if not validate_task(task):
        task["status"] = "Validation failure"
        update_status_in_redis(task.get("job_id"), task["status"])
        logger.warning(f"Invalid task: {task}")
        return

    # update the task status
    task["status"] = "formatting"
    update_status_in_redis(task.get("job_id"), task["status"])

    # Continue to process the task
    generate_audio(task)

def process_speaker_task(task):
    logger.info(f"Processing speaker task: {task}")
    if task.get("Type") == "clone_speaker":
        process_clone_speaker_task(task)
    else:
        logger.warning(f"Unhandled speaker task type: {task.get('Type')}")

def process_text_task(task):
    logger.info(f"Processing text task: {task}")
    # Add specific text task logic here