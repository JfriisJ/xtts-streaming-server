import base64
import io
import json
import logging
import os

import redis
from transformers import GPT2TokenizerFast
import re
from pydub import AudioSegment

import requests
import uuid
import time
from mq.producer import RedisProducer
from mq.consumer import RedisConsumer
from mq.mq import validate_task
from health_service import TTS_SERVER_API

# Initialize the tokenizer
tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=0)
except Exception as e:
    logger.error(f"Error connecting to Redis: {e}")

producer = RedisProducer()
consumer = RedisConsumer()


def consume_queue(queue_name="audio_format_tasks"):
    """
    Consume tasks from the Redis queue and process them.
    """
    logger.info(f"Listening to queue: {queue_name}")
    while True:
        try:
            # Blocking call to pop a task from the queue
            _, task_json = redis_client.blpop(queue_name)
            task = json.loads(task_json)

            # Validate task
            if not validate_task(task):
                logger.warning("Invalid task skipped.")
                continue

            logger.info(f"Processing task: {task}")

            # Process the task
            generate_audio_from_tuples(
                tuples=split_text_into_tuples(task["Sections"]),
                language=task["Language"],
                studio_speaker=task["Speaker"],
                speaker_type=task["SpeakerType"],
                output_format=task["AudioFormat"],
                book_title=task["Title"]
            )
        except Exception as e:
            logger.error(f"Error processing task: {e}")

def send_tts_job(text, language, speaker_embedding, gpt_cond_latent, queue_name="generate_audio"):
    """
    Send a TTS job to the MQ and wait for the result.
    """
    task_id = str(uuid.uuid4())
    task = {
        "task_id": task_id,
        "text": text,
        "language": language,
        "speaker_embedding": speaker_embedding,
        "gpt_cond_latent": gpt_cond_latent,
    }

    # Push task to `audio_tasks` queue
    producer.send_message(task, queue_name)
    print(f"Task {task_id} sent to queue")

    # Poll `audio_results` queue for the result
    while True:
        result = consumer.consume_message("audio_results")
        if result and result["task_id"] == task_id:
            print(f"Received result for task {task_id}")
            return result["audio_base64"]
        time.sleep(1)  # Avoid busy waiting


def consume_clone_speaker_task(queue_name="clone_speaker_tasks"):
    """
    Consume clone speaker tasks from the specified Redis queue.

    :param queue_name: Redis queue name to listen to for clone speaker tasks.
    """
    logger.info(f"Listening to '{queue_name}' queue...")
    while True:
        try:
            # Blocking call to retrieve a task from the queue
            _, task_json = redis_client.blpop(queue_name)
            task = json.loads(task_json)

            # Validate task
            if task.get("Type") != "clone_speaker":
                logger.warning(f"Invalid task type: {task.get('Type')}. Skipping.")
                continue

            # Decode the Base64-encoded audio file
            speaker_name = task["SpeakerName"]
            audio_base64 = task["AudioFileBase64"]
            audio_binary = base64.b64decode(audio_base64)

            # Process the clone speaker task
            logger.info(f"Processing clone speaker task for '{speaker_name}'")
            process_clone_speaker(audio_binary, speaker_name)

        except Exception as e:
            logger.error(f"Error processing clone speaker task: {e}")



def process_clone_speaker(audio_binary, clone_speaker_name):
    """
    Clone a speaker using the raw audio binary and store the embeddings in Redis.

    :param audio_binary: Raw audio data in binary format.
    :param clone_speaker_name: Name of the cloned speaker.
    """
    try:
        # Send the binary audio file to the cloning API
        files = {"wav_file": ("reference.wav", io.BytesIO(audio_binary))}
        response = requests.post(TTS_SERVER_API + "/clone_speaker", files=files)
        response.raise_for_status()

        # Get the embeddings from the API response
        embeddings = response.json()

        # Save embeddings to Redis
        redis_key = f"cloned_speaker:{clone_speaker_name}"
        redis_client.set(redis_key, json.dumps(embeddings))  # Store as JSON string
        logger.info(f"Saved cloned speaker embeddings to Redis with key: {redis_key}")

    except Exception as e:
        logger.error(f"Error cloning speaker '{clone_speaker_name}': {e}")


