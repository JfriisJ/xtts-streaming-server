import logging
import redis
import base64
from audio_service.utils.audio_utils import generate_audio  # Utility to handle audio generation logic

logger = logging.getLogger("AudioTaskHandler")

# Assuming Redis is initialized elsewhere and imported as `redis_client`
redis_client = redis.StrictRedis(host="localhost", port=6379, decode_responses=True, db=0)

TTS_QUEUE = "audio_tts"

def process_audio_task(task):
    """
    Process an audio task and handle the generation process.
    :param task: dict containing task details (text, language, embeddings, etc.)
    """
    try:
        logger.info(f"Processing audio task: {task}")

        # Validate task structure
        required_keys = ["task_id", "text", "language", "speaker_embedding", "gpt_cond_latent"]
        if not all(key in task for key in required_keys):
            logger.error("Task is missing required keys.")
            return

        # Extract task data
        task_id = task["task_id"]
        text = task["text"]
        language = task["language"]
        speaker_embedding = task["speaker_embedding"]
        gpt_cond_latent = task["gpt_cond_latent"]

        # Generate audio
        audio_data = generate_audio(
            text=text,
            language=language,
            speaker_embedding=speaker_embedding,
            gpt_cond_latent=gpt_cond_latent
        )

        # Ensure audio generation was successful
        if not audio_data:
            logger.error(f"Failed to generate audio for task {task_id}.")
            return

        # Convert audio data to base64
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")

        # Prepare result
        result = {
            "task_id": task_id,
            "audio_base64": audio_base64
        }

        # Push result to Redis queue
        redis_client.rpush(TTS_QUEUE, result)
        logger.info(f"Successfully processed and stored result for task {task_id}.")

    except Exception as e:
        logger.error(f"Error processing audio task: {e}")
