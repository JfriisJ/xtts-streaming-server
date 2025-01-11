import base64
import json
import logging
import os
import re
import tempfile
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




def clone_speaker(upload_file, speaker_name):
    """Clone a speaker using reference audio."""
    try:
        logger.info(f"Cloning speaker: {speaker_name}")
        with open(upload_file, "rb") as audio_file:
            files = {"wav_file": ("reference.wav", audio_file)}
            embeddings = requests.post(f"{SERVER_URL}/clone_speaker", files=files).json()
        output_path = os.path.join("demo_outputs", "cloned_speakers", f"{speaker_name}.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as fp:
            json.dump(embeddings, fp)
        logger.info(f"Speaker cloned successfully and saved to {output_path}.")
        return output_path
    except requests.RequestException as e:
        logger.error(f"Error cloning speaker: {e}")
        raise RuntimeError("Failed to clone speaker.")


def generate_audio(selected_title, sections, book_title, lang="en", speaker_type="Studio", speaker_name=None):
    """
    Generate audio for a given section of a document, including the title and section content,
    and keep the audio chunks in memory.
    """
    logger.info(f"Generating audio for section '{selected_title}' in book '{book_title}'")
    if not selected_title or not sections:
        raise ValueError("Invalid input: selected_title or sections is missing.")

    # Aggregate content and prepend the title
    aggregated_content = get_aggregated_content(selected_title, sections)
    if not aggregated_content:
        raise ValueError(f"No content found for section: {selected_title}")

    full_content = f"{selected_title}\n\n{aggregated_content}"  # Prepend the title to the content

    # Split the full content into manageable chunks
    chunks = split_text_into_chunks(full_content)
    logger.info(f"Text split into {len(chunks)} chunks for TTS processing.")

    combined_audio = AudioSegment.empty()

    try:
        for idx, chunk in enumerate(chunks):
            try:
                logger.info(f"Processing chunk {idx + 1}/{len(chunks)}: {chunk[:30]}...")
                audio_stream = text_to_audio_in_memory(
                    text=chunk,
                    lang=lang,
                    speaker_type=speaker_type,
                    speaker_name=speaker_name
                )
                chunk_audio = AudioSegment.from_file(audio_stream, format="wav")
                combined_audio += chunk_audio + AudioSegment.silent(duration=500)  # Add silence padding
            except Exception as e:
                logger.error(f"Failed to process chunk {idx + 1}: {e}")

        # Export the combined audio to memory
        final_audio_io = BytesIO()
        combined_audio.export(final_audio_io, format="wav")
        final_audio_io.seek(0)

        logger.info("Final combined audio generated successfully.")
        return final_audio_io
    except Exception as e:
        logger.exception(f"Error generating audio in memory: {e}")
        raise RuntimeError("Audio generation failed in memory.")


def text_to_audio(text, lang, speaker_type, speaker_name, output_format="wav"):
    """Generate audio using the TTS server."""
    try:
        embeddings = get_speaker_embeddings(speaker_type, speaker_name)
        payload = {
            "text": text,
            "language": lang,
            "speaker_embedding": embeddings.get("speaker_embedding"),
            "gpt_cond_latent": embeddings.get("gpt_cond_latent"),
        }

        response = requests.post(f"{SERVER_URL}/tts", json=payload)
        logger.debug(f"TTS server response content: {response.content[:1]}")

        # Check for non-200 status codes
        response.raise_for_status()

        # Check if response is JSON or raw base64
        try:
            response_data = response.json()
            base64_audio = response_data.get("audio")
            if not base64_audio:
                raise ValueError("No audio data in response.")
        except json.JSONDecodeError:
            logger.warning("Response is not JSON. Assuming raw base64 audio.")
            base64_audio = response.content.strip(b'"')  # Handle raw base64-encoded data

        # Decode base64 audio
        try:
            audio_data = base64.b64decode(base64_audio)
        except base64.binascii.Error as e:
            logger.error(f"Error decoding base64 audio: {e}")
            raise RuntimeError("Failed to decode audio data.")

        # Write audio to temporary file
        output_path = os.path.join(
            "demo_outputs", "generated_audios", f"{next(tempfile._get_candidate_names())}.{output_format}"
        )
        with open(output_path, "wb") as fp:
            fp.write(audio_data)

        logger.info(f"Audio saved at {output_path}")
        return output_path

    except requests.RequestException as e:
        logger.error(f"Error during TTS generation: {e}")
        raise RuntimeError("Failed to communicate with TTS server.")
    except Exception as e:
        logger.exception(f"Unexpected error during TTS generation: {e}")
        raise RuntimeError("Audio generation failed.")


def concatenate_audios(audio_paths, title, output_format="wav", output_name="combined_audio"):
    """
    Combine the title audio and multiple audio files into a single file with optional silence padding.

    Args:
        audio_paths (list): List of audio file paths to combine.
        title (str): Title to include as the first part of the audio.
        output_format (str): Output file format (default is "wav").
        output_name (str): Name of the combined output file (default is "combined_audio").

    Returns:
        str: Path to the combined audio file.
    """
    logger.debug(f"Combining title and {len(audio_paths)} audio files...")

    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=500)  # Optional: Add 500ms silence between title and sections

    # Generate a temporary audio file for the title
    title_audio_path = generate_title_audio(title, output_format="wav")
    logger.debug(f"Generated title audio at {title_audio_path}")

    # Add title audio to the combined audio
    title_audio = AudioSegment.from_file(title_audio_path)
    combined += title_audio + silence

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


def get_aggregated_content(selected_title, sections):
    """Aggregate content for a given section, including its subsections."""
    content = []
    for section in sections:
        if section["title"] == selected_title:
            content.append(section.get("content", ""))
    return "\n".join(content)




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
