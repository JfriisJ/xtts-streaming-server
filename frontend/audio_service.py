import os
import base64
import re
import shutil
import logging
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


def test_tts(text, lang, speaker_type, speaker_name_studio=None, speaker_name_custom=None, stream=False):
    """
    Test the TTS functionality with provided parameters.
    """
    try:
        start_time = time.time()
        embeddings = get_speaker_embeddings(speaker_type,
                                            speaker_name_studio if speaker_type == "Studio" else speaker_name_custom)

        endpoint = "/tts_stream" if stream else "/tts"
        payload = {
            "text": text,
            "language": lang,
            "speaker_embedding": embeddings.get("speaker_embedding"),
            "gpt_cond_latent": embeddings.get("gpt_cond_latent")
        }
        if stream:
            payload["add_wav_header"] = True
            payload["stream_chunk_size"] = "10"

        logger.info(f"Sending TTS request to {SERVER_URL + endpoint} with payload: {payload}")
        response = requests.post(SERVER_URL + endpoint, json=payload, stream=stream)

        if response.status_code == 200:
            logger.info(
                f"TTS request ({'streaming' if stream else 'normal'}) completed in {time.time() - start_time:.2f} seconds.")
        else:
            logger.error(f"TTS request failed: {response.status_code} - {response.text}")
    except Exception as e:
        logger.exception(f"Error during TTS testing: {e}")


def generate_audio(selected_title, sections, book_title, lang="en", speaker_type="Studio", speaker_name=None):
    """
    Generate audio for a given section of a document.
    """
    logger.info(f"Generating audio for section '{selected_title}' in book '{book_title}'")
    if not selected_title:
        logger.error("No title selected for TTS.")
        raise ValueError("No title selected for TTS.")
    if not sections:
        logger.error("No sections available for TTS.")
        raise ValueError("No sections available for TTS.")

    aggregated_content = get_aggregated_content(selected_title, sections)
    if not aggregated_content:
        logger.error(f"No content found for section: {selected_title}")
        raise ValueError(f"No content found for section: {selected_title}")

    folder_name = clean_filename(book_title)
    folder_path = os.path.join("demo_outputs", "generated_audios", folder_name)
    os.makedirs(folder_path, exist_ok=True)

    try:
        audio_path = text_to_audio(
            text=aggregated_content,
            heading=selected_title,
            lang=lang,
            speaker_type=speaker_type,
            speaker_name=speaker_name,
        )
        if audio_path:
            new_audio_path = os.path.join(folder_path, os.path.basename(audio_path))
            shutil.move(audio_path, new_audio_path)
            logger.info(f"Audio successfully generated and saved at {new_audio_path}")
            return new_audio_path
        else:
            logger.error("Audio generation failed.")
            raise RuntimeError("Audio generation failed.")
    except Exception as e:
        logger.exception(f"Error generating audio: {e}")
        raise RuntimeError(f"Error generating audio: {e}")


def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name=None, output_format="wav"):
    """
    Convert text to audio using the TTS API.
    """
    logger.debug(f"Preparing to generate audio for text: {text[:50]}...")
    first_line = text.splitlines()[0] if text else "Untitled"
    file_name = clean_filename(first_line)

    embeddings = get_speaker_embeddings(speaker_type, speaker_name)
    logger.debug(f"Embeddings fetched for speaker '{speaker_name}': {embeddings}")

    chunks = split_text_into_chunks(heading + "\n" + text)
    logger.info(f"Text split into {len(chunks)} chunks for processing")

    cache_dir = os.path.join("demo_outputs", "cache")
    os.makedirs(cache_dir, exist_ok=True)

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        logger.debug(f"Processing chunk {idx + 1}/{len(chunks)}: {chunk[:50]}...")
        response = requests.post(
            f"{SERVER_URL}/tts",
            json={
                "text": chunk,
                "language": lang,
                "speaker_embedding": embeddings.get("speaker_embedding"),
                "gpt_cond_latent": embeddings.get("gpt_cond_latent"),
            },
        )
        if response.status_code != 200:
            logger.error(f"Server error for chunk {idx + 1}: {response.status_code} - {response.text}")
            raise RuntimeError(f"Error: Server returned status {response.status_code} for chunk: {chunk}")

        decoded_audio = base64.b64decode(response.content)
        audio_path = os.path.join(cache_dir, f"{file_name}_{idx + 1}.wav")
        with open(audio_path, "wb") as fp:
            fp.write(decoded_audio)
            cached_audio_paths.append(audio_path)

    if cached_audio_paths:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        shutil.rmtree(cache_dir)
        logger.info(f"Audio chunks combined into file: {combined_audio_path}")
        return combined_audio_path
    else:
        logger.error("No audio chunks generated.")
        raise RuntimeError("No audio chunks generated.")


