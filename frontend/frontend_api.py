import os
import time

import requests
import gradio as gr
import logging

# Ensure the logs directory exists
os.makedirs('/app/logs', exist_ok=True)
TTS_API = os.getenv("TTS_API", "http://localhost:8003")
TEXT_EXTRACTION_API = os.getenv("TEXT_EXTRACTION_API", "http://localhost:8001")

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/app/logs/frontend_api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TTS_SPEAKERS_API = f"{TTS_API}/studio_speakers"
TTS_LANGUAGES_API = f"{TTS_API}/languages"
TTS_HEALTH_API = f"{TTS_API}/health"
EXTRACT_TEXT_API = f"{TEXT_EXTRACTION_API}/process"
EXTRACT_TEXT_HEALTH_API = f"{TEXT_EXTRACTION_API}/health"



# Fetch speaker options
def fetch_speakers():
    try:
        logger.info("Fetching speakers from API")
        response = requests.get(TTS_SPEAKERS_API)
        if response.status_code == 200:
            data = response.json()
            studio_speakers = data.get("studio_speakers", [])
            cloned_speakers = data.get("cloned_speakers", [])
            logger.info(f"Speakers fetched successfully: Studio - {studio_speakers}, Cloned - {cloned_speakers}")
            return studio_speakers, cloned_speakers
        else:
            logger.error(f"Failed to fetch speakers: {response.status_code} - {response.text}")
            return [], []
    except Exception as e:
        logger.exception(f"Error while fetching speakers: {e}")
        return [], []

# Gradio Interface Functions
def process_file(file):
    if file is None:
        logger.warning("No file uploaded.")
        return gr.update(choices=[], value=None), [], "No file uploaded."

    try:
        logger.info(f"Processing uploaded file: {file.name}")
        response = requests.post(EXTRACT_TEXT_API, files={'file': file})
        if response.status_code == 200:
            data = response.json()
            sections = data.get('sections', [])
            book_title = data.get('title', "Unknown Book")
            if not sections:
                logger.warning("No sections found in the document.")
                return gr.update(choices=[], value=None), [], "No sections found in the document."

            section_titles = [sec["title"] for sec in sections]
            logger.info(f"Sections extracted: {section_titles}")
            dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
            initial_preview = sections[0]["content"] if sections else "No content available."
            return dropdown_output, sections, initial_preview, book_title
        else:
            logger.error(f"Error processing file: {response.status_code} - {response.text}")
            return gr.update(choices=[], value=None), [], "Error processing file.", "Unknown Book"
    except Exception as e:
        logger.exception(f"Error processing file: {e}")
        return gr.update(choices=[], value=None), [], f"Error processing file: {e}", "Unknown Book"

def generate_audio(selected_title, sections, book_title, speaker_type, speaker_name, lang):
    if not selected_title:
        logger.warning("No title selected for TTS.")
        return None

    if not sections:
        logger.warning("No sections available for TTS.")
        return None

    section_content = next((sec["content"] for sec in sections if sec["title"] == selected_title), None)
    if not section_content:
        logger.warning(f"No content found for section: {selected_title}")
        return None

    try:
        payload = {
            "text": section_content,
            "title": selected_title,
            "book_title": book_title,
            "language": lang,
            "speaker_type": speaker_type,
            "speaker_name": speaker_name
        }
        logger.info(f"Sending TTS request with payload: {payload}")
        response = requests.post(TTS_API, json=payload)
        if response.status_code == 200:
            audio_file = f"{selected_title.replace(' ', '_')}.wav"
            with open(audio_file, "wb") as f:
                f.write(response.content)
            logger.info(f"Audio file generated: {audio_file}")
            return audio_file
        else:
            logger.error(f"TTS API error: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logger.exception(f"Error generating audio: {e}")
        return None

# Initialize speaker options
logger.info("Initializing speaker options")
studio_speakers, cloned_speakers = fetch_speakers()

# Gradio Interface
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
                lang = gr.Dropdown(label="Language", choices=["en", "es", "fr"], value="en", interactive=True)

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
            generate_audio,
            inputs=[section_titles, sections_state, gr.State("Unknown Book"), speaker_type, speaker_name, lang],
            outputs=[audio_output],
        )

    demo.launch(share=False, debug=False, server_port=3009, server_name="localhost")
