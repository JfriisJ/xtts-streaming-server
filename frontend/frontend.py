import json
import os
import logging
import time

import gradio as gr
import base64
import redis
import tempfile
import re


from text_service import extract_text_from_file, present_text_to_ui, aggregate_section_content


# Logging configuration---------------------------------------------------------
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/frontend_api.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# Initialize Redis client (Ensure it matches your Redis configuration)-----------
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_status_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=0)
redis_task_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=1)
redis_audio_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=2)

def fetch_audio_from_redis(redis_key):
    """
    Fetch audio data from Redis and save it as a temporary file.
    """
    audio_data = redis_task_client.get(redis_key)
    if not audio_data:
        raise ValueError(f"No audio found in Redis for key: {redis_key}")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_file.write(base64.b64decode(audio_data))
    temp_file.close()
    return temp_file.name


def update_section_content(book_title, selected_title, sections_state):
    """
    Display the content for the book title or specific section. Only the selected section
    should be included without aggregating nested subsections.
    """
    logger.debug(f"Selected title: {selected_title}")
    logger.debug(f"Sections state provided: {sections_state}")

    if not sections_state:
        logger.warning("No sections available.")
        return "No content available."

    if selected_title == book_title:
        # Return pre-aggregated content for the entire book
        return sections_state.get("FullBookContent", "")

    # Traverse sections to find the exact match
    sections = sections_state.get("Sections", [])
    for section in sections:
        # Search directly for the selected section
        if section.get("Heading") == selected_title:
            return section.get("Content", "").strip()

        # Recursively search subsections
        result = find_section_content(section, selected_title)
        if result:
            return result

    logger.warning(f"No matching section found for title: {selected_title}")
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

def fetch_audio_result_from_redis(task_id):
    """
    Fetch the generated audio file from Redis.
    """
    try:
        audio_data = redis_audio_client.get(f"audio:{task_id}")
        if not audio_data:
            raise ValueError(f"No audio found for task {task_id}")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.write(base64.b64decode(audio_data))
        temp_file.close()
        return temp_file.name
    except Exception as e:
        logger.error(f"Error fetching audio for task {task_id}: {e}")
        return None

def fetch_languages_and_speakers():
    """
    Fetch languages and speakers data from Redis.
    """
    try:
        # Fetch languages and speakers from Redis
        languages = redis_status_client.get("data:tts:languages")
        studio_speakers = redis_status_client.get("data:tts:studio_speakers")

        # Parse the JSON data if present
        languages = json.loads(languages) if languages else []  # Expecting a list
        studio_speakers = json.loads(studio_speakers) if studio_speakers else {}  # Expecting a dictionary
        return languages, studio_speakers
    except Exception as e:
        logger.error(f"Error fetching languages and speakers from Redis: {e}")
        return [], {}  # Return empty list and dictionary as fallback


def fetch_status_from_redis(task_id):
    """
    Fetch the status of a task from Redis.
    """
    try:
        status = redis_task_client.get(f"status:{task_id}")
        logger.info(f"Task {task_id} status: {status}")
        return status
    except Exception as e:
        logger.error(f"Error fetching status for task {task_id}: {e}")
        return "unknown"


def publish_audio_request_to_redis(
        book_title,
        section_heading,
        sections,
        language,
        speaker_name,
        speaker_type,
        output_format
):
    """
    Publish an audio generation request to Redis with only the selected section content.
    """
    logger.debug(f"Book title: {book_title}")
    logger.debug(f"Section heading: {section_heading}")
    logger.debug(f"Sections state: {sections}")
    logger.debug(f"Language: {language}, Speaker: {speaker_name}, Output format: {output_format}")

    if not section_heading:
        logger.error("No section heading provided. Cannot publish audio request.")
        return None

    # Fetch the selected section content
    selected_content = update_section_content(book_title, section_heading, sections)

    if not selected_content or selected_content == "No matching section or subsection found.":
        logger.error("Invalid content for the selected section. Cannot publish audio request.")
        return None

    try:
        task_id = f"task_{int(time.time())}"
        request_data = {
            "task_id": task_id,
            "book_title": book_title,
            "section_heading": section_heading,
            "sections": {"Heading": section_heading, "Content": selected_content},
            "language": language,
            "speaker_name": speaker_name,
            "speaker_type": speaker_type,
            "output_format": output_format,
        }

        redis_task_client.set(f"task:{task_id}", json.dumps(request_data))
        redis_task_client.set(f"status:{task_id}", "queued")
        redis_task_client.publish("audio_generation_channel", json.dumps(request_data))

        logger.info(f"Published task to Redis: {task_id}")
        return task_id
    except Exception as e:
        logger.error(f"Failed to publish audio request: {e}")
        return None



