import json
import os
import logging

import gradio as gr

from audio_service import generate_audio,  clone_speaker, CLONED_SPEAKERS, LANGUAGES, STUDIO_SPEAKERS
from health_service import check_service_health
from text_service import extract_text_from_file

# Logging configuration
os.makedirs('/app/logs', exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/frontend_api.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Function to get the connection status
def update_connection_status():
    status = check_service_health()  # Call the health check function

    # Create a status summary for disconnected services
    status_summary = []
    for service_name, service_status in status.items():
        status_summary.append(f"{service_name}: {service_status['status']}")
    return "\n".join(status_summary)


# File processing handler
def process_file(file):
    if not file:
        return "No file uploaded.", gr.update(choices=[]), None, "", ""

    try:
        logger.info(f"Processing file: {file.name}")
        result = extract_text_from_file(file.name)  # Send file to text_service

        # Extract title and sections
        # Extract sections
        result = extract_text_from_file(file.name)
        book_title = result.get("title", file.name)
        sections = result.get("sections", [])
        # title = result.get("title", file.name)
        # sections = result.get("sections", [])
        # section_titles = [section["title"] for section in sections]

        logger.debug(f"Extracted title: {book_title}")
        logger.debug(f"Extracted sections: {sections[:5]}")  # Log first few sections for clarity
        # Add the book title at the top of the dropdown
        section_titles = [book_title] + [section["title"] for section in sections]

        # Update UI components
        return (
            book_title,
            gr.update(choices=section_titles),
            sections,
            section_titles[0],
            # json.dumps(result, indent=2)
        )
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

def studio_speaker_change(speaker_type):
    if speaker_type == "Studio":
        return STUDIO_SPEAKERS.keys(),"Asya Anara" if "Asya Anara" in STUDIO_SPEAKERS.keys() else None
    return CLONED_SPEAKERS.value, CLONED_SPEAKERS.value[0] if len(CLONED_SPEAKERS.value) != 0 else None,

def speaker_type_change(speaker_type):
    if speaker_type == "Studio":
        return [generated_audio], [book_title, section_titles, sections_state, lang_dropdown, studio_dropdown, speaker_type]
    return [clone_speaker], [upload_file, clone_speaker_name, cloned_speaker_names]


# Frontend interface
with gr.Blocks() as Book2Audio:
    sections_state = gr.State([])
    # Connection status Textbox
    connection_status = gr.Textbox(label="Service Status", value="Checking...", interactive=False)

    # Timer component for periodic updates
    timer = gr.Timer(value=5)

    # Set up the tick event to update the connection status
    timer.tick(update_connection_status, inputs=[], outputs=[connection_status])  # Corrected here
    cloned_speaker_names = gr.State(list(CLONED_SPEAKERS.keys()))
    # Update the UI with JSON viewer
    with gr.Tab("TTS"):
        with gr.Row():
            file_input = gr.File(label="Upload ODT File", file_types=[".odt"])
            speaker_type = gr.Radio(
                label="Speaker Type",
                choices=["Studio", "Cloned"],
                value="Studio"
            )
            studio_dropdown = gr.Dropdown(
                label="Studio speaker",
                choices=studio_speaker_change(speaker_type.value)[0],
                value=studio_speaker_change(speaker_type.value)[1]
            )
            lang_dropdown = gr.Dropdown(
                label="Language",
                choices=LANGUAGES,
                value="en" if "en" in LANGUAGES else None
            )

        # File processing and preview
        with gr.Row():
            with gr.Column():
                process_btn = gr.Button("Process File")
                book_title = gr.Textbox(label="Book Title", value="Unknown Book", interactive=False)
                section_titles = gr.Dropdown(label="Select Section", choices=[0], interactive=True)
                # json_display = gr.Textbox(label="Full JSON Output", lines=20, interactive=False)  # New field for JSON
            section_preview = gr.Textbox(label="Section Content", lines=10, interactive=True)
        # TTS generation
        tts_button = gr.Button("Generate Audio")
        generated_audio = gr.Audio(label="Generated Audio", interactive=False)

    with gr.Tab("Clone a new speaker"):
        with gr.Row():
            upload_file = gr.Audio(label="Upload reference audio", type="filepath")
            with gr.Column():
                clone_speaker_name = gr.Textbox(label="Speaker name", value="default_speaker")
                clone_button = gr.Button(value="Clone speaker")
                speaker_name_custom = gr.Dropdown(
                    label="Cloned speaker",
                    choices=cloned_speaker_names.value,
                    value=cloned_speaker_names.value[0] if len(cloned_speaker_names.value) != 0 else None,
                )



    # Interactivity
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview]
    )
    section_titles.change(preview_section, inputs=[section_titles, sections_state], outputs=[section_preview])
    process_btn.click(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview])
    tts_button.click(
        generate_audio,
        inputs=[book_title, section_titles, sections_state, lang_dropdown, studio_dropdown, speaker_type],
        outputs=[generated_audio]
    )
    clone_button.click(
        fn=clone_speaker,
        inputs=[upload_file, clone_speaker_name, cloned_speaker_names],
        outputs=[upload_file, clone_speaker_name, cloned_speaker_names, speaker_name_custom],
    )

    Book2Audio.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")
