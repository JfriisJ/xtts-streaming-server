import base64
import json
import logging
import os
import re
import shutil
import uuid
import time

import nltk
nltk.download('punkt_tab', quiet=True)
from nltk.tokenize import sent_tokenize
import requests
from pydub import AudioSegment
from transformers import GPT2TokenizerFast

from health_service import AUDIO_SERVICE_API, check_service_health

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


# Check connection to audio service, if not connected retry in 5 seconds
print ("Checking audio service connection...")
while True:
    if check_service_health().get("Audio Service", {}).get("status") == "Connected":
        print ("Audio service connected")
        LANGUAGES = requests.get(f"{AUDIO_SERVICE_API}/languages").json()
        STUDIO_SPEAKERS = requests.get(f"{AUDIO_SERVICE_API}/studio_speakers").json()
        CLONED_SPEAKERS = {}
        print (LANGUAGES)
        print (STUDIO_SPEAKERS.keys())
        logger.info("Audio service connected.")
        break
    logger.warning("Audio service not connected. Retrying in 5 seconds...")
    time.sleep(5)

print("Preparing file structure...")
if not os.path.exists(OUTPUT):
    os.mkdir(OUTPUT)
    os.mkdir(os.path.join(OUTPUT, "cloned_speakers"))
    os.mkdir(os.path.join(OUTPUT, "generated_audios"))


def generate_audio(book_title, selected_title, sections, language="en", studio_speaker="Asya Anara", speaker_type="Studio", output_format="wav"):
    if not selected_title:
        logger.warning("No title selected for TTS.")
        return None

    if not sections:
        logger.warning("No sections available for TTS.")
        return None

    # Create folder named after the book title
    folder_name = clean_filename(book_title)
    folder_path = os.path.join("outputs", "generated_audios", folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Generate audio
    try:
        logger.info(f"Generating audio for: {selected_title}")
        audio_path = text_to_audio(
            title=book_title,
            heading=selected_title,
            text=sections,
            language=language,  # Default to English
            studio_speaker=studio_speaker,
            speaker_type=speaker_type,
            output_format=output_format  # Default to WAV format
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

def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(AUDIO_SERVICE_API + "/clone_speaker", files=files).json()
    with open(os.path.join(OUTPUT, "cloned_speakers", clone_speaker_name + ".json"), "w") as fp:
        json.dump(embeddings, fp)
    CLONED_SPEAKERS[clone_speaker_name] = embeddings
    cloned_speaker_names.append(clone_speaker_name)



def text_to_audio(title, heading, text, language, studio_speaker, speaker_type, output_format):
    """Generate audio using the TTS server."""
    file_name = clean_filename(heading or "Untitled")
    if speaker_type == "Studio":
        embeddings = STUDIO_SPEAKERS.get(studio_speaker, {})
    else:
        embeddings = CLONED_SPEAKERS.get(studio_speaker, {})
    if not embeddings:
        logger.error("Speaker embeddings not found.")
        return None


    text = str(text)  # Join list elements with newlines
    heading = str(heading)  # Convert heading to string if not already

    logger.info(f"Generating audio for: {heading} {text}...")
    # Split text into chunks for processing
    try:
        chunks = split_text_into_chunks(heading + "\n\n" + text)
    except Exception as e:
        logger.error(f"Error splitting text into chunks: {e}")
        return None

    cache_dir = os.path.join("outputs", "cache")
    os.makedirs(cache_dir, exist_ok=True)

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        try:
            response = requests.post(
                AUDIO_SERVICE_API + "/tts",
                json={
                    "text": chunk,
                    "language": language,
                    "speaker_embedding": embeddings["speaker_embedding"],
                    "gpt_cond_latent": embeddings["gpt_cond_latent"]
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
        combined_audio_path = concatenate_audios(cached_audio_paths, title, output_format)
        final_path = os.path.join("outputs", "generated_audios", f"{file_name}_{uuid.uuid4().hex}.{output_format}")
        shutil.move(combined_audio_path, final_path)
        shutil.rmtree(cache_dir)
        return final_path
    else:
        logger.error("No audio chunks were successfully generated.")
        return None


def concatenate_audios(audio_paths, title, output_format="wav"):
    logger.debug(f"Combining title and {len(audio_paths)} audio files...")

    # Initialize combined audio and silence
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=500)  # Optional: Add 500ms silence between title and sections

    # Add section audios to the combined audio
    for path in audio_paths:
        logger.debug(f"Adding audio file: {path}")
        audio = AudioSegment.from_file(path)
        combined += audio + silence

    # Export the final combined audio
    output_path = os.path.join("outputs", "generated_audios", f"{title}.{output_format}")
    combined.export(output_path, format=output_format)
    logger.debug(f"Combined audio saved to: {output_path}")

    return output_path


def split_text_into_chunks(text, max_chars=250, max_tokens=350):


    # Initialize tokenizer (adjust as needed for your language model)
    tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")
    sentences = sent_tokenize(text)  # Better sentence splitting
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        # Estimate tokens for the sentence using the tokenizer
        sentence_tokens = len(tokenizer.encode(sentence, add_special_tokens=False))

        if len(current_chunk) + len(sentence) <= max_chars and current_tokens + sentence_tokens <= max_tokens:
            current_chunk += sentence + " "
            current_tokens += sentence_tokens
        else:
            # If the sentence exceeds the limit, split it into smaller pieces
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
                # Add the current chunk to the list and start a new chunk
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                current_tokens = sentence_tokens

    # Append the last chunk if it's non-empty
    if current_chunk:
        chunks.append(current_chunk.strip())

    # Debugging output
    logger.debug(f"Split text into {len(chunks)} chunks: {[chunk[:50] for chunk in chunks]}")

    return chunks


def fetch_languages_and_speakers():
    """Fetch available languages and speakers from the TTS server."""
    try:
        logger.info("Fetching languages and speakers.")
        languages = LANGUAGES
        studio_speakers = STUDIO_SPEAKERS
        cloned_speakers = {}  # Initialize empty cloned speakers if not fetched
        return languages, studio_speakers, cloned_speakers
    except Exception as e:
        logger.error(f"Error fetching metadata: {e}")
        return {}, {}, {}


def clean_filename(filename):
    clean_name = re.sub(r'[<>:"/\\|?*\n\r]', "_", filename).strip()
    return clean_name or "default_filename"


