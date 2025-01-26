import io
import re

from pydub import AudioSegment
from transformers import GPT2TokenizerFast

tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

from audio_service.services.audio_service import enqueue_tts_task
from audio_service.utils.logging_utils import setup_logger
from audio_service.utils.redis_utils import fetch_languages_and_speakers, update_status_in_redis, redis_client_db_result
from audio_service.utils.text_utils import split_text_into_tuples

logger = setup_logger(name="AudioUtils")

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

def split_text_into_chunks(text, max_chars=250, max_tokens=350):
    """
    Splits text into chunks based on character and token limits, breaking at sentence boundaries.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text)  # Split by sentence-ending punctuation
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        # Get the token count for the sentence
        sentence_tokens = len(tokenizer.encode(sentence, add_special_tokens=False))

        # If adding the sentence exceeds the limits, finalize the current chunk
        if len(current_chunk) + len(sentence) > max_chars or current_tokens + sentence_tokens > max_tokens:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""
                current_tokens = 0

        # If the sentence itself is too large, split it
        if len(sentence) > max_chars or sentence_tokens > max_tokens:
            sentence_parts = [sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)]
            for part in sentence_parts:
                part_tokens = len(tokenizer.encode(part, add_special_tokens=False))
                if len(current_chunk) + len(part) <= max_chars and current_tokens + part_tokens <= max_tokens:
                    current_chunk += part + " "
                    current_tokens += part_tokens
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = part + " "
                    current_tokens = part_tokens
        else:
            # Add the sentence to the current chunk
            current_chunk += sentence + " "
            current_tokens += sentence_tokens

    # Add the last chunk if it's not empty
    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks

def text_to_audio(task, content, heading, section_index):
    """
    Convert text into audio using TTS service. Each chunk is sent to the TTS service via a queue,
    including all information needed for downstream processing and tracking.
    """
    speaker_type = task.get("speaker_type")
    speaker = task.get("speaker")

    # Fetch speaker embeddings
    languages, speakers, cloned_speaker = fetch_languages_and_speakers()
    embeddings = (
        speakers.get(speaker)
        if speaker_type == "Studio"
        else cloned_speaker.get(speaker)
    )
    if not embeddings:
        logger.error(f"No embeddings found for speaker type '{speaker_type}' and speaker name: '{speaker}'")
        logger.error(f"Available speakers: {list(speakers.keys()) if speakers else 'None'}")
        return None

    # Split text into chunks
    chunks = split_text_into_chunks(content)
    total_chunks = len(chunks)  # Total number of chunks
    task_ids = []

    # Update the task status
    task["status"] = "TTS conversion"
    update_status_in_redis(task.get("job_id"), task["status"])

    # Queue each chunk for TTS conversion
    for idx, chunk in enumerate(chunks):
        enqueue_tts_task(task, section_index, idx, total_chunks, heading, chunk, speaker, speaker_type, embeddings, task_ids)

def concatenate_audios(task):
    """
    Combines multiple audio files from Redis into one, adding pauses between sentences,
    and saves the final audio to Redis.

    :param task: The task dictionary containing metadata.
    :param audio_chunks: List of audio chunks (in binary format).
    :param total_chunks: Total number of chunks expected for the task.
    :param section_index: Section index used to generate the Redis key.
    :param heading: Heading used to generate the Redis key.
    """
    job_id = task.get("job_id")
    audio_chunks = task.get("audio_chunks")
    total_chunks = task.get("total_chunks")
    section_index = task.get("section_index")
    heading = task.get("heading")
    output_format = task.get("output_format")
    book_title = task.get("book_title")

    # Ensure all chunks are received
    if len(audio_chunks) != total_chunks:
        logger.error(
            f"Incomplete audio chunks for section {section_index}, heading '{heading}'. "
            f"Expected {total_chunks}, but got {len(audio_chunks)}."
        )
        task["status"] = "error"
        update_status_in_redis(job_id, task["status"])
        return

    # Update the task status
    task["status"] = "Combining audio chunks"
    update_status_in_redis(task.get("job_id"), task["status"])

    pauses = {"sentence": 500, "heading": 1000}  # Default pauses in milliseconds

    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=pauses["sentence"])
    pause_between_heading_and_text = AudioSegment.silent(duration=pauses["heading"])

    # Combine audio chunks
    for idx, chunk in enumerate(audio_chunks):
        try:
            # Load audio from binary
            audio = AudioSegment.from_file(io.BytesIO(chunk), format=output_format)

            # Add pause and concatenate
            if idx == 0:
                combined += audio + pause_between_heading_and_text
            else:
                combined += pause_between_sentences + audio
        except Exception as e:
            logger.error(f"Error processing audio chunk {idx}: {e}")
            task["status"] = "error"
            update_status_in_redis(task.get("job_id"), task["status"])
            return

    # Remove trailing silence
    combined = combined[:-len(pause_between_sentences)]

    # Save concatenated audio to Redis
    redis_key = f"{book_title}:{section_index}:{heading}"
    output_buffer = io.BytesIO()
    combined.export(output_buffer, format=output_format)  # Export to buffer

    try:
        redis_client_db_result.set(redis_key, output_buffer.getvalue())  # Save to Redis
        task["status"] = "completed"
        update_status_in_redis(task.get("job_id"), task["status"])
        logger.info(f"Saved concatenated audio to Redis with key: {redis_key}")
    except Exception as e:
        logger.error(f"Error saving final audio to Redis for key {redis_key}: {e}")
        task["status"] = "error"
        update_status_in_redis(task.get("job_id"), task["status"])



