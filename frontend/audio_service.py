import base64
import json
import logging
import os
import re
import shutil
import uuid
from io import BytesIO
import time

import nltk
nltk.download('punkt_tab', quiet=True)
from nltk.tokenize import sent_tokenize
from tempfile import NamedTemporaryFile
import requests
from fastapi import FastAPI
from pydub import AudioSegment


# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Base server URL for TTS processing
SERVER_URL = os.getenv("TTS_API", "http://localhost:8003")

app = FastAPI()
# Initialize cached speakers and languages


@app.get("/health")
def health_check():
    try:
        # Example check: Ensure TTS server is reachable
        response = requests.get(f"{SERVER_URL}/languages", timeout=5)
        if response.status_code == 200:
            return {"status": "healthy"}
        else:
            return {"status": "unhealthy", "error": "TTS server unreachable"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

def robust_request(url, retries=3, delay=2):
    for i in range(retries):
        try:
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            if i < retries - 1:
                time.sleep(delay)
            else:
                raise e

# Metadata Initialization
LANGUAGES = []
STUDIO_SPEAKERS = {}
CLONED_SPEAKERS = {}
if health_check().get("status") == "healthy":
    try:
        LANGUAGES = robust_request(f"{SERVER_URL}/languages").json()
        STUDIO_SPEAKERS = robust_request(f"{SERVER_URL}/studio_speakers").json()
    except Exception as e:
        logger.error(f"Failed to fetch metadata: {e}")

if health_check().get("status") == "healthy":
    try:
        print("Fetching metadata from server ...")
        LANGUAGES = robust_request(f"{SERVER_URL}/languages").json()
        print("Available languages:", ", ".join(LANGUAGES))
        STUDIO_SPEAKERS = robust_request(f"{SERVER_URL}/studio_speakers").json()
        print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS.keys()))
    except Exception as e:
        logger.error(f"Failed to fetch metadata: {e}")
        CLONED_SPEAKERS = {}
        STUDIO_SPEAKERS = {}
        LANGUAGES = []


def generate_audio(selected_title, sections, book_title):
    if not selected_title:
        logger.warning("No title selected for TTS.")
        return None

    if not sections:
        logger.warning("No sections available for TTS.")
        return None

    # Aggregate content for the selected title
    aggregated_content = get_aggregated_content(selected_title, sections)
    if not aggregated_content:
        logger.warning(f"No content found for section: {selected_title}")
        return None


    # Create folder named after the book title
    folder_name = clean_filename(book_title)
    folder_path = os.path.join("outputs", "generated_audios", folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Generate audio
    try:
        logger.info(f"Generating audio for: {selected_title}")
        audio_path = text_to_audio(
            text=aggregated_content,
            heading=selected_title,
            lang="en",  # Default to English
            speaker_type="Studio",  # Default speaker type
            speaker_name_studio=list(STUDIO_SPEAKERS.keys())[0] if STUDIO_SPEAKERS else None,
            speaker_name_custom=None  # No custom speaker by default
        )

        # Move the audio to the folder
        if audio_path:
            new_audio_path = os.path.join(folder_path, os.path.basename(audio_path))
            shutil.move(audio_path, new_audio_path)
            logger.info(f"Audio saved to: {new_audio_path}")
            return new_audio_path
        else:
            logger.error("Audio generation failed.")
            return None
    except Exception as e:
        logger.exception(f"Error generating audio: {e}")
        return None


def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None,
                  output_format="wav"):
    """Generate audio using the TTS server."""
    file_name = clean_filename(heading or "Untitled")

    embeddings = STUDIO_SPEAKERS.get(speaker_name_studio, {}) if speaker_type == 'Studio' else CLONED_SPEAKERS.get(speaker_name_custom, {})
    if not embeddings:
        logger.error("Speaker embeddings not found.")
        return None

    chunks = split_text_into_chunks(heading + "\n" + text)

    cache_dir = os.path.join("outputs", "cache")
    os.makedirs(cache_dir, exist_ok=True)

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        try:
            response = requests.post(
                SERVER_URL + "/tts",
                json={
                    "text": chunk,
                    "language": lang,
                    "speaker_embedding": embeddings.get("speaker_embedding"),
                    "gpt_cond_latent": embeddings.get("gpt_cond_latent")
                }
            )
            if response.status_code != 200:
                logger.warning(f"TTS server returned status {response.status_code} for chunk: {chunk}")
                continue

            decoded_audio = base64.b64decode(response.content)
            audio_path = os.path.join(cache_dir, f"{file_name}_{idx + 1}.wav")
            with open(audio_path, "wb") as fp:
                fp.write(decoded_audio)
                cached_audio_paths.append(audio_path)
        except Exception as e:
            logger.error(f"Error processing chunk {idx + 1}: {e}")

    if cached_audio_paths:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        final_path = os.path.join("outputs", "generated_audios", f"{file_name}_{uuid.uuid4().hex}.{output_format}")
        shutil.move(combined_audio_path, final_path)
        shutil.rmtree(cache_dir)
        return final_path
    else:
        logger.error("No audio chunks were successfully generated.")
        return None

