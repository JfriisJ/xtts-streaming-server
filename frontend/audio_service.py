import base64
import json
import logging
import os
import re
import shutil
import time

import requests
from pydub import AudioSegment

from health_service import XTTS_SERVER_API

# Setup logging
logging.basicConfig(
    level=logging.INFO,
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

    if not selected_title:
        print("No title selected for TTS.")
        return None

    if not sections:
        print("No sections available for TTS.")
        return None

    # Aggregate content for the selected title
    aggregated_content = get_aggregated_content(selected_title, sections)
    if not aggregated_content:
        print(f"No content found for section: {selected_title}")
        return None

    # Create folder named after the book title
    folder_name = clean_filename(book_title)
    folder_path = os.path.join("outputs", "generated_audios", folder_name)
    os.makedirs(folder_path, exist_ok=True)



    # Generate audio
    try:
        print(f"Generating audio for: {selected_title}")
        audio_path = text_to_audio(
            text=aggregated_content,
            heading=selected_title,
            lang=language,  # Default to English
            speaker_type=speaker_type,  # Default speaker type
            speaker_name_studio=studio_speaker,  # Default studio speaker
            speaker_name_custom=None  # No custom speaker by default
        )

        # Move the audio to the folder
        if audio_path:
            new_audio_path = os.path.join(folder_path, os.path.basename(audio_path))
            shutil.move(audio_path, new_audio_path)
            print(f"Audio saved to: {new_audio_path}")
            return new_audio_path
        else:
            print("Audio generation failed.")
            return None
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None



def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(XTTS_SERVER_API + "/clone_speaker", files=files).json()
    with open(os.path.join(OUTPUT, "cloned_speakers", clone_speaker_name + ".json"), "w") as fp:
        json.dump(embeddings, fp)
    CLONED_SPEAKERS[clone_speaker_name] = embeddings
    cloned_speaker_names.append(clone_speaker_name)

def get_aggregated_content(selected_title, sections, include_subsections=True):
    aggregated_content = []

    def collect_content(section, include, depth=0):
        indent = "  " * depth
        if section.get("title") == selected_title:
            include = True
            print(f"{indent}*** Matched section: '{section['title']}' (Style: {section.get('style', 'Unknown Style')})")

        if include:
            aggregated_content.append(section.get("content", ""))

        for subsection in section.get("subsections", []):
            collect_content(subsection, include, depth + 1)

    for section in sections:
        collect_content(section, include=False)

    return "\n\n".join(filter(None, aggregated_content))

def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None, output_format="wav"):
    # Get the first line as the file name
    file_name = clean_filename(heading)
    print(f"file_name: {file_name}")

    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == "Studio" else CLONED_SPEAKERS[speaker_name_custom]
    chunks = split_text_into_chunks(heading + "\n\n" + text)

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
    Kombinerer flere lydfiler til én og eksporterer i det valgte format.
    """
    combined = AudioSegment.empty()
    for path in audio_paths:
        audio = AudioSegment.from_file(path)
        combined += audio

    output_path = os.path.join("outputs", "generated_audios", f"combined_audio_temp.{output_format}")
    combined.export(output_path, format=output_format)
    return output_path


def split_text_into_chunks(text, max_chars=250, max_tokens=350):

    sentences = re.split(r'(?<=\.) ', text)
    chunks = []
    current_chunk = ""
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = len(sentence) // 4
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
    return chunks


def clean_filename(filename):
    """
    Cleans the filename by removing or replacing invalid characters.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()




