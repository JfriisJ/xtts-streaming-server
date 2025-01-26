import base64
import uuid

from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import push_to_queue, redis_client_db_task, update_status_in_redis
from audio_service.utils.task_utils import validate_task

logger = setup_logger(name="AudioUtils")

def process_clone_speaker_task(task: dict):
    """
    Handles cloning a speaker by enqueuing the task into a message queue.

    :param task: A dictionary containing details about the cloning task.
    """
    try:
        # Extract required fields
        speaker_name = task.get("SpeakerName")
        audio_base64 = task.get("AudioFileBase64")

        if not speaker_name or not audio_base64:
            logger.error("Invalid task: Missing 'SpeakerName' or 'AudioFileBase64'.")
            return

        # Decode the audio base64 to ensure it's valid
        try:
            audio_binary = base64.b64decode(audio_base64)
        except base64.binascii.Error:
            logger.error(f"Invalid Base64 encoding for speaker '{speaker_name}'.")
            return

        # Generate a unique task ID
        task_id = str(uuid.uuid4())

        # Prepare the message payload
        queue_task = {
            "task_id": task_id,
            "action": "clone_speaker",
            "speaker_name": speaker_name,
            "audio_binary": audio_base64,  # Keeping it Base64 encoded to simplify message transport
        }

        # Enqueue the task into the 'speaker_tasks' queue
        push_to_queue(redis_client_db_task,"speaker_tasks", queue_task)

        logger.info(f"Speaker cloning task for '{speaker_name}' enqueued successfully with Task ID: {task_id}.")

    except Exception as e:
        logger.error(f"Error processing speaker cloning task: {e}")


def enqueue_tts_task(task, section_index, idx, total_chunks, heading, chunk, speaker, speaker_type, embeddings, task_ids):
    """
    Enqueue a TTS task into the audio_tasks queue and wait for its result.

    :param text: The text to be converted to speech.
    :param language: The language of the text.
    :param speaker_embedding: The embedding vector for the speaker.
    :param gpt_cond_latent: The latent vector for GPT condition.
    """
    try:
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        tts_task = {
            "task_id": task_id,
            "job_id": task.get("job_id"),
            "section_index": section_index,
            "chunk_index": idx,
            "total_chunks": total_chunks,  # Include total chunks in the task
            "heading": heading,
            "text": chunk,
            "language": task.get("language"),
            "speaker": speaker,
            "speaker_type": speaker_type,
            "speaker_embedding": embeddings["speaker_embedding"],
            "gpt_cond_latent": embeddings["gpt_cond_latent"],
            "cache_key": f"cache:{task.get('book_title')}:{section_index}:{idx}",
            "book_title": task.get("book_title"),
            "timestamp": task.get("timestamp"),
        }
        if validate_task(tts_task):
            push_to_queue(redis_client_db_task, tts_task, "generate_tts_tasks")
            task_ids.append(task_id)
            logger.info(
            f"Task {task_id} for chunk {idx + 1}/{total_chunks} of section '{heading}' "
            f"(section_index: {section_index}) queued successfully."
            )
        else:
            logger.warning(f"Task skipped due to validation failure: {tts_task}")
            # Update the task status
        task["status"] = "awaiting audio chunks"
        update_status_in_redis(task.get("job_id"), task["status"])
    except Exception as e:
        logger.error(f"Error enqueuing TTS task: {e}")
        # Update the task status
        task["status"] = "failed"
        update_status_in_redis(task.get("job_id"), task["status"])
        return False
