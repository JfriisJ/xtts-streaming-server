import io
import logging
import base64
import uuid

from pydub import AudioSegment

from audio_service.config import REDIS_HOST, REDIS_PORT, REDIS_DB_TASK, REDIS_DB_RESULT
from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import fetch_languages_and_speakers, pop_from_queue, get_redis_client, \
    update_status_in_redis
from audio_service.utils.text_utils import split_text_into_chunks, split_text_into_tuples

logger = setup_logger(name="AudioUtils")

redis_task_queue = get_redis_client(REDIS_HOST, REDIS_PORT, REDIS_DB_TASK)
redis_result_db = get_redis_client(REDIS_HOST, REDIS_PORT, REDIS_DB_RESULT)

def generate_audio(task):
    """
    Splits the book into tuples and generates audio for each section in the specified format.
    """
    selected_title = task["selected_title"]
    sections = task["sections"]
    book_title = task["book_title"]
    logger.info(f"Starting audio generation for the selected section: '{selected_title}'")

    def find_selected_section(sections, selected_title):
        """
        Recursively find the section or subsection matching the selected title.
        """
        for section in sections:
            if section.get("Heading") == selected_title:
                return [section]  # Wrap in a list for compatibility with split_text_into_tuples
            if "Subsections" in section:
                result = find_selected_section(section["Subsections"], selected_title)
                if result:
                    return result
        return None

    if selected_title == book_title:
        # Generate audio for the entire book
        tuples = split_text_into_tuples(sections)
    else:
        # Find the matching section or subsection
        selected_section = find_selected_section(sections, selected_title)
        if not selected_section:
            logger.warning(f"No matching section found for '{selected_title}'")
            return None

        # Generate audio for the selected section or subsection
        tuples = split_text_into_tuples(selected_section)

    if not tuples:
        logger.warning("No sections to process for audio generation.")
        return None

    generate_audio_from_tuples(tuples, task)


def generate_audio_from_tuples(tuples, task):
    """
    Generate audio for each tuple in the provided list.
    """
    logger.info("Starting audio generation from tuples.")

    for section_index, section_name, content in tuples:
        if not content.strip():
            logger.warning(f"Section '{section_name}' (Index: {section_index}) has no content.")
            content = f"(No content for section '{section_name}')"

        try:
            logger.info(f"Generating audio for section '{section_name}' (Index: {section_index})")
            text_to_audio(task, content=content, heading=section_name, section_index=section_index,)
        except Exception as e:
            logger.error(f"Error generating audio for section '{section_name}' (Index: {section_index}): {e}")



def text_to_audio(task, content, heading, section_index):
    """
    Convert text into audio using TTS service. Each chunk is sent to the TTS service via a queue, and results are
    recombined after conversion.
    """
    from audio_service.core.mq import push_to_queue
    speaker_type = task.get("speaker_type")
    # Fetch speaker embeddings
    languages, speakers, cloned_speaker = fetch_languages_and_speakers()
    embeddings = (
        speakers.get(task.get("speaker_name_studio"))
        if speaker_type == "Studio"
        else cloned_speaker.get(task.get("speaker_name_custom"))
    )
    if not embeddings:
        logger.error(f"No embeddings found for speaker type '{speaker_type}' and speaker name.")
        return None

    # Split text into chunks
    chunks = split_text_into_chunks(content)
    task_ids = []

    # update the task status
    task["status"] = "TTS conversion"
    update_status_in_redis(task.get("job_id"), task["status"])

    # Queue each chunk for TTS conversion
    for idx, chunk in enumerate(chunks):
        task_id = str(uuid.uuid4())
        tts_task = {
            "task_id": task_id,
            "job_id": task.get("job_id"),
            "text": chunk,
            "language": task.get("language"),
            "speaker_embedding": embeddings["speaker_embedding"],
            "gpt_cond_latent": embeddings["gpt_cond_latent"],
            "cache_key": f"cache:{task.get("book_title")}:{section_index}:{idx}"
        }
        push_to_queue(redis_task_queue, tts_task, "tts_conversion_queue")
        task_ids.append(task_id)
        logger.info(f"Task {task_id} for chunk {idx} queued successfully.")

    # Wait for results and collect them
    audio_chunks = []
    for task_id in task_ids:
        try:
            while True:
                result = pop_from_queue(redis_task_queue, "tts_result_queue")
                if result and result["task_id"] == task_id:
                    audio_chunks.append(base64.b64decode(result["audio_base64"]))
                    logger.info(f"Received audio for task {task_id}")
                    break
        except Exception as e:
            logger.error(f"Error while waiting for result of task {task_id}: {e}")


    # Combine chunks into a single audio file
    if audio_chunks:
        concatenate_audios(task, audio_chunks, section_index, heading)
    else:
        logger.warning(f"No audio chunks were generated for heading: '{heading}'")


def concatenate_audios(task, audio_chunks, section_index, heading, pauses=None):
    """
    Combines multiple audio files from Redis into one, adding pauses between sentences, and saves the final audio to Redis.

    :param redis_keys: List of Redis keys pointing to cached audio chunks.
    :param book_title: Title of the book, used to generate the Redis key.
    :param section_index: Section index used to generate the Redis key.
    :param heading: Heading used to generate the Redis key.
    :param pauses: Dictionary specifying pause durations in milliseconds, e.g., {"sentence": 500, "heading": 1000}.
    """
    # update the task status
    task["status"] = "Combining audio chunks"
    update_status_in_redis(task.get("job_id"), task["status"])

    output_format = task.get("output_format")
    book_title = task.get("book_title")
    if pauses is None:
        pauses = {"sentence": 500, "heading": 1000}  # Default pauses in milliseconds

    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=pauses["sentence"])
    pause_between_heading_and_text = AudioSegment.silent(duration=pauses["heading"])

    for idx, chunk in enumerate(audio_chunks):

        # Load audio from binary
        audio = AudioSegment.from_file(io.BytesIO(chunk), format=output_format)

        # Add pause and concatenate
        if idx == 0:
            combined += audio + pause_between_heading_and_text
        else:
            combined += pause_between_sentences + audio

    # Remove trailing silence
    combined = combined[:-len(pause_between_sentences)]

    # Save concatenated audio to Redis
    redis_key = f"{book_title}:{section_index}:{heading}"
    output_buffer = io.BytesIO()
    combined.export(output_buffer, format="wav")  # Export to buffer
    redis_result_db.set(redis_key, output_buffer.getvalue())  # Save to Redis
    # update the task status
    task["status"] = "completed"
    update_status_in_redis(task.get("job_id"), task["status"])

    logger.info(f"Saved concatenated audio to Redis with key: {redis_key}")



