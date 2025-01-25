import logging
import re
import io
from pydub import AudioSegment
from typing import List, Dict
from transformers import GPT2TokenizerFast

from audio_service.redis_utils import redis_client

# Initialize the tokenizer
tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

# Setup logger
logger = logging.getLogger("AudioUtils")

def aggregate_section_with_subsections(section: Dict, depth: int = 1) -> str:
    """
    Aggregate content of a section and its subsections, allowing up to 5 levels.
    """
    if depth > 5:
        return ""  # Ignore deeper levels

    heading_marker = "#" * depth  # Use up to 5 # for heading markers
    heading = section.get("Heading", "").strip()
    content = section.get("Content", "")

    if isinstance(content, list):
        content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
    elif isinstance(content, str):
        content = content.strip()
    else:
        content = ""

    aggregated_content = f"{heading_marker} {heading}\n\n{content}"

    for subsection in section.get("Subsections", []):
        aggregated_content += "\n\n" + aggregate_section_with_subsections(subsection, depth + 1)

    return aggregated_content


def split_text_into_tuples(sections: List[Dict]) -> List[tuple]:
    """
    Splits the text into tuples of (index, section_name, content),
    ensuring a maximum depth of 5 levels in the hierarchy.
    """
    tuples = []
    section_counts = {}

    def process_section(section: Dict, level: int = 1, index_prefix: str = "1"):
        """
        Recursively process sections and limit hierarchy to 5 levels.
        """
        if level > 5:  # Ignore levels deeper than 5
            return

        if index_prefix not in section_counts:
            section_counts[index_prefix] = 0
        section_counts[index_prefix] += 1

        index_parts = index_prefix.split(".")
        if len(index_parts) < level:
            index_parts.append("0")
        index_parts[level - 1] = str(section_counts[index_prefix])
        while len(index_parts) < 5:
            index_parts.append("0")

        current_index = ".".join(index_parts[:5])
        heading = section.get("Heading", "").strip()
        content = section.get("Content", "")

        if isinstance(content, list):
            content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
        elif isinstance(content, str):
            content = content.strip()
        else:
            content = ""

        combined_content = f"{heading}\n\n{content}"
        tuples.append((current_index, heading, combined_content))

        for subsection in section.get("Subsections", []):
            process_section(subsection, level + 1, current_index)

    for section in sections:
        process_section(section)

    return tuples


def split_text_into_chunks(text: str, max_chars: int = 250, max_tokens: int = 350) -> List[str]:
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


def concatenate_audios(redis_keys: List[str], output_format: str = "wav", pauses: Dict[str, int] = None) -> bytes:
    """
    Combines multiple audio files into one, adding pauses between sentences.
    """
    if pauses is None:
        pauses = {"sentence": 500, "heading": 1000}  # Default pauses in milliseconds

    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=pauses["sentence"])
    pause_between_heading_and_text = AudioSegment.silent(duration=pauses["heading"])

    for idx, redis_key in enumerate(redis_keys):
        # Fetch audio from Redis (mocked for utility)
        audio_binary = redis_client.get(redis_key)
        if not audio_binary:
            logger.error(f"Audio chunk not found for key: {redis_key}")
            continue

        audio = AudioSegment.from_file(io.BytesIO(audio_binary), format=output_format)

        if idx == 0:
            combined += audio + pause_between_heading_and_text
        else:
            combined += pause_between_sentences + audio

    return combined.raw_data




def generate_audio(task, tts_service, output_format="wav"):
    """
    Generates audio from text and metadata in the task.

    Args:
        task (dict): The task containing text, language, speaker details, etc.
        tts_service (object): A TTS service object or function to convert text to audio.
        output_format (str): The desired output audio format (e.g., "wav", "mp3").

    Returns:
        dict: A result dictionary containing the audio data in base64 and metadata.
    """
    try:
        text = task.get("text")
        language = task.get("language", "en")
        speaker_embedding = task.get("speaker_embedding")
        gpt_cond_latent = task.get("gpt_cond_latent")
        task_id = task.get("task_id")

        if not text or not task_id:
            raise ValueError("Task must contain 'text' and 'task_id'.")

        logger.info(f"Processing task {task_id} with language {language}.")

        # Split text into manageable chunks
        text_chunks = split_text_into_chunks(text)

        audio_chunks = []
        for idx, chunk in enumerate(text_chunks):
            logger.debug(f"Generating audio for chunk {idx + 1}/{len(text_chunks)}")
            audio_data = tts_service(
                text=chunk,
                language=language,
                speaker_embedding=speaker_embedding,
                gpt_cond_latent=gpt_cond_latent,
                output_format=output_format,
            )
            if audio_data:
                audio_chunks.append(audio_data)
            else:
                logger.warning(f"Audio generation failed for chunk {idx + 1}.")

        if not audio_chunks:
            logger.error(f"Audio generation failed for task {task_id}.")
            return {"task_id": task_id, "status": "failed", "audio": None}

        # Combine audio chunks if needed
        combined_audio = combine_audio_chunks(audio_chunks, output_format=output_format)

        logger.info(f"Audio generated successfully for task {task_id}.")
        return {"task_id": task_id, "status": "success", "audio": combined_audio}

    except Exception as e:
        logger.error(f"Error generating audio for task {task.get('task_id', 'unknown')}: {e}")
        return {"task_id": task.get("task_id", "unknown"), "status": "failed", "audio": None}


def combine_audio_chunks(chunks, output_format="wav"):
    """
    Combines multiple audio chunks into a single audio file.

    Args:
        chunks (list): List of audio data (binary or base64-encoded).
        output_format (str): The desired output audio format.

    Returns:
        bytes: The combined audio file data.
    """
    from pydub import AudioSegment
    import io

    combined_audio = AudioSegment.empty()
    for idx, chunk in enumerate(chunks):
        try:
            audio_segment = AudioSegment.from_file(io.BytesIO(chunk), format=output_format)
            combined_audio += audio_segment
        except Exception as e:
            logger.error(f"Error combining chunk {idx + 1}: {e}")
            continue

    # Export the combined audio to bytes
    audio_buffer = io.BytesIO()
    combined_audio.export(audio_buffer, format=output_format)
    audio_buffer.seek(0)

    return audio_buffer.getvalue()


def clean_filename(filename: str) -> str:
    """
    Cleans the filename by removing or replacing invalid characters.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()
