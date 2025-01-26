import logging
import base64
import uuid

from audio_service.config import REDIS_HOST, REDIS_PORT, REDIS_DB_TASK
from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import push_to_queue, get_redis_client

logger = setup_logger(name="AudioUtils")

redis_task_queue = get_redis_client(REDIS_HOST, REDIS_PORT, REDIS_DB_TASK)

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
        push_to_queue(redis_task_queue, "speaker_tasks", queue_task)

        logger.info(f"Speaker cloning task for '{speaker_name}' enqueued successfully with Task ID: {task_id}.")

    except Exception as e:
        logger.error(f"Error processing speaker cloning task: {e}")


def enqueue_tts_task(text: str, language: str, speaker_embedding: list, gpt_cond_latent: list):
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

        # Create the task payload
        task = {
            "task_id": task_id,
            "text": text,
            "language": language,
            "speaker_embedding": speaker_embedding,
            "gpt_cond_latent": gpt_cond_latent,
        }

        # Enqueue the task
        push_to_queue(redis_task_queue, "audio_tasks", task)
        logger.info(f"TTS task {task_id} added to the audio_tasks queue.")

    except Exception as e:
        logger.error(f"Error in enqueue_tts_task: {e}")
    return ""