def update_section_dropdown_and_audio(book_title, audio_files_by_book):
    """
    Updates the section dropdown based on the selected book title and
    dynamically retrieves the first section's audio to update the generated_audio component.
    """
    if not book_title or book_title not in audio_files_by_book:
        return gr.update(choices=[], value=None), None

    sections = audio_files_by_book[book_title]
    section_titles = [f"{index} - {section}" for index, section in sections]

    # Retrieve the first section's audio
    first_section_key = f"{book_title}:{sections[0][0]}:{sections[0][1]}" if sections else None
    audio_file_path = retrieve_audio_from_redis_to_file(first_section_key) if first_section_key else None

    return (
        gr.update(choices=section_titles, value=section_titles[0] if section_titles else None),
        audio_file_path
    )



# Helper functions-------------------------------------------------------------
def sanitize_filename(name):
    """Replace invalid characters in filenames with underscores."""
    return re.sub(r'[<>:"/\\|?*]', '_', name)

def generate_redis_key(book_title, section_index, heading):
    """Create a sanitized Redis key."""
    return f"audio:{sanitize_filename(book_title)}:{section_index}:{sanitize_filename(heading)}"

# Functions -------------------------------------------------------------------
def update_connection_status():
    """
    Fetch the status of connected services from Redis and return formatted status text.
    """
    try:
        # Retrieve all health data keys from Redis
        service_keys = list(redis_status_client.scan_iter("health:*"))
        statuses = {}

        for key in service_keys:
            # Parse the service name from the Redis key
            service_name = key.split("health:")[-1]
            service_status = redis_status_client.get(key)

            if service_status:
                try:
                    # Parse the JSON string into a Python dictionary
                    status_data = json.loads(service_status)
                    statuses[service_name] = status_data.get("status", "Unknown")
                except json.JSONDecodeError:
                    statuses[service_name] = "Invalid Data"
            else:
                statuses[service_name] = "Unknown"

        # Format the status for UI display
        formatted_status = "\n".join([f"{name}: {status}" for name, status in statuses.items()])
        logger.info(f"Service statuses updated: {formatted_status}")
        return formatted_status
    except Exception as e:
        logger.error(f"Error updating connection status from Redis: {e}")
        return "Error retrieving connection status."



def retrieve_audio_from_redis_to_file(redis_key):
    """Retrieve audio from Redis and save it as a temporary file."""
    try:
        audio_data = redis_audio_client.get(redis_key)
        if not audio_data:
            raise ValueError(f"No audio found in Redis for key: {redis_key}")

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        temp_file.write(base64.b64decode(audio_data))
        temp_file.close()
        logger.info(f"Audio retrieved from Redis and saved to {temp_file.name}")
        return temp_file.name
    except Exception as e:
        logger.error(f"Error retrieving audio from Redis for key {redis_key}: {e}")
        return None


def get_audio_files_grouped_by_book():
    """Retrieve and organize audio files in Redis grouped by book title."""
    grouped_files = {}
    try:
        for key in redis_audio_client.scan_iter("*"):
            match = re.match(r"(?P<book>.*):(?P<index>[0-9.]+):(?P<section>.*)", key)
            if match:
                book_title = match.group("book")
                index = match.group("index")
                section_title = match.group("section")
                grouped_files.setdefault(book_title, []).append((index, section_title))

        for book_title in grouped_files:
            grouped_files[book_title].sort(key=lambda x: tuple(map(int, x[0].split("."))))
    except Exception as e:
        logger.error(f"Error fetching grouped audio files: {e}")

    return grouped_files


def update_status(task_id):
    status = fetch_status_from_redis(task_id)
    if status == "completed":
        audio_path = fetch_audio_result_from_redis(task_id)
        return status, audio_path, True
    return status, None, False

