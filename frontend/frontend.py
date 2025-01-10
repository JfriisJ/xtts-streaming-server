import os
import time
import gradio as gr
import logging

import requests

from text_service import extract_odt_structure
from audio_service import generate_audio, fetch_languages_and_speakers, test_tts

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


def handle_tts_test(text, lang, speaker_type, speaker_name_studio, speaker_name_custom, stream):
    if speaker_type == "Studio":
        return test_tts(text, lang, "Studio", speaker_name_studio=speaker_name_studio, stream=stream)
    else:
        return test_tts(text, lang, "Cloned", speaker_name_custom=speaker_name_custom, stream=stream)


# Fetch languages and speakers
try:
    languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()
except Exception as e:
    logger.error(f"Failed to initialize metadata: {e}")
    languages, studio_speakers, cloned_speakers = [], [], []

with gr.Blocks() as demo:
    sections_state = gr.State([])

    with gr.Row():
        file_input = gr.File(label="Upload ODT File", file_types=[".odt"])

    with gr.Tab("Process ODT"):
        with gr.Row():
            with gr.Column():
                process_button = gr.Button("Process File")
                section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
                section_preview = gr.Textbox(label="Section Content", lines=10, interactive=True)
                tts_button = gr.Button("Generate Audio")
                audio_output = gr.Audio(label="Generated Audio", interactive=False)

                speaker_type = gr.Radio(
                    label="Speaker Type",
                    choices=["Studio", "Cloned"],
                    value="Studio",
                    interactive=True
                )
                speaker_name = gr.Dropdown(
                    label="Speaker Name",
                    choices=studio_speakers + cloned_speakers,
                    interactive=True
                )
                lang = gr.Dropdown(
                    label="Language",
                    choices=languages,
                    value=languages[0] if languages else "en",
                    interactive=True
                )

        # File Input Change Action
        file_input.change(
            process_file,
            inputs=[file_input],
            outputs=[section_titles, sections_state, section_preview, gr.State("Unknown Book")],
        )

        # Section Titles Dropdown Change Action
        section_titles.change(
            lambda selected_title, sections: next(
                (sec["content"] for sec in sections if sec["title"] == selected_title), "No content available."),
            inputs=[section_titles, sections_state],
            outputs=[section_preview],
        )

        # TTS Button Click Action
        tts_button.click(
            lambda selected_title, sections, book_title, speaker_type, speaker_name, lang: generate_audio(
                selected_title, sections, book_title, lang, speaker_type, speaker_name
            ),
            inputs=[section_titles, sections_state, gr.State("Unknown Book"), speaker_type, speaker_name, lang],
            outputs=[audio_output],
        )

    with gr.Tab("TTS Test"):
        with gr.Row():
            test_text = gr.Textbox(label="Test Text", lines=2, placeholder="Enter text for TTS testing")
            test_lang = gr.Dropdown(label="Language", choices=languages, value=languages[0] if languages else "en")
            test_speaker_type = gr.Radio(
                label="Speaker Type",
                choices=["Studio", "Cloned"],
                value="Studio",
                interactive=True
            )
            test_speaker_name_studio = gr.Dropdown(
                label="Studio Speaker",
                choices=studio_speakers,
                visible=True,
                interactive=True
            )
            test_speaker_name_custom = gr.Dropdown(
                label="Cloned Speaker",
                choices=cloned_speakers,
                visible=False,
                interactive=True
            )
            stream_option = gr.Checkbox(label="Stream TTS", value=False)
            test_button = gr.Button("Test TTS")

        test_button.click(
            handle_tts_test,
            inputs=[test_text, test_lang, test_speaker_type, test_speaker_name_studio, test_speaker_name_custom, stream_option],
            outputs=[]
        )


    demo.launch(share=False, debug=False, server_port=3009, server_name="localhost")