def concatenate_audios(audio_paths, output_format="wav"):
    """
    Combine multiple audio files into a single file.
    """
    logger.debug(f"Combining {len(audio_paths)} audio files...")
    combined = AudioSegment.empty()
    for path in audio_paths:
        logger.debug(f"Adding audio file: {path}")
        audio = AudioSegment.from_file(path)
        combined += audio

    output_path = os.path.join("demo_outputs", "generated_audios", f"combined_audio_temp.{output_format}")
    combined.export(output_path, format=output_format)
    logger.debug(f"Combined audio saved to: {output_path}")
    return output_path


def split_text_into_chunks(text, max_chars=250, max_tokens=350):
    """
    Split text into manageable chunks for TTS processing.
    """
    sentences = re.split(r"(?<=\.) ", text)
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        sentence_tokens = len(sentence) // 4
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


def clean_filename(filename):
    """
    Clean a string to make it safe for use as a filename.
    """
    clean_name = re.sub(r'[<>:"/\\|?*]', "_", filename).strip()
    logger.debug(f"Cleaned filename: {clean_name}")
    return clean_name


def get_aggregated_content(selected_title, sections):
    """
    Aggregate content for a given section, including its subsections.
    """
    logger.debug(f"Aggregating content for title: {selected_title}")
    aggregated_content = []

    def collect_content(section, include=False):
        if section.get("title") == selected_title:
            include = True

        if include:
            aggregated_content.append(section.get("content", ""))

        for subsection in section.get("subsections", []):
            collect_content(subsection, include)

    for section in sections:
        collect_content(section)

    aggregated_text = "\n\n".join(filter(None, aggregated_content))
    logger.debug(f"Aggregated content length: {len(aggregated_text)}")
    return aggregated_text


def get_speaker_embeddings(speaker_type, speaker_name):
    """
    Get speaker embeddings based on type and name.
    """
    logger.debug(f"Fetching embeddings for speaker type '{speaker_type}' and name '{speaker_name}'")
    url = f"{SERVER_URL}/studio_speakers" if speaker_type == "Studio" else f"{SERVER_URL}/cloned_speakers"
    response = requests.get(url)
    if response.status_code == 200:
        speakers = response.json()
        embeddings = speakers.get(speaker_name, {})
        if not embeddings:
            logger.warning(f"Speaker '{speaker_name}' not found in {speaker_type} speakers.")
        logger.debug(f"Embeddings fetched: {embeddings}")
        return embeddings
    else:
        logger.error(f"Failed to fetch speaker embeddings: {response.status_code} - {response.text}")
        raise RuntimeError(f"Failed to fetch speaker embeddings: {response.status_code} - {response.text}")

def fetch_languages_and_speakers():
    """
    Fetch available languages and speakers from the TTS server.

    Returns:
        tuple: (languages, studio_speakers, cloned_speakers)
    """
    try:
        print("Getting metadata from server ...")

        # Fetch languages
        languages_response = requests.get(f"{SERVER_URL}/languages")
        if languages_response.status_code == 200:
            LANGUAGES = languages_response.json()
            print("Available languages:", ", ".join(LANGUAGES))
        else:
            raise Exception(f"Failed to fetch languages: {languages_response.status_code} - {languages_response.text}")

        # Fetch speakers
        speakers_response = requests.get(f"{SERVER_URL}/studio_speakers")
        if speakers_response.status_code == 200:
            SPEAKERS = speakers_response.json()
            STUDIO_SPEAKERS = SPEAKERS.get("studio_speakers", [])
            CLONED_SPEAKERS = SPEAKERS.get("cloned_speakers", [])
            print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS))
            print("Available cloned speakers:", ", ".join(CLONED_SPEAKERS))
        else:
            raise Exception(f"Failed to fetch speakers: {speakers_response.status_code} - {speakers_response.text}")

        return LANGUAGES, STUDIO_SPEAKERS, CLONED_SPEAKERS
    except Exception as e:
        raise Exception(f"Error fetching metadata from server: {e}")
