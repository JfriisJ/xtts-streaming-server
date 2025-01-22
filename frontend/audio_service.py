import base64
import json
import logging
import os
import shutil
import time
from transformers import GPT2TokenizerFast
import re

import requests
from pydub import AudioSegment

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

# Initialize cached speakers and languages
OUTPUT = "./outputs"
os.makedirs(os.path.join(OUTPUT, "cloned_speakers"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT, "generated_audios"), exist_ok=True)


LANGUAGES, STUDIO_SPEAKERS, CLONED_SPEAKERS = {}, {}, {}
retries = 5
for attempt in range(retries):
    try:
        LANGUAGES = requests.get(f"{TTS_SERVER_API}/languages", timeout=10).json()
        STUDIO_SPEAKERS = requests.get(f"{TTS_SERVER_API}/studio_speakers", timeout=10).json()
        CLONED_SPEAKERS = {}
        print("Audio service connected.")
        break
    except requests.exceptions.RequestException as e:
        logger.warning(f"Audio service connection attempt {attempt + 1} failed: {e}")
        if attempt < retries - 1:
            time.sleep(10)
        else:
            logger.error("Failed to connect to the audio service after multiple attempts.")


print("Preparing file structure...")
if not os.path.exists(OUTPUT):
    os.mkdir(OUTPUT)
    os.mkdir(os.path.join(OUTPUT, "cloned_speakers"))
    os.mkdir(os.path.join(OUTPUT, "generated_audios"))


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


def generate_audio_from_tuples(tuples, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav",book_title="no-title"):
    """
    Generates audio for each tuple and saves the files in a folder named after the book_title.
    """
    logger.info("Starting audio generation from tuples.")


    audio_files = []

    for section_index, section_name, content in tuples:
        # Ensure no content is skipped
        if not content.strip():
            logger.warning(f"Section '{section_name}' (Index: {section_index}) has no content.")
            content = f"(No content for section '{section_name}')"

        try:
            logger.info(f"Generating audio for section '{section_name}' (Index: {section_index})")
            logger.debug(f"Section content: {content[:500]}...")  # Log first 500 characters
            file_path = text_to_audio(
                text=content,
                heading=section_name,
                section_index=section_index,  # Pass the hierarchical index
                lang=language,
                speaker_type=speaker_type,
                speaker_name_studio=studio_speaker,
                output_format=output_format,
                book_title=book_title
            )
            if file_path:
                audio_files.append(file_path)
        except Exception as e:
            logger.error(f"Error generating audio for section '{section_name}' (Index: {section_index}): {e}")

    logger.info(f"Completed audio generation. Generated files: {audio_files}")
    return audio_files


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




def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(TTS_SERVER_API + "/clone_speaker", files=files).json()
    with open(os.path.join(OUTPUT, "cloned_speakers", clone_speaker_name + ".json"), "w") as fp:
        json.dump(embeddings, fp)
    CLONED_SPEAKERS[clone_speaker_name] = embeddings
    cloned_speaker_names.append(clone_speaker_name)


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
    logger.debug(f"Text to convert: {text[:100]}...")

    # Clean the book title and ensure the directory exists
    clean_book_title = clean_filename(book_title)
    book_output_dir = os.path.join(OUTPUT, "generated_audios", clean_book_title)
    os.makedirs(book_output_dir, exist_ok=True)

    # Combine index and heading for the file name
    file_name = clean_filename(f"{section_index}_{heading}")
    file_path = os.path.join(book_output_dir, f"{file_name}.{output_format}")
    logger.debug(f"Generated file path: {file_path}")

    embeddings = (
        STUDIO_SPEAKERS.get(speaker_name_studio)
        if speaker_type == "Studio"
        else CLONED_SPEAKERS.get(speaker_name_custom)
    )
    if not embeddings:
        logger.error(f"No embeddings found for speaker type '{speaker_type}' and speaker name.")
        return None

    logger.debug(f"Using embeddings: {embeddings}")

    # Process the text into smaller chunks
    chunks = split_text_into_chunks(text)

    cache_dir = os.path.join(OUTPUT, "cache")
    os.makedirs(cache_dir, exist_ok=True)

    cached_audio_paths = []
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
        chunk_path = os.path.join(cache_dir, f"{file_name}_{idx + 1}.wav")
        with open(chunk_path, "wb") as fp:
            fp.write(decoded_audio)
            cached_audio_paths.append(chunk_path)

    if len(cached_audio_paths) > 0:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format, clean_book_title)
        shutil.move(combined_audio_path, file_path)
        shutil.rmtree(cache_dir)
        logger.info(f"Saved audio file: {file_path}")
        return file_path
    else:
        logger.warning(f"No audio files generated for heading: '{heading}'")
        return None




def concatenate_audios(audio_paths, output_format="mp3", book_title="no-title", pauses=None):
    """
    Combines multiple audio files into one with configurable pauses and allows saving in different formats.
    """
    if pauses is None:
        pauses = {"sentence": 500, "heading": 1000}  # Default pauses in milliseconds

    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=pauses["sentence"])
    pause_between_heading_and_text = AudioSegment.silent(duration=pauses["heading"])

    for idx, path in enumerate(audio_paths):
        audio = AudioSegment.from_file(path)
        if idx == 0:
            combined += audio + pause_between_heading_and_text
        else:
            combined += audio + pause_between_sentences

    combined = combined[:-len(pause_between_sentences)]  # Remove the final pause

    # Ensure the output folder exists
    clean_book_title = clean_filename(book_title)
    book_output_dir = os.path.join(OUTPUT, "generated_audios", clean_book_title)
    os.makedirs(book_output_dir, exist_ok=True)

    # Save the combined audio in the specified format
    output_file_path = os.path.join(book_output_dir, f"combined_audio.{output_format}")
    combined.export(output_file_path, format=output_format)
    logger.info(f"Saved combined audio file: {output_file_path}")
    return output_file_path




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



