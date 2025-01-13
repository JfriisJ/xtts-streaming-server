import json
import os
import logging
import gradio as gr
from audio_service import generate_audio, clone_speaker, CLONED_SPEAKERS, LANGUAGES, STUDIO_SPEAKERS
from health_service import check_service_health
from text_service import extract_text_from_file, present_text_to_ui, aggregate_section_content

# Logging configuration
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/frontend_api.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def update_connection_status():
    """
    Check the status of connected services and update the connection status in the UI.
    """
    try:
        # Call the health service to check the status of all services
        status = check_service_health()
        # Format the status for display
        return "\n".join([f"{name}: {info['status']}" for name, info in status.items()])
    except Exception as e:
        logger.error(f"Error updating connection status: {e}")
        return "Error checking service status."


def update_section_content(book_title, selected_title, sections_state):
    """
    Display the pre-aggregated content for the book title or specific sections.
    """
    logger.debug(f"Selected title: {selected_title}")
    logger.debug(f"Sections state provided: {sections_state}")

    if not sections_state:
        logger.warning("No sections available.")
        return "No content available."

    if selected_title == book_title:
        # Return pre-aggregated content for the entire book
        full_book_content = sections_state.get("FullBookContent", "")
        logger.debug(f"Using pre-aggregated content for book title: {full_book_content[:500]}...")
        return full_book_content

    # Find and display content for the selected section
    for section in sections_state.get("Sections", []):
        if section.get("Heading") == selected_title:
            content = aggregate_section_content(selected_title, [section])
            logger.debug(f"Content for section '{selected_title}': {content[:500]}...")
            return content

    logger.warning(f"No matching section found for title: {selected_title}")
    return "No matching section found."


def process_file(file):
    """
    Process the uploaded file and display formatted content, including pre-aggregated text for the book title.
    """
    if not file:
        return "No file uploaded.", gr.update(choices=[]), None, "", ""

    try:
        raw_result, file_name = extract_text_from_file(file.name)
        formatted_json_output = json.dumps(raw_result, indent=4, ensure_ascii=False)
        logger.debug(f"Raw extraction result: {raw_result}")

        # Extract title and sections
        title, section_titles, formatted_content = present_text_to_ui(raw_result, file_name)

        # Aggregate content for the entire book
        sections = raw_result.get("Sections", [])
        full_book_content = aggregate_section_content(title, sections, include_subsections=True)

        # Ensure the book title is only included once
        if title not in section_titles:
            section_titles.insert(0, title)

        # Update dropdown and state
        if not sections:
            return title, gr.update(choices=[]), [], "No sections found.", ""

        logger.info(f"File processed successfully: {file.name}")
        return title, gr.update(choices=section_titles), {"Sections": sections, "FullBookContent": full_book_content}, formatted_content, formatted_json_output

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return "Error processing file.", gr.update(choices=[]), None, "", ""



def update_speakers(speaker_type):
    """
    Dynamically update the speaker dropdown based on the speaker type.
    """
    try:
        # Determine the list of speakers based on the selected type
        if speaker_type == "Studio":
            speakers = list(STUDIO_SPEAKERS.keys())
        elif speaker_type == "Cloned":
            speakers = list(CLONED_SPEAKERS.keys())
        else:
            speakers = []

        # Set the default speaker
        default_speaker = "Asya Anara" if "Asya Anara" in speakers else speakers[0] if speakers else None

        # Log the update
        logger.info(f"Speaker dropdown updated for type: {speaker_type} with speakers: {speakers}")

        # Update the Gradio dropdown with the speaker list
        return gr.update(choices=speakers, value=default_speaker)

    except Exception as e:
        # Log and handle errors
        logger.error(f"Error updating speakers: {e}")
        return gr.update(choices=[], value=None)


def log_and_generate_audio(book_title, selected_title, sections_state, language, speaker_name, speaker_type):
    """
    Logs the input data before passing it to the generate_audio function.
    """
    logger.info(f"Frontend -> Audio Service: Preparing to generate audio")
    logger.debug(f"Book Title: {book_title}")
    logger.debug(f"Selected Section Title: {selected_title}")
    logger.debug(f"Language: {language}")
    logger.debug(f"Speaker Type: {speaker_type}")
    logger.debug(f"Speaker Name: {speaker_name}")
    logger.debug(f"Sections State: {sections_state}")

    return generate_audio(
        book_title, selected_title, sections_state, language, speaker_name, speaker_type
    )


def get_selected_content(selected_title, sections):
    """
    Retrieve the content of the selected section or the entire book if the title is selected.
    """
    if selected_title == sections[0].get("Title", "Unknown Book"):
        return "\n".join([aggregate_section_content(selected_title, section, include_subsections=True) for section in sections])

    for section in sections:
        if section.get("Heading") == selected_title:
            return aggregate_section_content(selected_title, section, include_subsections=True)

    return ""

# Gradio UI
with gr.Blocks() as Book2Audio:
    sections_state = gr.State([])
    connection_status = gr.Textbox(label="Service Status", value="Checking...", interactive=False)
    gr.Timer(value=20).tick(update_connection_status, inputs=[], outputs=[connection_status])

    with gr.Tab("TTS"):
        with gr.Row():
            file_input = gr.File(label="Upload File")
            speaker_type = gr.Radio(label="Speaker Type", choices=["Studio", "Cloned"], value="Studio")
            studio_dropdown = gr.Dropdown(label="Speaker", choices=[], value=None)
            lang_dropdown = gr.Dropdown(label="Language", choices=LANGUAGES, value="en" if "en" in LANGUAGES else None)

        with gr.Row():
            with gr.Column():
                process_btn = gr.Button("Process File")
                book_title = gr.Textbox(label="Book Title", value="Unknown Book", interactive=False)
                section_titles = gr.Dropdown(label="Select Section", choices=[], value=None, interactive=True)
            section_preview = gr.Textbox(label="Section Content", lines=20, interactive=False)

        tts_button = gr.Button("Generate Audio")
        generated_audio = gr.Audio(label="Generated Audio", interactive=False)
        json_display = gr.Textbox(label="Full JSON Output", lines=20, interactive=False)

    with gr.Tab("Clone a Speaker"):
        upload_file = gr.Audio(label="Upload Reference Audio", type="filepath")
        clone_speaker_name = gr.Textbox(label="Speaker Name", value="default_speaker")
        clone_button = gr.Button("Clone Speaker")
        cloned_speaker_dropdown = gr.Dropdown(label="Cloned Speaker", choices=list(CLONED_SPEAKERS.keys()), value=None)

    # Bind events
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display]
    )
    speaker_type.change(
        update_speakers,
        inputs=[speaker_type],
        outputs=[studio_dropdown]
    )
    section_titles.change(
        update_section_content,
        inputs=[book_title, section_titles, sections_state],
        outputs=[section_preview]
    )
    tts_button.click(
        log_and_generate_audio,  # Wrap `generate_audio` with a logging function
        inputs=[
            book_title,  # The title of the book
            section_titles,  # The selected section title
            sections_state,  # The state containing all sections
            lang_dropdown,  # Language
            studio_dropdown,  # Speaker name
            speaker_type,  # Speaker type
        ],
        outputs=[generated_audio]
    )

    clone_button.click(
        clone_speaker,
        inputs=[upload_file, clone_speaker_name],
        outputs=[upload_file, clone_speaker_name, cloned_speaker_dropdown]
    )

    Book2Audio.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")
