import base64
import io
import json
import logging
import os
from transformers import GPT2TokenizerFast
import re

import requests
from pydub import AudioSegment

import redis


# Initialize Redis client
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_status_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=0)
redis_task_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=1)
redis_audio_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=2)

TTS_SERVER_API = os.getenv("TTS_SERVER_API", "http://localhost:4001")

# Initialize the tokenizer
tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Initialize cached speakers and languages
OUTPUT = "./outputs"
os.makedirs(os.path.join(OUTPUT, "generated_audios"), exist_ok=True)


print("Preparing file structure...")
if not os.path.exists(OUTPUT):
    os.mkdir(OUTPUT)
    os.mkdir(os.path.join(OUTPUT, "generated_audios"))

#------------------------------------------------------------
#redis section
def monitor_redis_for_tasks():
    """
    Listen to Redis Pub/Sub for new tasks and trigger audio generation.
    """
    # Subscribe to the Redis Pub/Sub channel
    pubsub = redis_task_client.pubsub()
    pubsub.subscribe("audio_generation_channel")
    logger.info("Subscribed to 'audio_generation_channel'")

    # Listen for messages on the channel
    for message in pubsub.listen():
        try:
            if message["type"] == "message":
                # Parse the incoming task data
                task_data = json.loads(message["data"])  # Ensure task_data is parsed as a dictionary
                task_id = task_data.get("task_id")

                if not task_id:
                    logger.error(f"Task data missing 'task_id': {task_data}")
                    continue

                # Extract and validate required fields
                book_title = task_data.get("book_title")
                section_heading = task_data.get("section_heading")
                language = task_data.get("language", "en")
                speaker_name = task_data.get("speaker_name", "Default Speaker")
                speaker_type = task_data.get("speaker_type", "Studio")
                output_format = task_data.get("output_format", "wav")

                # Parse 'sections' if it is a string
                sections_raw = task_data.get("sections")
                if isinstance(sections_raw, str):
                    try:
                        sections_raw = json.loads(sections_raw)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse 'sections' as JSON for task {task_id}: {e}")
                        redis_task_client.set(f"status:{task_id}", f"error: invalid 'sections' format")
                        continue

                # Validate the structure of 'sections'
                if not isinstance(sections_raw, dict) or "Content" not in sections_raw:
                    logger.error(f"'Sections' structure is invalid or missing for task {task_id}: {task_data}")
                    redis_task_client.set(f"status:{task_id}", "error: invalid 'sections' structure")
                    continue

                # Parse the sections
                sections = parse_sections(sections_raw)

                if not sections:
                    logger.error(f"No valid sections extracted for task {task_id}: {task_data}")
                    redis_task_client.set(f"status:{task_id}", "error: no valid sections extracted")
                    continue

                # Check the current task status
                status = redis_task_client.get(f"status:{task_id}")
                if status != "queued":
                    logger.info(f"Ignoring task {task_id} with status: {status}")
                    continue

                # Update the task status to 'processing'
                redis_task_client.set(f"status:{task_id}", "processing")
                logger.info(f"Processing task {task_id}: {task_data}")

                try:
                    # Generate audio for the task
                    generate_audio(
                        book_title=book_title,
                        selected_title=section_heading,
                        sections=sections,
                        language=language,
                        studio_speaker=speaker_name,
                        speaker_type=speaker_type,
                        output_format=output_format,
                    )

                    redis_task_client.set(f"status:{task_id}", "completed")
                    logger.info(f"Task {task_id} completed successfully")
                except Exception as e:
                    logger.error(f"Error processing task {task_id}: {e}")
                    redis_task_client.set(f"status:{task_id}", f"error: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from message: {e}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")


def parse_sections(sections_data):
    """
    Parse sections from the task data and extract valid content.
    """

    def extract_section(section):
        # Extract content from the section
        content = section.get("Content", "").strip()
        if isinstance(content, str) and content:
            # If content is a non-empty string, return it with the heading
            return {"Heading": section.get("Heading", "").strip(), "Content": content}
        elif isinstance(content, list):
            # If content is a list, join the items into a single string
            return {"Heading": section.get("Heading", "").strip(), "Content": "\n".join(map(str, content))}
        return None  # Skip sections without valid content

    parsed_sections = []

    # Check if sections_data is a dictionary
    if isinstance(sections_data, dict):
        top_section = extract_section(sections_data)
        if top_section:
            parsed_sections.append(top_section)  # Add top-level section
        # Recursively parse all subsections
        for subsection in sections_data.get("Subsections", []):
            parsed_sections.extend(parse_sections(subsection))

    # Check if sections_data is a list
    elif isinstance(sections_data, list):
        for section in sections_data:
            # Recursively parse each section in the list
            parsed_sections.extend(parse_sections(section))

    return parsed_sections


