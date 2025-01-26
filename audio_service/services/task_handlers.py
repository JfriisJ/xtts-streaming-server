import time

from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import update_status_in_redis
from audio_service.utils.task_utils import validate_task

logger = setup_logger(name="TaskHandlers")


# Collect audio tasks from the audio_tasks queue and process them to generate audio
def process_audio_task(task):
    from audio_service.services.audio_utils import generate_audio
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
    from audio_service.services.audio_utils import concatenate_audios

    logger.info(f"Processing TTS result: {task}")

    if not validate_task(task):
        task["status"] = "tts result validation failure"
        update_status_in_redis(task.get("job_id"), task["status"])
        logger.warning(f"Invalid TTS result: {task}")
        return

    job_id = task.get("job_id")
    section_index = task.get("section_index")
    total_chunks = task.get("total_chunks")
    start_time = time.time()
    timeout = 300  # 5 minutes

    # Track received chunks
    received_chunks = {}

    # Wait until all chunks are received or timeout
    while len(received_chunks) < total_chunks:
        if time.time() - start_time > timeout:
            logger.error(
                f"Timeout reached while waiting for audio chunks for job {job_id}, section {section_index}. "
                f"Expected {total_chunks}, but got {len(received_chunks)}."
            )
            task["status"] = "timeout"
            update_status_in_redis(job_id, task["status"])
            return

    # Check if all chunks are received
    if len(received_chunks) != total_chunks:
        logger.error(
            f"Incomplete audio chunks for job {job_id}, section {section_index}. "
            f"Expected {total_chunks}, but got {len(received_chunks)}."
        )
        task["status"] = "error"
        update_status_in_redis(job_id, task["status"])
        return

    # Prepare task with collected chunks
    task["audio_chunks"] = [received_chunks[idx] for idx in range(total_chunks)]

    # Update status to concatenating
    task["status"] = "concatenating"
    update_status_in_redis(job_id, task["status"])

    # Pass task to concatenate and save audio
    try:
        concatenate_audios(task)
        task["status"] = "completed"
        update_status_in_redis(job_id, task["status"])

        # Remove processed chunks from queue or tracking
        for idx in range(total_chunks):
            del received_chunks[idx]  # Adjust if tracking is done elsewhere
        logger.info(f"Processed and cleared all chunks for job {job_id}, section {section_index}.")
    except Exception as e:
        logger.error(f"Error during audio concatenation for job {job_id}: {e}")
        task["status"] = "error"
        update_status_in_redis(job_id, task["status"])