def fetch_languages_and_speakers():
    """
    Fetch languages and speakers data from Redis.
    """
    try:
        # Fetch languages and speakers from Redis
        languages = redis_client.get("data:tts:languages")
        studio_speakers = redis_client.get("data:tts:studio_speakers")
        cloned_speakers = redis_client.get("data:tts:cloned_speakers")

        # Parse the JSON data if present
        languages = json.loads(languages) if languages else []  # Expecting a list
        studio_speakers = json.loads(studio_speakers) if studio_speakers else {}  # Expecting a dictionary
        cloned_speakers = json.loads(cloned_speakers) if cloned_speakers else {}  # Expecting a dictionary
        return languages, studio_speakers, cloned_speakers
    except Exception as e:
        logger.error(f"Error fetching languages and speakers from Redis: {e}")
        return [], {}, {}  # Return empty list and dictionary as fallback



def aggregate_section_with_subsections(section, depth=1):
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


def split_text_into_tuples(sections):
    """
    Splits the text into tuples of (index, section_name, content),
    ensuring a maximum depth of 5 levels in the hierarchy.
    """
    tuples = []
    section_counts = {}

    def process_section(section, level=1, index_prefix="1"):
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


def generate_audio_from_tuples(
    tuples, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav", book_title="no-title"
):
    logger.info("Starting audio generation from tuples.")

    for section_index, section_name, content in tuples:
        if not content.strip():
            logger.warning(f"Section '{section_name}' (Index: {section_index}) has no content.")
            content = f"(No content for section '{section_name}')"

        try:
            logger.info(f"Generating audio for section '{section_name}' (Index: {section_index})")
            text_to_audio(
                text=content,
                heading=section_name,
                section_index=section_index,
                lang=language,
                speaker_type=speaker_type,
                speaker_name_studio=studio_speaker,
                output_format=output_format,
                book_title=book_title,
            )
        except Exception as e:
            logger.error(f"Error generating audio for section '{section_name}' (Index: {section_index}): {e}")


def clear_cache(keys):
    """
    Delete cached keys from Redis.
    """
    for key in keys:
        redis_client.delete(key)
    logger.info(f"Deleted {len(keys)} cache keys from Redis.")



