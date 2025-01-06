import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
import gradio as gr
import requests
import tempfile
import base64
import json


# Helper Function to Extract and Filter Text from EPUB
def extract_text_filtered(epub_file):
    book = epub.read_epub(epub_file)
    sections = []

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            body = soup.find('body')

            if not body:
                continue

            # Filter out headers and footers based on heuristics
            for tag in body.find_all(['h1', 'h2', 'h3']):
                section_title = tag.get_text().strip()
                section_content = []

                # Collect content until the next heading
                for sibling in tag.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3']:
                        break  # Stop at the next section
                    text = sibling.get_text().strip()
                    if text.isdigit() or "Chapter" in text or len(text) < 3:
                        continue  # Skip headers, footers, and irrelevant text
                    section_content.append(text)

                if section_content:
                    sections.append({"title": section_title, "content": "\n".join(section_content)})

    return sections


# Helper Function to Convert Text to Audio
def text_to_audio(text, lang="en", speaker="default_speaker"):
    SERVER_URL = 'http://localhost:8000'
    response = requests.post(
        f"{SERVER_URL}/tts",
        json={"text": text, "language": lang, "speaker": speaker}
    )

    if response.status_code != 200:
        return None, f"Error: {response.status_code}"

    audio_data = base64.b64decode(response.content)
    audio_path = os.path.join(tempfile.gettempdir(), "output.wav")
    with open(audio_path, 'wb') as f:
        f.write(audio_data)

    return audio_path, None


# Gradio Interface
def process_epub(epub_file):
    sections = extract_text_filtered(epub_file.name)
    section_titles = [section["title"] for section in sections]
    return gr.update(choices=section_titles, value=None), sections


def display_section(selected_title, sections):
    for section in sections:
        if section["title"] == selected_title:
            return section["content"]
    return "Section not found."


def generate_audio(selected_section, lang, speaker):
    audio_path, error = text_to_audio(selected_section, lang, speaker)
    if error:
        return None, error
    return audio_path, None


with gr.Blocks() as demo:
    sections_state = gr.State([])  # To store sections data

    with gr.Row():
        epub_file = gr.File(label="Upload EPUB File", file_types=[".epub"])

    process_button = gr.Button("Process EPUB")
    section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
    section_preview = gr.Textbox(label="Preview Section Content", lines=10)

    with gr.Row():
        lang = gr.Dropdown(label="Language", choices=["en", "es", "fr"], value="en")
        speaker = gr.Textbox(label="Speaker", value="default_speaker")
        generate_audio_button = gr.Button("Generate Audio")

    audio_output = gr.Audio(label="Generated Audio")

    # Update section titles and sections state when EPUB is processed
    process_button.click(
        process_epub,
        inputs=[epub_file],
        outputs=[section_titles, sections_state],
    )

    # Display content of selected section
    section_titles.change(
        display_section,
        inputs=[section_titles, sections_state],
        outputs=[section_preview],
    )

    # Generate audio for the selected section
    generate_audio_button.click(
        generate_audio,
        inputs=[section_preview, lang, speaker],
        outputs=[audio_output],
    )

demo.launch()