# Polling mechanism to dynamically update service status every 10 seconds
def poll_all_updates():
    """
    Poll for updates to all necessary components.
    Updates:
    - connection_status: Fetch service statuses from Redis.
    - lang_dropdown: Fetch updated language list.
    - studio_dropdown: Fetch updated speakers list.
    """
    try:
        # Update connection status
        connection_status_value = update_connection_status()

        # Fetch languages and speakers
        languages, studio_speakers = fetch_languages_and_speakers()
        lang_update = gr.update(choices=languages)
        speaker_update = gr.update(choices=list(studio_speakers.keys()))

        logger.info("Polling updates completed successfully.")
        return connection_status_value, lang_update, speaker_update
    except Exception as e:
        logger.error(f"Error during polling: {e}")
        return "Error during polling", gr.update(choices=["en"]), gr.update(choices=[])



# Gradio UI
LANGUAGES, STUDIO_SPEAKERS = fetch_languages_and_speakers()
audio_files_by_book = get_audio_files_grouped_by_book()

# Gradio UI
with gr.Blocks() as Book2Audio:
    sections_state = gr.State([])
    connection_status = gr.Textbox(label="Service Status", value="Checking", interactive=False)
    # Add a timer to dynamically fetch and update dropdown values every 10 seconds



    with gr.Tab("TTS"):
        with gr.Row():
            file_input = gr.File(label="Upload File")
            speaker_type = gr.Radio(label="Speaker Type", choices=["Studio"], value="Studio")

            # Initialize dropdowns with empty choices; these will be updated dynamically
            studio_dropdown = gr.Dropdown(label="Speaker", choices=list(STUDIO_SPEAKERS.keys()), value="Claribel Dervla" if "Claribel Dervla" in STUDIO_SPEAKERS else None)
            lang_dropdown = gr.Dropdown(label="Language", choices=LANGUAGES, value="en" if "en" in LANGUAGES else None)
            output_format_dropdown = gr.Dropdown(label="Output Format", choices=["wav", "mp3"], value="wav")

        with gr.Row():
            with gr.Column():
                process_btn = gr.Button("Process File")
                book_title = gr.Textbox(label="Book Title", value="Unknown Book", interactive=False)
                section_titles = gr.Dropdown(label="Select Section", choices=[], value=None, interactive=True)
            section_preview = gr.Textbox(label="Section Content", lines=20, interactive=True)

        tts_button = gr.Button("Generate Audio")
        progress_bar = gr.Slider(label="Progress", minimum=0, maximum=100, value=0, interactive=False)
        with gr.Row():
            task_id_box = gr.Textbox(label="Task ID", interactive=False)
            status_box = gr.Textbox(label="Task Status", interactive=False)
            download_button = gr.Button("Download Audio", visible=False)

        with gr.Row():
            with gr.Row():
                book_dropdown = gr.Dropdown(label="Select Book", choices=[], value=None, interactive=True)
                section_dropdown = gr.Dropdown(label="Select Section", choices=[], value=None)

            with gr.Column():
                generated_audio = gr.Audio(label="Generated Audio", type="filepath", interactive=False)

        json_display = gr.Textbox(label="Full JSON Output", lines=20, interactive=False)



        # Bind events
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display],
    )
    #Update audio player when a new file is selected
    book_dropdown.change(
        update_section_dropdown_and_audio,
        inputs=[book_dropdown, gr.State(audio_files_by_book)],
        outputs=[section_dropdown, generated_audio],
    )
    tts_button.click(
        publish_audio_request_to_redis,
        inputs=[
            book_title,  # The book title textbox
            section_titles,  # The dropdown value for section titles
            sections_state,  # The current state containing all sections
            lang_dropdown,  # Selected language
            studio_dropdown,  # Selected speaker
            speaker_type,  # Selected speaker type
            output_format_dropdown  # Selected output format
        ],
        outputs=[task_id_box],  # Output task ID
    )
    status_box.change(
        update_status,
        inputs=[task_id_box],
        outputs=[status_box, download_button],
    )
    process_btn.click(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_dropdown, sections_state],
    )

    # Fetch audio dynamically when a section is selected
    section_dropdown.change(
        lambda book, section: fetch_audio_from_redis(f"{book}:{section.split(' - ')[0]}:{section.split(' - ')[1]}"),
        inputs=[book_dropdown, section_dropdown],
        outputs=[generated_audio],
    )

    section_titles.change(
        update_section_content,
        inputs=[book_title, section_titles, sections_state],
        outputs=[section_preview],
    )
    gr.Timer(value=10).tick(poll_all_updates, inputs=[], outputs=[connection_status, lang_dropdown, studio_dropdown])


    Book2Audio.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")