def get_aggregated_content(selected_title, sections, include_subsections=True):
    aggregated_content = []

    def collect_content(section, include, depth=0):
        if section.get("title") == selected_title:
            include = True
            logger.debug(f"Matched section: '{section['title']}' (Style: {section.get('style', 'Unknown Style')})")

        if include:
            aggregated_content.append(section.get("content", ""))

        # Only recurse into subsections if include_subsections is True
        if include_subsections:
            for subsection in section.get("subsections", []):
                collect_content(subsection, include, depth + 1)

    for section in sections:
        collect_content(section, include=False)

    return "\n\n".join(filter(None, aggregated_content))


def concatenate_audios(audio_paths, title, output_format="wav", output_name="combined_audio"):
    logger.debug(f"Combining title and {len(audio_paths)} audio files...")

    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=500)  # Optional: Add 500ms silence between title and sections

    # Generate a temporary audio file for the title
    title_audio_path = generate_title_audio(title, output_format="wav")
    logger.debug(f"Generated title audio at {title_audio_path}")

    # Add section audios to the combined audio
    for path in audio_paths:
        logger.debug(f"Adding audio file: {path}")
        audio = AudioSegment.from_file(path)
        combined += audio + silence

    # Export the final combined audio
    output_path = os.path.join("demo_outputs", "generated_audios", f"{output_name}.{output_format}")
    combined.export(output_path, format=output_format)
    logger.debug(f"Combined audio saved to: {output_path}")

    # Clean up the temporary title audio file
    os.remove(title_audio_path)

    return output_path

def split_text_into_chunks(text, max_chars=250, max_tokens=350):
    sentences = sent_tokenize(text)  # Better sentence splitting
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = len(sentence) // 4  # Approximate token count
        if len(current_chunk) + len(sentence) <= max_chars and current_tokens + sentence_tokens <= max_tokens:
            current_chunk += sentence + " "
            current_tokens += sentence_tokens
        else:
            if len(sentence) > max_chars or sentence_tokens > max_tokens:
                sentence_parts = [sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)]
                for part in sentence_parts:
                    part_tokens = len(part) // 4
                    if len(current_chunk) + len(part) <= max_chars and current_tokens + part_tokens <= max_tokens:
                        current_chunk += part + " "
                        current_tokens += part_tokens
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = part + " "
                        current_tokens = part_tokens
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                current_tokens = sentence_tokens
    if current_chunk:
        chunks.append(current_chunk.strip())

    logger.debug(f"Split text into {len(chunks)} chunks")
    return chunks


def get_speaker_embeddings(speaker_type, speaker_name):
    url = f"{SERVER_URL}/studio_speakers" if speaker_type == "Studio" else f"{SERVER_URL}/cloned_speakers"
    response = requests.get(url)
    response.raise_for_status()
    speakers = response.json()
    if speaker_name not in speakers:
        logger.warning(f"Speaker '{speaker_name}' not found. Available speakers: {list(speakers.keys())}")
        raise ValueError(f"Speaker '{speaker_name}' not found.")
    return speakers[speaker_name]


def fetch_languages_and_speakers():
    """Fetch available languages and speakers from the TTS server."""
    try:
        logger.info("Fetching languages and speakers.")
        languages = requests.get(f"{SERVER_URL}/languages").json()
        studio_speakers = requests.get(f"{SERVER_URL}/studio_speakers").json()
        cloned_speakers = {}  # Initialize empty cloned speakers if not fetched
        return languages, studio_speakers, cloned_speakers
    except Exception as e:
        logger.error(f"Error fetching metadata: {e}")
        return [], {}, {}


def clean_filename(filename):
    clean_name = re.sub(r'[<>:"/\\|?*]', "_", filename).strip()
    return clean_name or "default_filename"


def generate_title_audio(title, lang="en", speaker_type="Studio", speaker_name=None, output_format="wav"):
    try:
        embeddings = get_speaker_embeddings(speaker_type, speaker_name)
        payload = {
            "text": title,
            "language": lang,
            "speaker_embedding": embeddings.get("speaker_embedding"),
            "gpt_cond_latent": embeddings.get("gpt_cond_latent"),
        }
        response = requests.post(f"{SERVER_URL}/tts", json=payload)
        response.raise_for_status()
        audio_data = base64.b64decode(response.content)

        with NamedTemporaryFile(delete=False, suffix=f".{output_format}") as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name

        logger.info(f"Title audio generated at {temp_audio_path}")
        return temp_audio_path
    except Exception as e:
        logger.error(f"Error generating title audio: {e}")
        raise RuntimeError("Failed to generate title audio.")



def text_to_audio_in_memory(text, lang, speaker_type, speaker_name):
    """Generate audio and return it in memory as a byte array."""
    embeddings = get_speaker_embeddings(speaker_type, speaker_name)
    payload = {
        "text": text,
        "language": lang,
        "speaker_embedding": embeddings.get("speaker_embedding"),
        "gpt_cond_latent": embeddings.get("gpt_cond_latent"),
    }

    response = requests.post(f"{SERVER_URL}/tts", json=payload)
    response.raise_for_status()
    audio_data = base64.b64decode(response.content)
    return BytesIO(audio_data)
