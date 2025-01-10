import json
import os
import base64
import re
import shutil
import logging
import tempfile
import time

from pydub import AudioSegment
import requests

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Base server URL for TTS processing
SERVER_URL = os.getenv("TTS_API", "http://localhost:8003")

# Fetch metadata (languages and speakers)
try:
    print("Fetching metadata from server ...")
    LANGUAGES = requests.get(SERVER_URL + "/languages").json()
    print("Available languages:", ", ".join(LANGUAGES))
    STUDIO_SPEAKERS = requests.get(SERVER_URL + "/studio_speakers").json()
    print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS.keys()))
except Exception as e:
    raise Exception(f"Error fetching metadata: {e}")

# Initialize cloned speakers (starts empty)
CLONED_SPEAKERS = {}

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
    Generate audio for a given section of a document, including the title and section content.

    Args:
        selected_title (str): Title of the section to generate audio for.
        sections (list): List of sections extracted from the document.
        book_title (str): Title of the book/document.
        lang (str): Language of the TTS.
        speaker_type (str): Speaker type ("Studio" or "Cloned").
        speaker_name (str): Name of the speaker to use.

    Returns:
        str: Path to the final combined audio file.
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

    # Generate audio for each chunk
    folder_path = os.path.join("demo_outputs", "generated_audios", clean_filename(book_title))
    os.makedirs(folder_path, exist_ok=True)

    audio_paths = []
    try:
        for idx, chunk in enumerate(chunks):
            logger.info(f"Processing chunk {idx + 1}/{len(chunks)}: {chunk[:50]}...")
            audio_path = text_to_audio(
                text=chunk,
                lang=lang,
                speaker_type=speaker_type,
                speaker_name=speaker_name,
                output_format="wav",
            )
            audio_paths.append(audio_path)
            logger.info(f"Audio for chunk {idx + 1} saved at {audio_path}.")

        # Combine all chunk audios into a single file, including the title
        final_audio_path = concatenate_audios(audio_paths, title=selected_title,
                                              output_name=clean_filename(selected_title))
        logger.info(f"Final combined audio saved at {final_audio_path}")

        # Clean up intermediate chunk audio files
        for path in audio_paths:
            os.remove(path)

        return final_audio_path
    except Exception as e:
        logger.exception(f"Error generating audio: {e}")
        raise RuntimeError("Audio generation failed.")


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
        response = requests.post(f"{SERVER_URL}/tts", json=payload, timeout=30)
        response.raise_for_status()

        try:
            response_data = response.json()
        except ValueError:
            logger.error(f"Non-JSON response from TTS server: {response.content}")
            raise RuntimeError("Invalid response from TTS server.")

        if "audio" not in response_data:
            logger.error(f"Missing 'audio' in TTS response: {response_data}")
            raise RuntimeError("Invalid TTS server response: 'audio' key missing.")

        audio_data = base64.b64decode(response_data["audio"])
        output_path = os.path.join(
            "demo_outputs", "generated_audios", f"{next(tempfile._get_candidate_names())}.{output_format}"
        )
        with open(output_path, "wb") as fp:
            fp.write(audio_data)
        return output_path
    except requests.RequestException as e:
        logger.error(f"Request error during TTS generation: {e}")
        raise RuntimeError("TTS generation failed.")



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
    """
    Split text into manageable chunks for TTS processing.

    Args:
        text (str): The text to split into chunks.
        max_chars (int): Maximum characters allowed in a single chunk.
        max_tokens (int): Maximum tokens allowed in a single chunk.

    Returns:
        list: List of text chunks.
    """
    sentences = re.split(r"(?<=\.) ", text)  # Split text into sentences
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = len(sentence) // 4  # Approximate token count (4 chars/token)
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
    """Get speaker embeddings based on type and name."""
    url = f"{SERVER_URL}/studio_speakers" if speaker_type == "Studio" else f"{SERVER_URL}/cloned_speakers"
    response = requests.get(url)
    response.raise_for_status()
    speakers = response.json()
    if speaker_name not in speakers:
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
    """Clean a string to make it safe for use as a filename."""
    return re.sub(r'[<>:"/\\|?*]', "_", filename).strip()


def get_aggregated_content(selected_title, sections):
    """Aggregate content for a given section, including its subsections."""
    content = []
    for section in sections:
        if section["title"] == selected_title:
            content.append(section.get("content", ""))
    return "\n".join(content)


def generate_title_audio(title, lang="en", speaker_type="Studio", speaker_name="default_speaker", output_format="wav"):
    """
    Generate a temporary audio file for the title using TTS.

    Args:
        title (str): Title text to generate audio for.
        lang (str): Language for the TTS.
        speaker_type (str): Speaker type ("Studio" or "Cloned").
        speaker_name (str): Speaker name to use for TTS.
        output_format (str): Audio format for the output file.

    Returns:
        str: Path to the generated title audio file.
    """
    logger.info(f"Generating audio for title: {title}")

    # Fetch embeddings for the speaker
    embeddings = get_speaker_embeddings(speaker_type, speaker_name)

    # Payload for the TTS request
    payload = {
        "text": title,
        "language": lang,
        "speaker_embedding": embeddings.get("speaker_embedding"),
        "gpt_cond_latent": embeddings.get("gpt_cond_latent"),
    }

    try:
        response = requests.post(f"{SERVER_URL}/tts", json=payload)
        response.raise_for_status()
        audio_data = base64.b64decode(response.content)
        temp_audio_path = os.path.join(tempfile.gettempdir(),
                                       f"{next(tempfile._get_candidate_names())}.{output_format}")
        with open(temp_audio_path, "wb") as fp:
            fp.write(audio_data)
        logger.info(f"Title audio generated and saved at {temp_audio_path}")
        return temp_audio_path
    except requests.RequestException as e:
        logger.error(f"Error generating title audio: {e}")
        raise RuntimeError("Failed to generate title audio.")
