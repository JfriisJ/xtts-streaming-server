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
    logger.info(f"Audio Service: Starting audio generation for section '{selected_title}'")
    logger.debug(f"Received Book Title: {book_title}")
    logger.debug(f"Selected Section Title: {selected_title}")
    logger.debug(f"Language: {language}")
    logger.debug(f"Speaker Type: {speaker_type}")
    logger.debug(f"Speaker Name: {studio_speaker}")
    logger.debug(f"Sections Data: {sections}")

    aggregated_content = aggregate_section_content(selected_title, sections)
    logger.debug(f"Aggregated Content: {aggregated_content}")

    logger.debug(f"Aggregated content for section '{selected_title}': {aggregated_content}")
    if not aggregated_content:
        logger.error("No aggregated content found. Cannot proceed with audio generation.")
        return None

    try:
        audio_path = text_to_audio(
            text=aggregated_content,
            heading=selected_title,
            lang=language,
            speaker_type=speaker_type,
            speaker_name_studio=studio_speaker
        )
        logger.info(f"Audio generated successfully for section '{selected_title}'. Path: {audio_path}")
        return audio_path
    except Exception as e:
        logger.error(f"Error generating audio for section '{selected_title}': {e}")
        return None

def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(XTTS_SERVER_API + "/clone_speaker", files=files).json()
    with open(os.path.join(OUTPUT, "cloned_speakers", clone_speaker_name + ".json"), "w") as fp:
        json.dump(embeddings, fp)
    CLONED_SPEAKERS[clone_speaker_name] = embeddings
    cloned_speaker_names.append(clone_speaker_name)


def aggregate_section_content(selected_title, sections, include_subsections=True):
    """
    Aggregates content for the selected section and its subsections.
    """
    logger.debug(f"Starting aggregation for title: {selected_title}")
    logger.debug(f"Sections: {json.dumps(sections, indent=2)}")  # Logs sections for debugging

    aggregated_content = []

    def collect_content(section, include, depth=0):
        if section.get("title") == selected_title:
            include = True
            logger.debug(f"Matched section: '{section['title']}'")

        if include:
            content = section.get("content", "").strip()
            if content:
                aggregated_content.append(content)

        for subsection in section.get("subsections", []):
            collect_content(subsection, include, depth + 1)

    for section in sections:
        collect_content(section, include=False)

    result = "\n\n".join(filter(None, aggregated_content))
    logger.info(f"Aggregated Content: {result}")
    return result



def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None, output_format="wav"):

    logger.info(f"Audio Service: Converting text to audio for '{heading}'")
    logger.debug(f"Text Content: {text[:100]}...")  # Log first 100 characters to avoid clutter
    logger.debug(f"Language: {lang}")
    logger.debug(f"Speaker Type: {speaker_type}")
    logger.debug(f"Studio Speaker: {speaker_name_studio}")
    logger.debug(f"Custom Speaker: {speaker_name_custom}")

    file_name = clean_filename(heading)
    logger.debug(f"Cleaned file name: {file_name}")

    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == "Studio" else CLONED_SPEAKERS.get(speaker_name_custom, {})
    if not embeddings:
        logger.error(f"Embeddings not found for speaker type: {speaker_type}, speaker: {speaker_name_studio or speaker_name_custom}")
        return None

    logger.debug(f"Using embeddings: {embeddings}")

    heading_chunk = heading.strip()
    text_chunks = split_text_into_chunks(text)

    chunks = [heading_chunk] + text_chunks
    cache_dir = os.path.join("outputs", "cache")
    os.makedirs(cache_dir, exist_ok=True)
    logger.debug(f"Cache directory: {cache_dir}")

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        try:

            logger.debug(f"Sending chunk to TTS API: {chunk[:50]}...")  # Log only the first 50 characters
            response = requests.post(
                XTTS_SERVER_API + "/tts",
                json={
                    "text": chunk,
                    "language": lang,
                    "speaker_embedding": embeddings["speaker_embedding"],
                    "gpt_cond_latent": embeddings["gpt_cond_latent"]
                }
            )
            logger.debug(f"TTS API Response: Status Code: {response.status_code}, Response Body: {response.text}")

            if response.status_code != 200:
                logger.error(f"TTS server error: {response.status_code}, Response: {response.text}")
                return None

            if response.status_code != 200:
                logger.error(f"Error from TTS API: {response.status_code}, Response: {response.text}")
                continue

            decoded_audio = base64.b64decode(response.content)
            audio_path = os.path.join(cache_dir, f"{file_name}_{idx + 1}.wav")
            with open(audio_path, "wb") as fp:
                fp.write(decoded_audio)
                cached_audio_paths.append(audio_path)
            logger.info(f"Saved audio chunk to: {audio_path}")
        except Exception as e:
            logger.error(f"Error processing chunk {idx}: {e}")
            continue

    if cached_audio_paths:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        final_path = os.path.join("outputs", "generated_audios", f"{file_name}.{output_format}")
        os.rename(combined_audio_path, final_path)
        shutil.rmtree(cache_dir)
        logger.info(f"Final audio saved to: {final_path}")
        return final_path
    else:
        logger.error("No audio chunks generated.")
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




