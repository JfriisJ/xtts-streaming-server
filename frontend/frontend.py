import os
import time
import gradio as gr
import logging

import requests

from audio_service import generate_audio, fetch_languages_and_speakers, clone_speaker
from text_service import extract_odt_structure



# Ensure the logs directory exists
os.makedirs('/app/logs', exist_ok=True)

# Environment variables
TTS_API = os.getenv("TTS_API", "http://localhost:8003")

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - {%(pathname)s:%(lineno)d} - %(message)s',
    handlers=[
        logging.FileHandler("/app/logs/frontend_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API Endpoints
TTS_SPEAKERS_API = f"{TTS_API}/studio_speakers"
TTS_LANGUAGES_API = f"{TTS_API}/languages"


# Fetch speaker options
def fetch_speakers():
    try:
        logger.info("Fetching speakers from API.")
        response = requests.get(TTS_SPEAKERS_API)
        if response.status_code == 200:
            data = response.json()
            studio_speakers = data.get("studio_speakers", [])
            cloned_speakers = data.get("cloned_speakers", [])
            logger.info(f"Speakers fetched successfully. Studio: {studio_speakers}, Cloned: {cloned_speakers}")
            return studio_speakers, cloned_speakers
        else:
            logger.error(f"Failed to fetch speakers. Status: {response.status_code}, Response: {response.text}")
            return [], []
    except requests.ConnectionError as e:
        logger.error(f"Connection error while fetching speakers: {e}")
        return [], []
    except Exception as e:
        logger.exception(f"Unexpected error while fetching speakers: {e}")
        return [], []


# Process the uploaded file
def process_file(file):
    if file is None:
        logger.warning("No file uploaded.")
        return gr.update(choices=[], value=None), [], "No file uploaded."

    try:
        logger.info(f"Processing uploaded file: {file.name}")
        extraction_result = extract_odt_structure(file.name)  # Use the local extraction service
        book_title = extraction_result.get("title", "Unknown Book")
        sections = extraction_result.get("sections", [])

        if not sections:
            logger.warning("No sections found in the document.")
            return gr.update(choices=[], value=None), [], "No sections found in the document."

        section_titles = [sec["title"] for sec in sections]
        logger.info(f"Sections extracted: {section_titles}")
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = sections[0]["content"] if sections else "No content available."
        return dropdown_output, sections, initial_preview, book_title
    except Exception as e:
        logger.exception(f"Error processing file: {e}")
        return gr.update(choices=[], value=None), [], f"Error processing file: {e}", "Unknown Book"



# Fetch languages and speakers
try:
    languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()
except Exception as e:
    logger.error(f"Failed to initialize metadata: {e}")
    languages, studio_speakers, cloned_speakers = [], {}, {}

with gr.Blocks() as demo:
    # States for managing sections and cloned speakers
    sections_state = gr.State([])

    with gr.Row():
        file_input = gr.File(label="Upload ODT File", file_types=[".odt"])
        speaker_type = gr.Radio(label="Speaker Type", choices=["Studio", "Cloned"], value="Studio")
        speaker_name_studio = gr.Dropdown(
            label="Studio Speaker",
            choices=list(studio_speakers.keys()),
            value=list(studio_speakers.keys())[0] if studio_speakers else None,
        )
        speaker_name_custom = gr.Dropdown(
            label="Cloned Speaker",
            choices=list(cloned_speakers.keys()),
            value=list(cloned_speakers.keys())[0] if cloned_speakers else None,
        )
        lang = gr.Dropdown(label="Language", choices=languages, value="en")

    # Process ODT Tab
    with gr.Tab("Process ODT"):
        with gr.Column():
            process_button = gr.Button("Process File")
            section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
            section_preview = gr.Textbox(label="Section Content", lines=10, interactive=True)
            tts_button = gr.Button("Generate Audio")
            audio_output = gr.Audio(label="Generated Audio", interactive=False)

    # Define Actions
    # 1. Process File
    file_input.change(
        fn=process_file,
        inputs=[file_input],
        outputs=[section_titles, sections_state, section_preview],
    )

    # 2. Update Section Preview on Title Selection
    section_titles.change(
        fn=lambda selected_title, sections: next(
            (sec["content"] for sec in sections if sec["title"] == selected_title), "No content available."
        ),
        inputs=[section_titles, sections_state],
        outputs=[section_preview],
    )

    # 3. Generate Audio
    tts_button.click(
        fn=lambda selected_title, sections, speaker_type, studio_speaker, custom_speaker, lang: generate_audio(
            selected_title=selected_title,
            sections=sections,
            book_title="Uploaded Book",
            lang=lang,
            speaker_type=speaker_type,
            speaker_name=studio_speaker if speaker_type == "Studio" else custom_speaker,
        ),
        inputs=[section_titles, sections_state, speaker_type, speaker_name_studio, speaker_name_custom, lang],
        outputs=[audio_output],
    )

    demo.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")

