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

from health_service import XTTS_SERVER_API

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
        LANGUAGES = requests.get(f"{XTTS_SERVER_API}/languages", timeout=10).json()
        STUDIO_SPEAKERS = requests.get(f"{XTTS_SERVER_API}/studio_speakers", timeout=10).json()
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


import os

def generate_audio(book_title, selected_title, sections, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav"):
    logger.info(f"Starting audio generation for '{selected_title or book_title}'")
    logger.debug(f"Input Sections: {json.dumps(sections, indent=2)}")
    audio_files = []

    if selected_title == book_title:
        logger.info(f"Generating audio for the entire book '{book_title}'")
        for section in sections:
            heading = section.get("Heading", "Untitled Section")
            content = get_aggregated_content(heading, [section])

            if not content.strip():
                logger.warning(f"Skipping empty section: {heading}")
                continue

            try:
                file_name = f"{clean_filename(heading)}.{output_format}"
                logger.debug(f"Generating audio for section '{heading}' with file name: {file_name}")
                text_to_audio(
                    text=content,
                    heading=heading,
                    lang=language,
                    speaker_type=speaker_type,
                    speaker_name_studio=studio_speaker,
                    output_format=output_format
                )
                audio_files.append(file_name)
            except Exception as e:
                logger.error(f"Failed to generate audio for section '{heading}': {e}")
    else:
        logger.info(f"Generating audio for the selected section '{selected_title}'")
        content = get_aggregated_content(selected_title, sections)
        if not content.strip():
            logger.warning(f"No content found for the selected section: {selected_title}")
            return None

        try:
            file_name = f"{clean_filename(selected_title)}.{output_format}"
            logger.debug(f"Generating audio for section '{selected_title}' with file name: {file_name}")
            text_to_audio(
                text=content,
                heading=selected_title,
                lang=language,
                speaker_type=speaker_type,
                speaker_name_studio=studio_speaker,
                output_format=output_format
            )
            audio_files.append(file_name)
        except Exception as e:
            logger.error(f"Failed to generate audio for section '{selected_title}': {e}")

    if audio_files:
        logger.info(f"Generated audio files: {audio_files}")
        return audio_files
    else:
        logger.warning("No audio files generated.")
        return None



def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(XTTS_SERVER_API + "/clone_speaker", files=files).json()
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



def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None, output_format="wav"):
    logger.info(f"Converting text to audio for heading: '{heading}'")
    logger.debug(f"Text to convert: {text[:100]}...")
    file_name = clean_filename(heading)
    logger.debug(f"Generated file name: {file_name}")

    embeddings = STUDIO_SPEAKERS.get(speaker_name_studio) if speaker_type == "Studio" else CLONED_SPEAKERS.get(speaker_name_custom)
    if not embeddings:
        logger.error(f"No embeddings found for speaker type '{speaker_type}' and speaker name.")
        return None

    logger.debug(f"Using embeddings: {embeddings}")


    # Process the text into smaller chunks
    chunks = split_text_into_chunks(text)

    cache_dir = os.path.join("outputs", "cache")
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    print(f"cache_dir: {cache_dir}")

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        response = requests.post(
            XTTS_SERVER_API + "/tts",
            json={
                "text": chunk,
                "language": lang,
                "speaker_embedding": embeddings["speaker_embedding"],
                "gpt_cond_latent": embeddings["gpt_cond_latent"]
            }
        )
        if response.status_code != 200:
            print(f"Error: Server returned status {response.status_code} for chunk: {chunk}")
            continue

        decoded_audio = base64.b64decode(response.content)
        audio_path = os.path.join(cache_dir, f"{file_name}_{idx + 1}.wav")
        with open(audio_path, "wb") as fp:
            fp.write(decoded_audio)
            cached_audio_paths.append(audio_path)

    if len(cached_audio_paths) > 0:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        final_path = os.path.join("outputs", "generated_audios", f"{file_name}.{output_format}")
        os.rename(combined_audio_path, final_path)
        shutil.rmtree(cache_dir)
        return final_path
    else:
        return None

def concatenate_audios(audio_paths, output_format="wav"):
    """
    Combines multiple audio files into one with added pauses for natural sound.
    """
    combined = AudioSegment.empty()
    pause_between_sentences = AudioSegment.silent(duration=500)  # 500ms pause
    pause_between_heading_and_text = AudioSegment.silent(duration=1000)  # 1 second pause

    for idx, path in enumerate(audio_paths):
        audio = AudioSegment.from_file(path)

        # Add a longer pause after the first chunk (assuming it's the heading)
        if idx == 0:
            combined += audio + pause_between_heading_and_text
        else:
            combined += audio + pause_between_sentences

    # Remove the final pause
    combined = combined[:-len(pause_between_sentences)]

    # Export the combined audio
    output_path = os.path.join("outputs", "generated_audios", f"combined_audio_temp.{output_format}")
    combined.export(output_path, format=output_format)
    return output_path


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



