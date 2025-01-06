import binascii
import os
import tempfile
import base64
import json

import ebooklib
import requests
from ebooklib import epub
from bs4 import BeautifulSoup
import gradio as gr
from pydub import AudioSegment

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
    LANGUAGES = requests.get(SERVER_URL + "/languages").json()
    print("Available languages:", ", ".join(LANGUAGES))
    STUDIO_SPEAKERS = requests.get(SERVER_URL + "/studio_speakers").json()
    print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS.keys()))
except:
    raise Exception("Please make sure the server is running first.")

# Helper Functions

def process_file(file):
    if file.name.endswith('.epub'):
        sections = extract_text_filtered(file.name)
        section_titles = [section["title"] for section in sections]
        return gr.update(choices=section_titles, value=None), sections
    elif file.name.endswith('.txt'):
        with open(file.name, 'r', encoding='utf-8') as f:
            text = f.read()
        return gr.update(choices=[], value=None), [{"title": "Text File Content", "content": text}]
    else:
        return gr.update(choices=[], value=None), []


def extract_text_filtered(epub_file):
    book = epub.read_epub(epub_file, ignore_ncx=False)

    sections = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            body = soup.find('body')
            if not body:
                continue
            for tag in body.find_all(['h1', 'h2', 'h3']):
                section_title = tag.get_text().strip()
                section_content = []
                for sibling in tag.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3']:
                        break
                    text = sibling.get_text().strip()
                    if text.isdigit() or "Chapter" in text or len(text) < 3:
                        continue
                    section_content.append(text)
                if section_content:
                    sections.append({"title": section_title, "content": "\n".join(section_content)})
    return sections

def text_to_audio(text, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None):
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
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

def split_text_into_chunks(text, max_chars=250, max_tokens=350):
    import re
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

def concatenate_audios(audio_paths):
    combined = AudioSegment.empty()
    for path in audio_paths:
        audio = AudioSegment.from_file(path)
        combined += audio
    output_path = os.path.join("demo_outputs", "generated_audios", "combined_audio.wav")
    combined.export(output_path, format="wav")
    return output_path

def display_section(selected_title, sections):
    for section in sections:
        if section["title"] == selected_title:
            return section["content"]
    return "Section not found."


# Gradio Interface
with gr.Blocks() as demo:
    cloned_speaker_names = gr.State(list(cloned_speakers.keys()))
    sections_state = gr.State([])

    with gr.Row():
        file_input = gr.File(label="Upload Text or EPUB File", file_types=[".epub", ".txt"])

    with gr.Row():
        speaker_type = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
        lang = gr.Dropdown(label="Language", choices=LANGUAGES, value="en")
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

    with gr.Tab("Process Text/EPUB"):
        process_button = gr.Button("Process File")
        section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
        section_preview = gr.Textbox(label="Preview Section Content", lines=10)

        process_button.click(
            process_file,
            inputs=[file_input],
            outputs=[section_titles, sections_state]
        )

        section_titles.change(
            display_section,
            inputs=[section_titles, sections_state],
            outputs=[section_preview]
        )

    with gr.Tab("Generate Audio"):
        generate_audio_button = gr.Button("Generate Audio")
        audio_output = gr.Audio(label="Generated Audio")

        generate_audio_button.click(
            text_to_audio,
            inputs=[section_preview, lang, speaker_type, speaker_name_studio, speaker_name_custom],
            outputs=[audio_output]
        )

    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )
