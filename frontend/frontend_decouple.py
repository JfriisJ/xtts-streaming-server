import time

import redis
import json
import os
import logging
import gradio as gr

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

# Initialize Redis client
redis_setup_client = redis.StrictRedis(host="localhost", port=6379, db=1)
redis_text_client = redis.StrictRedis(host="localhost", port=6379, db=2)
redis_audio_client = redis.StrictRedis(host="localhost", port=6379, db=3)


def fetch_languages_and_speakers():
    """
    Dynamically fetch languages and speaker data from Redis.
    """
    try:
        languages = json.loads(redis_setup_client.get("tts:languages") or "[]")  # Default to empty list
        studio_speakers = json.loads(redis_setup_client.get("tts:studio_speakers") or "{}")  # Default to empty dict
        cloned_speakers = json.loads(redis_setup_client.get("tts:cloned_speakers") or "{}")  # Default to empty dict

        logger.info("Fetched languages and speakers from the TTS server.")
        logger.info(f"Languages: {languages}")
        logger.info(f"Studio Speakers: {list(studio_speakers.keys())}")
        logger.info(f"Cloned Speakers: {list(cloned_speakers.keys())}")

        return languages, studio_speakers, cloned_speakers
    except redis.exceptions.ConnectionError as e:
        logger.error(f"Redis connection error: {e}")
        return [], {}, {}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return [], {}, {}


def check_task_status(task_id):
    """
    Check the status of an audio generation task in Redis stream.
    """
    try:
        status = redis_audio_client.hget(f"status:{task_id}", "status")
        if not status:
            return "Pending", None

        status = status.decode("utf-8")
        if status == "completed":
            results = redis_audio_client.lrange(f"results:{task_id}", 0, -1)
            return "Completed", [result.decode("utf-8") for result in results]
        elif status == "failed":
            return "Failed", None
        else:
            return "In Progress", None
    except Exception as e:
        logger.error(f"Error checking status for task '{task_id}': {e}")
        return "Pending", None



def submit_audio_task(book_title, selected_title, sections_state, language, speaker_type, speaker_name, output_format):

    """
    Submit an audio generation task to Redis stream for processing by a background worker.
    """
    task_id = f"{book_title}:{selected_title}".replace(" ", "_")
    try:
        # Fetch pre-segmented data from Redis
        redis_key = f"book:{book_title.replace(' ', '_')}"
        segmented_data = redis_text_client.get(redis_key)
        if not segmented_data:
            raise ValueError(f"No pre-segmented data found in Redis for book: {book_title}")

        task_data = {
            "task_id": task_id,
            "book_title": book_title,
            "selected_title": selected_title,
            "sections_state": sections_state,
            "language": language,
            "speaker_type": speaker_type,
            "speaker_name": speaker_name,
            "output_format": output_format,
            "content": json.loads(segmented_data),
        }

        # Submit task to Redis stream
        redis_text_client.xadd("audio_tasks", {"task_data": json.dumps(task_data)})
        logger.info(f"Task '{task_id}' submitted to Redis stream.")
        return task_id

    except Exception as e:
        logger.error(f"Failed to submit task '{task_id}': {e}")
        return None



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
    Display the content for the book title, specific sections, or subsections.
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

    # Traverse sections and subsections to find the selected title
    sections = sections_state.get("Sections", [])

    for section in sections:
        # Search for the selected section
        if section.get("Heading") == selected_title:
            content = aggregate_section_with_subsections(section)
            logger.debug(f"Content for section '{selected_title}': {content[:500]}...")
            return content

        # Recursively search subsections
        result = find_section_content(section, selected_title)
        if result:
            logger.debug(f"Content for subsection '{selected_title}': {result[:500]}...")
            return result

    logger.warning(f"No matching section or subsection found for title: {selected_title}")
    return "No matching section or subsection found."



def find_section_content(section, selected_title):
    """
    Recursively finds the content for the selected section or subsection, including all its nested subsections.
    """
    if section.get("Heading") == selected_title:
        return aggregate_section_with_subsections(section)

    for subsection in section.get("Subsections", []):
        result = find_section_content(subsection, selected_title)
        if result:
            return result

    return None


def aggregate_section_with_subsections(section, depth=1):
    """
    Aggregate content of a section and its subsections recursively.
    Adds appropriate heading markers (#, ##, ###, etc.) based on depth.
    """
    heading_marker = "#" * min(depth, 5)  # Limit heading levels to 5
    heading = section.get("Heading", "").strip()
    content = section.get("Content", "")

    if isinstance(content, list):
        content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
    elif isinstance(content, str):
        content = content.strip()
    else:
        content = ""

    aggregated_content = f"{heading_marker} {heading}\n\n{content}"

    for subsection in section.get("Subsections", []):
        aggregated_content += "\n\n" + aggregate_section_with_subsections(subsection, depth + 1)

    return aggregated_content


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

        # Add all sections and subsections to the dropdown
        def add_titles(section, titles):
            titles.append(section.get("Heading", ""))
            for subsection in section.get("Subsections", []):
                add_titles(subsection, titles)

        section_titles = []
        for section in sections:
            add_titles(section, section_titles)

        # Ensure the book title is included as a choice
        if title not in section_titles:
            section_titles.insert(0, title)

        # Update dropdown and state
        if not sections:
            return title, gr.update(choices=[]), [], "No sections found.", ""

        logger.info(f"File processed successfully: {file.name}")
        return (
            title,
            gr.update(choices=section_titles),
            {"Sections": sections, "FullBookContent": full_book_content},
            formatted_content,
            formatted_json_output
        )

    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return "Error processing file.", gr.update(choices=[]), None, "", ""


def update_speakers(speaker_type):
    """
    Dynamically update the speaker dropdown based on the speaker type.
    """
    try:
        languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()

        if speaker_type == "Studio":
            speakers = list(studio_speakers.keys())
        elif speaker_type == "Cloned":
            speakers = list(cloned_speakers.keys())
        else:
            speakers = []

        if not speakers:
            logger.warning(f"No speakers found for type: {speaker_type}")
            return gr.update(choices=[], value=None)

        default_speaker = speakers[0] if speakers else None
        return gr.update(choices=speakers, value=default_speaker)
    except Exception as e:
        logger.error(f"Error updating speakers: {e}")
        return gr.update(choices=[], value=None)


def submit_clone_speaker_task(upload_file_path, clone_speaker_name):
    """
    Submit a clone speaker task to Redis for processing by the backend worker.
    """
    task_id = f"clone_speaker:{clone_speaker_name}"
    task_data = {
        "task_id": task_id,
        "audio_file_path": upload_file_path,
        "clone_speaker_name": clone_speaker_name,
    }
    try:
        redis_setup_client.xadd("clone_speaker_tasks", {"task_data": json.dumps(task_data)})
        logger.info(f"Clone speaker task '{task_id}' submitted to Redis.")
        return task_id
    except Exception as e:
        logger.error(f"Failed to submit clone speaker task '{task_id}': {e}")
        return None

def check_clone_speaker_status(task_id):
    """
    Check the status of a clone speaker task in Redis.
    """
    try:
        status = redis_setup_client.hget(f"status:{task_id}", "status")
        if not status:
            return "Pending", None

        status = status.decode("utf-8")
        if status == "completed":
            new_speaker_name = redis_setup_client.hget(f"status:{task_id}", "result").decode("utf-8")
            return "Completed", new_speaker_name
        elif status == "failed":
            return "Failed", None
        else:
            return "In Progress", None
    except Exception as e:
        logger.error(f"Error checking status for task '{task_id}': {e}")
        return "Pending", None

def update_languages(speaker_type):
    """
    Dynamically update the language dropdown.
    """
    try:
        languages, __, __ = fetch_languages_and_speakers()

        if not languages:
            logger.warning(f"No languages found for type: {speaker_type}")
            return gr.update(choices=[], value=None)

        default_languages = languages[0] if languages else None
        return gr.update(choices=languages, value=default_languages)
    except Exception as e:
        logger.error(f"Error updating languages: {e}")
        return gr.update(choices=[], value=None)


def clone_speaker(upload_file, clone_speaker_name):
    """
    Handle the clone speaker functionality by submitting a task to Redis and polling for the result.
    """
    if not upload_file or not clone_speaker_name.strip():
        return "No file or speaker name provided.", gr.update(choices=[])

    # Submit the cloning task
    task_id = submit_clone_speaker_task(upload_file.name, clone_speaker_name)
    if not task_id:
        return "Failed to submit cloning task.", gr.update(choices=[])

    logger.info(f"Clone speaker task '{task_id}' submitted. Checking status...")

    # Poll for task completion
    for _ in range(30):  # Poll for up to 30 seconds
        status, result = check_clone_speaker_status(task_id)
        if status == "Completed":
            # Update cloned speaker list
            cloned_speakers = redis_setup_client.get("tts:cloned_speakers")
            cloned_speakers = json.loads(cloned_speakers) if cloned_speakers else {}
            cloned_speakers[clone_speaker_name] = result
            redis_setup_client.set("tts:cloned_speakers", json.dumps(cloned_speakers))
            return f"Speaker '{clone_speaker_name}' cloned successfully.", gr.update(choices=list(cloned_speakers.keys()))
        elif status == "Failed":
            return "Speaker cloning failed. Please try again.", gr.update(choices=[])

        time.sleep(2)

    return "Speaker cloning is still in progress. Please check back later.", gr.update(choices=[])


def poll_task_status(task_id):
    """
    Poll the status of an audio generation task from Redis.
    """
    while True:
        status, details = check_task_status(task_id)
        if status == "completed":
            logger.info(f"Task '{task_id}' completed.")
            return "Completed", details
        elif status == "failed":
            logger.error(f"Task '{task_id}' failed.")
            return "Failed", None
        time.sleep(2)


# Fetch data on page load
languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()

# Validate dropdown defaults
default_language = "en" if "en" in languages else (languages[0] if languages else None)
default_speaker = list(studio_speakers.keys())[0] if studio_speakers else None

# Gradio UI
with gr.Blocks() as Book2Audio:
    sections_state = gr.State([])
    connection_status = gr.Textbox(label="Service Status", value="Checking...", interactive=False)
    gr.Timer(value=20).tick(update_connection_status, inputs=[], outputs=[connection_status])

    with gr.Tab("TTS"):
        with gr.Row():
            file_input = gr.File(label="Upload File")
            speaker_type = gr.Dropdown(label="Speaker Type", choices=["Studio", "Cloned"], value="Studio")
            studio_dropdown = gr.Dropdown(
                label="Speaker",
                choices=list(studio_speakers.keys()),
                value=default_speaker
            )
            lang_dropdown = gr.Dropdown(
                label="Language",
                choices=languages,
                value=default_language
            )
            output_format_dropdown = gr.Dropdown(
                label="Output Format", choices=["wav", "mp3"], value="wav", interactive=True
            )

        with gr.Row():
            with gr.Column():
                process_btn = gr.Button("Process File")
                book_title = gr.Textbox(label="Book Title", value="Unknown Book", interactive=False)
                section_titles = gr.Dropdown(label="Select Section", choices=[], value=None, interactive=True)
            section_preview = gr.Textbox(label="Section Content", lines=20, interactive=True)

        with gr.Row():
            tts_button = gr.Button("Generate Audio")
            generated_audio = gr.Audio(label="Generated Audio", interactive=False)
            file_selector = gr.Dropdown(label="Select Audio File", choices=[], interactive=True)
            download_links = gr.Files(label="Download Generated Audio")

        json_display = gr.Textbox(label="Full JSON Output", lines=20, interactive=False)

    with gr.Tab("Clone a Speaker"):
        upload_file = gr.Audio(label="Upload Reference Audio", type="filepath")
        clone_speaker_name = gr.Textbox(label="Speaker Name", value="default_speaker")
        clone_button = gr.Button("Clone Speaker")
        cloned_speaker_dropdown = gr.Dropdown(
            label="Cloned Speaker",
            choices=list(cloned_speakers.keys()),
            value=None
        )

    # Event bindings
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display]
    )

    file_selector.change(
        lambda selected_file: selected_file,
        inputs=[file_selector],
        outputs=[generated_audio]
    )

    speaker_type.change(
        update_speakers,
        inputs=[speaker_type],
        outputs=[studio_dropdown]
    )

    lang_dropdown.change(
        lambda selected_language: gr.update(value=selected_language),  # Update the value to the user's selection
        inputs=[lang_dropdown],  # Pass the current value as input
        outputs=[lang_dropdown]  # Update the dropdown with the selected value
    )

    section_titles.change(
        update_section_content,
        inputs=[book_title, section_titles, sections_state],
        outputs=[section_preview]
    )

    tts_button.click(
        lambda *args: submit_audio_task(*args) or "Task submitted. Polling for status...",
        inputs=[
            book_title,
            section_titles,
            sections_state,
            lang_dropdown,
            studio_dropdown,
            speaker_type,
            output_format_dropdown,
        ],
        outputs=[gr.Textbox(label="Status", interactive=False)],
    )

    process_btn.click(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display]
    )

    clone_button.click(
        clone_speaker,
        inputs=[upload_file, clone_speaker_name],
        outputs=[gr.Textbox(label="Status Message", interactive=False), cloned_speaker_dropdown]
    )

Book2Audio.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")