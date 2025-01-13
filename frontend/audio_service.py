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

from health_service import AUDIO_SERVICE_API

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
        LANGUAGES = requests.get(f"{AUDIO_SERVICE_API}/languages", timeout=10).json()
        STUDIO_SPEAKERS = requests.get(f"{AUDIO_SERVICE_API}/studio_speakers", timeout=10).json()
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
    """
    Generate audio for each section or subchapter and save files with structured filenames, including titles for empty sections.
    """
    # Determine the folder name based on book or chapter title
    folder_name = clean_filename(selected_title)
    folder_path = os.path.join("outputs", "generated_audios", folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Collect relevant sections
    content_to_generate = []
    if selected_title == book_title:  # Generate for the entire book
        content_to_generate = sections
    else:  # Generate for the selected chapter and its subchapters
        capture_content = False
        for section in sections:
            if section["title"] == selected_title or capture_content:
                content_to_generate.append(section)
                capture_content = True
                # Stop capturing when the next top-level section is reached
                if section["style"] == "Heading 1" and section["title"] != selected_title:
                    break

    if not content_to_generate:
        logger.warning(f"No content found for {selected_title}.")
        return None

    generated_files = []
    for idx, section in enumerate(content_to_generate, start=1):
        section_title = section["title"]
        section_content = section.get("content", "")

        # Handle empty sections by using only the title
        if not section_content.strip():
            logger.warning(f"Section '{section_title}' is empty. Generating audio for title only.")
            section_content = f"This is the section titled {section_title}."  # Customize this template if needed

        # Generate filename
        file_name = f"{str(idx).zfill(2)}_{clean_filename(section_title)}.{output_format}"
        file_path = os.path.join(folder_path, file_name)

        logger.info(f"Generating audio for section: {section_title}")

        # Call TTS service to generate audio
        audio_path = text_to_audio(
            title=book_title,
            heading=section_title,
            text=section_content,
            language=language,
            studio_speaker=studio_speaker,
            speaker_type=speaker_type,
            output_format=output_format
        )

        if audio_path:
            new_audio_path = os.path.join(folder_path, os.path.basename(audio_path))
            os.rename(audio_path, file_path)  # Save with structured filename
            generated_files.append(file_path)
            logger.info(f"Audio saved as: {file_path}")
        else:
            logger.error(f"Audio generation failed for section: {section_title}")

    return generated_files



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


