import os
import logging
import time

import gradio as gr
import requests

from audio_service import generate_audio, fetch_languages_and_speakers, health_check as audio_health_check
from text_service import extract_odt_structure, health_check as text_health_check

# Logging configuration
os.makedirs('/app/logs', exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/frontend_api.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)



def check_service_health():
    services = {
        "Audio Service": audio_health_check,
        "Text Service": text_health_check
        # Add similar health checks for other services if defined
        # For example: "Text Service": text_health_check
    }
    status = {}
    for service_name, health_function in services.items():
        try:
            response = health_function()
            if response.get("status") == "healthy":
                status[service_name] = "Connected"
            else:
                status[service_name] = f"Disconnected ({response.get('error', 'Unknown Error')})"
        except Exception as e:
            logger.warning(f"Service {service_name} health check failed: {e}")
            status[service_name] = "Disconnected"
    return status

# Function to get the connection status
def update_connection_status():
    status = check_service_health()
    all_connected = all(value == "Connected" for value in status.values())
    if all_connected:
        return "All Services Connected"
    else:
        return "\n".join([f"{k}: {v}" for k, v in status.items()])

# Fetch metadata after verifying service connection
def fetch_metadata_if_connected(retries=5, delay=5):
    for _ in range(retries):
        try:
            if all(status == "Connected" for status in check_service_health().values()):
                languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()

                # Sanitize languages for dropdown
                languages = [str(lang) for lang in languages]
                logger.debug(f"Fetched languages for dropdown: {languages}")
                logger.debug(f"Fetched studio speakers: {list(studio_speakers.keys())[:5]}")
                logger.debug(f"Fetched cloned speakers: {list(cloned_speakers.keys())[:5]}")

                return languages, studio_speakers, cloned_speakers
        except Exception as e:
            logger.warning(f"Retrying metadata fetch: {e}")
            time.sleep(delay)

    logger.error("Failed to fetch metadata after retries.")
    return ["en"], {}, {}  # Fallback to English as default language

# Initial metadata setup
languages, studio_speakers, cloned_speakers = fetch_metadata_if_connected()

# File processing handler
def process_file(file):
    if not file:
        return "No file uploaded.", gr.update(choices=[]), None, "", ""

    try:
        logger.info(f"Processing file: {file.name}")
        result = extract_odt_structure(file.name)  # Process the ODT file
        title = result.get("title", file.name)
        sections = result.get("sections", [])
        section_titles = [section["title"] for section in sections]

        logger.debug(f"Extracted sections: {sections[:5]}")  # Log extracted sections for debugging

        # Return the title to be displayed in the book_title textbox
        return title, gr.update(choices=section_titles), sections, section_titles[0] if section_titles else "", title
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return f"Error: {e}", gr.update(choices=[]), None, "", ""



# Section content preview
def preview_section(selected_title, sections):
    if not sections:  # Handle None or empty sections
        logger.warning("No sections available to preview.")
        return "No sections available to preview."

    logger.debug(f"Selected title: {selected_title}")
    logger.debug(f"Available sections: {[section['title'] for section in sections]}")

    for section in sections:
        if section["title"] == selected_title:
            logger.debug(f"Found content for section '{selected_title}': {section['content'][:5]}")  # Log first 100 chars
            return section["content"]

    logger.warning(f"No content found for section '{selected_title}'.")
    return "No content available."

# Frontend interface
with gr.Blocks() as demo:
    sections_state = gr.State([])
    # Connection status Textbox
    connection_status = gr.Textbox(label="Service Status", value="Checking...", interactive=False)

    # Timer component for periodic updates
    timer = gr.Timer(value=5)

    # Set up the tick event to update the connection status
    timer.tick(update_connection_status, inputs=[], outputs=[connection_status])  # Corrected here

    # Inputs
    with gr.Row():
        file_input = gr.File(label="Upload ODT File", file_types=[".odt"])
        speaker_type = gr.Radio(label="Speaker Type", choices=["Studio", "Cloned"], value="Studio")
        studio_dropdown = gr.Dropdown(label="Studio Speaker", choices=list(studio_speakers.keys()))
        lang_dropdown = gr.Dropdown(label="Language", choices=languages, value="en")


    # File processing and preview
    with gr.Row():
        with gr.Column():
            process_btn = gr.Button("Process File")
            book_title = gr.Textbox(label="Book Title", value="")
            section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True)
        section_preview = gr.Textbox(label="Section Content", lines=10, interactive=True)

    # TTS generation
    tts_button = gr.Button("Generate Audio")
    audio_output = gr.Audio(label="Generated Audio")

    # Interactivity
    file_input.change( process_file, inputs=[file_input], outputs=[book_title, section_titles, sections_state, section_preview])
    section_titles.change(preview_section, inputs=[section_titles, sections_state], outputs=[section_preview])
    process_btn.click(process_file, inputs=[file_input], outputs=[book_title, section_titles, sections_state, section_preview])
    tts_button.click(
        generate_audio,
        inputs=[section_titles, sections_state, book_title, lang_dropdown, speaker_type, studio_dropdown],
        outputs=[audio_output],
    )

    demo.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")