def aggregate_section_with_subsections(section):
    """
    Aggregate content of a section and its subsections recursively.
    """
    content = section.get("Content", "")
    if isinstance(content, list):
        content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
    elif isinstance(content, str):
        content = content.strip()
    else:
        content = ""

    subsections = section.get("Subsections", [])
    for subsection in subsections:
        sub_heading = subsection.get("Heading", "").strip()
        sub_content = aggregate_section_with_subsections(subsection)
        if sub_heading:
            content += f"\n\n{sub_heading}\n{sub_content}"

    return content


def split_text_into_tuples(sections):
    """
    Splits the book text into tuples of (index, section_name, content).
    Ensures hierarchical indexes follow a consistent 4-level pattern.
    """
    tuples = []
    section_counts = {}  # Track counts for each hierarchical level

    def process_section(section, level=0, index_prefix="0"):
        """
        Recursively processes sections and generates hierarchical indexes with consistent 4-level depth.
        """
        # Increment the count for the current level
        if index_prefix not in section_counts:
            section_counts[index_prefix] = 0
        section_counts[index_prefix] += 1

        # Generate the next index
        index_parts = index_prefix.split(".")
        if level <= len(index_parts):
            index_parts[level - 1] = str(section_counts[index_prefix])
        else:
            index_parts.extend(['0'] * (level - len(index_parts) - 1))
            index_parts.append(str(section_counts[index_prefix]))

        # # Ensure the index has exactly 4 levels
        # while len(index_parts) < 4:
        #     index_parts.append("0")

        # Reconstruct the index as a string
        current_index = ".".join(index_parts[:4])

        # Extract section details
        heading = section.get("Heading", "").strip()
        content = section.get("Content", "")

        # Handle content as a string or list
        if isinstance(content, list):
            content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
        elif isinstance(content, str):
            content = content.strip()
        else:
            content = ""

        # Combine section name and content
        if content:
            combined_content = f"{heading}\n\n{content}"  # Include section name followed by content
        else:
            combined_content = heading  # Use section name only if no content exists

        # Add the current section as a tuple
        tuples.append((current_index, heading, combined_content))

        # Process subsections recursively
        subsections = section.get("Subsections", [])
        for subsection in subsections:
            process_section(subsection, level + 1, current_index)

    # Process each top-level section
    for section in sections:
        process_section(section)

    return tuples


