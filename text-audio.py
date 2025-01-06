import binascii

import gradio as gr
import requests
import base64
import tempfile
import json
import os


SERVER_URL = 'http://localhost:8000'
OUTPUT = "./demo_outputs"
cloned_speakers = {}

print("Preparing file structure...")
if not os.path.exists(OUTPUT):
    os.mkdir(OUTPUT)
    os.mkdir(os.path.join(OUTPUT, "cloned_speakers"))
    os.mkdir(os.path.join(OUTPUT, "generated_audios"))
elif os.path.exists(os.path.join(OUTPUT, "cloned_speakers")):
    print("Loading existing cloned speakers...")
    for file in os.listdir(os.path.join(OUTPUT, "cloned_speakers")):
        if file.endswith(".json"):
            with open(os.path.join(OUTPUT, "cloned_speakers", file), "r") as fp:
                cloned_speakers[file[:-5]] = json.load(fp)
    print("Available cloned speakers:", ", ".join(cloned_speakers.keys()))

try:
    print("Getting metadata from server ...")
    LANUGAGES = requests.get(SERVER_URL + "/languages").json()
    print("Available languages:", ", ".join(LANUGAGES))
    STUDIO_SPEAKERS = requests.get(SERVER_URL + "/studio_speakers").json()
    print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS.keys()))
except:
    raise Exception("Please make sure the server is running first.")

from pydub import AudioSegment

def concatenate_audios(audio_paths):
    combined = AudioSegment.empty()
    for path in audio_paths:
        audio = AudioSegment.from_file(path)
        combined += audio
    output_path = os.path.join("demo_outputs", "generated_audios", "combined_audio.wav")
    combined.export(output_path, format="wav")
    return output_path




def split_text_into_chunks(text, max_chars=250, max_tokens=350):
    """
    Split text into chunks of up to max_chars characters and max_tokens tokens,
    ensuring the split happens at sentence boundaries if possible.
    """
    import re
    sentences = re.split(r'(?<=\.) ', text)  # Split by sentences
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        # Estimate token count for the sentence (1 token ≈ 4 characters)
        sentence_tokens = len(sentence) // 4

        # Ensure chunk stays within character and token limits
        if len(current_chunk) + len(sentence) <= max_chars and current_tokens + sentence_tokens <= max_tokens:
            current_chunk += sentence + " "
            current_tokens += sentence_tokens
        else:
            # If a single sentence exceeds the limits, split the sentence itself
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
                # Finalize the current chunk and start a new one
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                current_tokens = sentence_tokens

    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def tts(text, speaker_type, speaker_name_studio, speaker_name_custom, lang):
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[
        speaker_name_custom]
    chunks = split_text_into_chunks(text)
    generated_audio_paths = []

    for chunk in chunks:
        response = requests.post(
            SERVER_URL + "/tts",
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

        generated_audio = response.content
        try:
            decoded_audio = base64.b64decode(generated_audio)
        except binascii.Error as e:
            print(f"Error decoding audio for chunk: {e}")
            continue

        audio_path = os.path.join("demo_outputs", "generated_audios", next(tempfile._get_candidate_names()) + ".wav")
        with open(audio_path, "wb") as fp:
            fp.write(decoded_audio)
            generated_audio_paths.append(audio_path)

    return generated_audio_paths


def text_to_audio(file_path, speaker_type, speaker_name_studio, speaker_name_custom, lang):
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        first_line = lines[0].strip() if lines else "audio_output"  # Use the first line as the file name or a default name
        text = ''.join(lines)

    audio_paths = tts(text, speaker_type, speaker_name_studio, speaker_name_custom, lang)
    if len(audio_paths) > 1:
        combined_audio_path = concatenate_audios(audio_paths)
        # Rename the combined audio file to include the first line
        renamed_path = os.path.join(
            os.path.dirname(combined_audio_path), f"{first_line[:50]}.wav"
        )
        os.rename(combined_audio_path, renamed_path)
        return renamed_path
    elif audio_paths:
        # Rename single audio file to include the first line
        renamed_path = os.path.join(
            os.path.dirname(audio_paths[0]), f"{first_line[:50]}.wav"
        )
        os.rename(audio_paths[0], renamed_path)
        return renamed_path

    return "Error: No audio generated."


with gr.Blocks() as demo:
    cloned_speaker_names = gr.State(list(cloned_speakers.keys()))
    with gr.Tab("TTS"):
        with gr.Column() as row4:
            with gr.Row() as col4:
                speaker_name_studio = gr.Dropdown(
                    label="Studio speaker",
                    choices=STUDIO_SPEAKERS.keys(),
                    value="Asya Anara" if "Asya Anara" in STUDIO_SPEAKERS.keys() else None,
                )
                speaker_name_custom = gr.Dropdown(
                    label="Cloned speaker",
                    choices=cloned_speaker_names.value,
                    value=cloned_speaker_names.value[0] if len(cloned_speaker_names.value) != 0 else None,
                )
            speaker_type = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
        with gr.Column() as col2:
            lang = gr.Dropdown(label="Language", choices=LANUGAGES, value="en")
            text = gr.Textbox(label="text", value="A quick brown fox jumps over the lazy dog.")
            tts_button = gr.Button(value="TTS")
        with gr.Column() as col3:
            generated_audio = gr.Audio(label="Generated audio", autoplay=True)
    with gr.Tab("Convert Text to Audio"):
        with gr.Column() as col5:
            text_file = gr.File(label="Upload Text File", type="filepath")
            speaker_type_audio = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
            lang_audio = gr.Dropdown(label="Language", choices=LANUGAGES, value="en")
            speaker_name_studio_audio = gr.Dropdown(
                label="Studio speaker",
                choices=STUDIO_SPEAKERS.keys(),
                value="Asya Anara" if "Asya Anara" in STUDIO_SPEAKERS.keys() else None,
            )
            speaker_name_custom_audio = gr.Dropdown(
                label="Cloned speaker",
                choices=cloned_speaker_names.value,
                value=cloned_speaker_names.value[0] if len(cloned_speaker_names.value) != 0 else None,
            )
            text_to_audio_button = gr.Button(value="Convert to Audio")
        with gr.Column() as col6:
            generated_audio_file = gr.Audio(label="Generated Audio from Text File", autoplay=True)

    tts_button.click(
        fn=tts,
        inputs=[text, speaker_type, speaker_name_studio, speaker_name_custom, lang],
        outputs=[generated_audio],
    )

    text_to_audio_button.click(
        fn=text_to_audio,
        inputs=[text_file, speaker_type_audio, speaker_name_studio_audio, speaker_name_custom_audio, lang_audio],
        outputs=[generated_audio_file],
    )

if __name__ == "__main__":
    print("Warming up server...")
    with open("test/default_speaker.json", "r") as fp:
        warmup_speaker = json.load(fp)
    resp = requests.post(
        SERVER_URL + "/tts",
        json={
            "text": "This is a warmup request.",
            "language": "en",
            "speaker_embedding": warmup_speaker["speaker_embedding"],
            "gpt_cond_latent": warmup_speaker["gpt_cond_latent"],
        }
    )
    resp.raise_for_status()
    print("Starting the demo...")
    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )
