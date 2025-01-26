from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import update_status_in_redis
from audio_service.utils.task_utils import validate_task

logger = setup_logger(name="TaskHandlers")


# Collect audio tasks from the audio_tasks queue and process them to generate audio
def process_audio_task(task):
    from audio_service.utils.audio_utils import generate_audio
    logger.info(f"Processing audio task: {task}")

    # Validate the task
    if validate_task(task):
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
    from audio_service.services.audio_service import process_clone_speaker_task
    logger.info(f"Processing speaker task: {task}")
    if task.get("Type") == "clone_speaker":
        process_clone_speaker_task(task)
    else:
        logger.warning(f"Unhandled speaker task type: {task.get('Type')}")

def process_text_task(task):
    logger.info(f"Processing text task: {task}")
    # Add specific text task logic here

def process_tts_result(task):
    from audio_service.utils.audio_utils import concatenate_audios
    logger.info(f"Processing TTS result: {task}")
    if validate_task(task):
        task["status"] = "tts result validation failure"
        update_status_in_redis(task.get("job_id"), task["status"])
        logger.warning(f"Invalid TTS result: {task}")
        return

    task["status"] = "tts result processing"
    update_status_in_redis(task.get("job_id"), task["status"])
    concatenate_audios(task)