def generate_audio_from_tuples(tuples, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav",book_title="no-title"):
    """
    Generates audio for each tuple and saves the files in a folder named after the book_title.
    """
    logger.info("Starting audio generation from tuples.")


    audio_files = []

    for section_index, section_name, content in tuples:

        # log the current tuple being processed
        logger.info(f"Processing tuple: {section_index} - {section_name}out of {len(tuples)}")
        # Ensure no content is skipped
        if not content.strip():
            logger.warning(f"Section '{section_name}' (Index: {section_index}) has no content.")
            content = f"(No content for section '{section_name}')"

        try:
            logger.info(f"Generating audio for section '{section_name}' (Index: {section_index})")
            text_to_audio(
                text=content,
                heading=section_name,
                section_index=section_index,  # Pass the hierarchical index
                lang=language,
                speaker_type=speaker_type,
                speaker_name_studio=studio_speaker,
                output_format=output_format,
                book_title=book_title
            )
        except Exception as e:
            logger.error(f"Error generating audio for section '{section_name}' (Index: {section_index}): {e}")

    logger.info(f"Completed audio generation. Total cached audio files: {len(audio_files)}")



def generate_audio(book_title, selected_title, sections, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav"):
    """
    Splits the book into tuples and generates audio for each section in the specified format.
    """
    if selected_title == book_title:
        logger.info(f"Starting audio generation for the whole book: '{book_title}'")
        tuples = split_text_into_tuples(sections)
    else:
        logger.info(f"Starting audio generation for the selected section: '{selected_title}'")
        tuples = split_text_into_tuples([section for section in sections if section.get("Heading") == selected_title])

    if not tuples:
        logger.warning("No sections to process for audio generation.")
        return None

    generate_audio_from_tuples(
        tuples,
        language=language,
        studio_speaker=studio_speaker,
        speaker_type=speaker_type,
        output_format=output_format,
        book_title=book_title,
    )


def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(TTS_SERVER_API + "/clone_speaker", files=files).json()
    with open(os.path.join(OUTPUT, "cloned_speakers", clone_speaker_name + ".json"), "w") as fp:
        json.dump(embeddings, fp)
    [clone_speaker_name] = embeddings
    cloned_speaker_names.append(clone_speaker_name)


def fetch_service_data():
    """
    Fetch languages and speakers data from Redis.
    """
    try:
        # Fetch languages and speakers from Redis
        languages = redis_status_client.get("data:tts:languages")
        studio_speakers = redis_status_client.get("data:tts:studio_speakers")
        cloned_speakers = redis_status_client.get("data:tts:cloned_speakers")

        # Parse the JSON data if present
        languages = json.loads(languages) if languages else []  # Expecting a list
        studio_speakers = json.loads(studio_speakers) if studio_speakers else {}  # Expecting a dictionary
        cloned_speakers = json.loads(cloned_speakers) if cloned_speakers else {}  # Expecting a dictionary

        return languages, studio_speakers, cloned_speakers
    except Exception as e:
        logger.error(f"Error fetching languages and speakers from Redis: {e}")
        return [], {}  # Return empty list and dictionary as fallback

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
    task_id=None,  # Task ID for Redis key structuring
):
    logger.info(f"Converting text to audio for heading: '{heading}' (Index: {section_index})")
    logger.debug(f"Text to convert: {text[:100]}...")

    # Fetch speaker embeddings from Redis
    languages, studio_speakers, cloned_speakers = fetch_service_data()
    embeddings = (
        studio_speakers.get(speaker_name_studio)
        if speaker_type == "Studio"
        else cloned_speakers.get(speaker_name_custom)
    )
    if not embeddings:
        logger.error(f"No embeddings found for speaker type '{speaker_type}' and speaker name.")
        return None

    # Process the text into smaller chunks
    chunks = split_text_into_chunks(text)

    logger.info(f"Generating audio chunks for heading: '{heading}' '{chunks}'")

    cached_chunk_keys = []
    for idx, chunk in enumerate(chunks):
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

        decoded_audio = base64.b64decode(response.content)
        cache_chunk_key = f"{idx}:{clean_filename(book_title)}:{clean_filename(heading)}:{section_index}"


        redis_audio_client.set(cache_chunk_key, base64.b64encode(decoded_audio).decode("utf-8"))
        cached_chunk_keys.append(cache_chunk_key)
        logger.info(f"Audio chunk {idx + 1} cached in Redis under key: {cache_chunk_key}")

    if not cached_chunk_keys:
        logger.warning(f"No audio chunks generated for heading: '{heading}'")
        return None

    # Concatenate audio chunks and save file in Redis
    concatenate_audios(cached_chunk_keys, book_title, section_index, heading, output_format)


def concatenate_audios(cached_chunk_keys, book_title, section_index, heading="no-heading", output_format="mp3", pauses=None):
    """
    Combines multiple audio chunks stored in Redis into one audio file and clears the cached chunks.
    """

    logger.info(f"Combining audio chunks for heading: '{heading}' (Index: {section_index})")
    if pauses is None:
        pauses = {"sentence": 500, "heading": 1000}  # Default pauses in milliseconds

    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=pauses["sentence"])
    pause_between_heading_and_text = AudioSegment.silent(duration=pauses["heading"])

    for idx, redis_key in enumerate(cached_chunk_keys):
        try:
            # Fetch audio chunk data from Redis
            audio_data = redis_audio_client.get(redis_key)
            if not audio_data:
                logger.error(f"Audio chunk not found in Redis for key: {redis_key}")
                continue

            # Decode the audio data
            audio_chunk = AudioSegment.from_file(io.BytesIO(base64.b64decode(audio_data)), format="wav")

            # Add pauses
            if idx == 0:
                combined += audio_chunk + pause_between_heading_and_text
            else:
                combined += audio_chunk + pause_between_sentences
        except Exception as e:
            logger.error(f"Error processing audio chunk for key {redis_key}: {e}")

    # Remove the final pause
    combined = combined[:-len(pause_between_sentences)]

    # Save the combined audio back to Redis
    final_key = f"{clean_filename(book_title)}:{clean_filename(heading)}:{section_index}"
    try:
        with io.BytesIO() as output_buffer:
            combined.export(output_buffer, format=output_format)
            redis_audio_client.set(final_key, base64.b64encode(output_buffer.getvalue()).decode("utf-8"))
            logger.info(f"Combined audio saved in Redis under key: {final_key}")

        # Clear cached audio chunks from Redis
        for redis_key in cached_chunk_keys:
            try:
                redis_audio_client.delete(redis_key)
                logger.info(f"Cleared cached audio chunk from Redis: {redis_key}")
            except Exception as e:
                logger.error(f"Error clearing cached audio chunk {redis_key} from Redis: {e}")

    except Exception as e:
        logger.error(f"Error saving combined audio for section '{heading}' to Redis: {e}")
        return None


def split_text_into_chunks(text, max_chars=250, max_tokens=400):
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
    logger.info("Starting audio service...")
    monitor_redis_for_tasks()