def generate_audio(book_title, selected_title, sections, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav"):
    """
    Splits the book into tuples and generates audio for each section in the specified format.
    """
    logger.info(f"Starting audio generation for the selected section: '{selected_title}'")

    def find_selected_section(section_list, selected_title):
        """
        Recursively find the section or subsection matching the selected title.
        """
        for section in section_list:
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

    audio_files = generate_audio_from_tuples(
        tuples,
        language=language,
        studio_speaker=studio_speaker,
        speaker_type=speaker_type,
        output_format=output_format,
        book_title=book_title,
    )

    if audio_files:
        logger.info(f"Generated audio files: {audio_files}")
        return audio_files
    else:
        logger.warning("No audio files generated.")
        return None


def clone_speaker(upload_file, clone_speaker_name):
    """
    Clone a speaker and store the embeddings in Redis instead of writing to a file.

    :param upload_file: Path to the uploaded audio file for cloning.
    :param clone_speaker_name: Name of the cloned speaker.
    """
    try:
        # Upload the file for speaker cloning
        files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
        response = requests.post(TTS_SERVER_API + "/clone_speaker", files=files)
        response.raise_for_status()

        # Get the embeddings from the API response
        embeddings = response.json()

        # Save embeddings to Redis
        redis_key = f"cloned_speaker:{clone_speaker_name}"
        redis_client.set(redis_key, json.dumps(embeddings))  # Store as JSON string
        logger.info(f"Saved cloned speaker embeddings to Redis with key: {redis_key}")

    except Exception as e:
        logger.error(f"Error cloning speaker '{clone_speaker_name}': {e}")



def get_aggregated_content(selected_title, sections, include_subsections=True):
    """
    Aggregates content for the selected section and all its nested subsections.
    Includes headings and content in a hierarchical structure.
    """
    logger.debug(f"Aggregating content for title: {selected_title}")
    logger.debug(f"Sections provided: {json.dumps(sections, indent=2)}")  # Log sections for debugging

    aggregated_content = []

    def collect_content(section, include, depth=0):
        indent = "  " * depth
        heading = section.get("Heading", "").strip()
        content = section.get("Content", "")

        # Match the selected title to start including content
        if heading.lower() == selected_title.lower():
            include = True
            logger.debug(f"{indent}Matched section: '{heading}'")

        if include:
            # Add the heading
            if heading:
                aggregated_content.append(f"{indent}{heading}")
                logger.debug(f"{indent}Added heading: {heading}")

            # Add the content (handle both string and list types)
            if isinstance(content, str) and content.strip():
                aggregated_content.append(f"{indent}  {content.strip()}")
                logger.debug(f"{indent}Added content: {content[:100]}...")
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        aggregated_content.append(f"{indent}  {item.strip()}")
                        logger.debug(f"{indent}Added content item: {item.strip()}")

        # Process subsections recursively
        if include_subsections and "Subsections" in section:
            for subsection in section.get("Subsections", []):
                collect_content(subsection, include, depth + 1)

    # Iterate over top-level sections
    for section in sections:
        collect_content(section, include=False)

    result = "\n\n".join(filter(None, aggregated_content))
    logger.info(f"Aggregated content: {result[:500]}...")  # Log the first 500 characters
    return result



def text_to_audio(
    text,
    heading,
    section_index,
    lang="en",
    speaker_type="Studio",
    speaker_name_studio=None,
    speaker_name_custom=None,
    output_format="wav",
    book_title="no-title",
):
    logger.info(f"Converting text to audio for heading: '{heading}' (Index: {section_index})")

    languages, speakers, cloned_speaker = fetch_languages_and_speakers()
    embeddings = (
        speakers.get(speaker_name_studio)
        if speaker_type == "Studio"
        else cloned_speaker.get(speaker_name_custom)
    )
    if not embeddings:
        logger.error(f"No embeddings found for speaker type '{speaker_type}' and speaker name.")
        return None

    chunks = split_text_into_chunks(text)
    redis_keys = []

    for idx, chunk in enumerate(chunks):
        cache_key = f"cache:{book_title}:{section_index}:{idx}"
        try:
            response = requests.post(
                TTS_SERVER_API + "/tts",
                json={
                    "text": chunk,
                    "language": lang,
                    "speaker_embedding": embeddings["speaker_embedding"],
                    "gpt_cond_latent": embeddings["gpt_cond_latent"],
                },
            )
            if response.status_code != 200:
                logger.error(f"Error: Server returned status {response.status_code} for chunk: {chunk}")
                continue

            # Save audio chunk to Redis
            redis_client.set(cache_key, base64.b64decode(response.content))
            redis_keys.append(cache_key)

        except Exception as e:
            logger.error(f"Error generating audio for chunk {idx}: {e}")
            continue

        # Concatenate audio chunks and save final audio to Redis
        if redis_keys:
            concatenate_audios(redis_keys,output_format, book_title, section_index, heading)
        else:
            logger.warning(f"No audio generated for heading: '{heading}'")

def concatenate_audios(redis_keys, output_format="wav",  book_title="no-title", section_index="1", heading="unknown", pauses=None):
    """
    Combines multiple audio files from Redis into one, adding pauses between sentences, and saves the final audio to Redis.

    :param redis_keys: List of Redis keys pointing to cached audio chunks.
    :param book_title: Title of the book, used to generate the Redis key.
    :param section_index: Section index used to generate the Redis key.
    :param heading: Heading used to generate the Redis key.
    :param pauses: Dictionary specifying pause durations in milliseconds, e.g., {"sentence": 500, "heading": 1000}.
    """
    if pauses is None:
        pauses = {"sentence": 500, "heading": 1000}  # Default pauses in milliseconds

    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=pauses["sentence"])
    pause_between_heading_and_text = AudioSegment.silent(duration=pauses["heading"])

    for idx, redis_key in enumerate(redis_keys):
        # Retrieve audio chunk from Redis
        audio_binary = redis_client.get(redis_key)
        if not audio_binary:
            logger.error(f"Audio chunk not found for key: {redis_key}")
            continue

        # Load audio from binary
        audio = AudioSegment.from_file(io.BytesIO(audio_binary), format=output_format)

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
    redis_client.set(redis_key, output_buffer.getvalue())  # Save to Redis
    logger.info(f"Saved concatenated audio to Redis with key: {redis_key}")

    # Clean up cached chunks from Redis
    for redis_key in redis_keys:
        redis_client.delete(redis_key)
        logger.info(f"Deleted cache for key: {redis_key}")


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




def clean_filename(filename):
    """
    Cleans the filename by removing or replacing invalid characters.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()



if __name__ == "__main__":
    consume_queue("audio_tasks")
    languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()
