import time
import os
import uuid

import gradio as gr
import redis
import base64
from jsonschema import validate, ValidationError
import json
import logging
from mq.producer import RedisProducer
from mq.consumer import RedisConsumer
from text_service import extract_text_from_file, present_text_to_ui, aggregate_section_content

# Logging configuration
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/frontend_api.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Redis setup
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

try:
    redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=2)
    redis_health_care = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=1)
    redis_tts_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False, db=4)
except Exception as e:
    logger.error(f"Error connecting to Redis: {e}")
    raise

producer = RedisProducer()
consumer = RedisConsumer()


def fetch_languages_and_speakers():
    """Fetch languages and speakers from Redis."""
    try:
        languages = redis_tts_client.get("data:xtts:languages")
        studio_speakers = redis_tts_client.get("data:xtts:speakers")
        cloned_speakers = redis_tts_client.get("data:xtts:cloned_speakers")

        return (
            json.loads(languages) if languages else [],
            json.loads(studio_speakers) if studio_speakers else {},
            json.loads(cloned_speakers) if cloned_speakers else {},
        )
    except Exception as e:
        logger.error(f"Error fetching languages and speakers: {e}")
        return [], {}, {}

# # Channel definitions
# HEALTH_CHECK_CHANNEL = "health_check"
# HEALTH_STATUS_CHANNEL = "health_status"
# SERVICE_NAME = os.getenv("SERVICE_NAME", "frontend")
#
# def listen_for_health_checks():
#     """
#     Listen for health check requests and respond with the service's health status.
#     """
#     pubsub = redis_health_care.pubsub()
#     pubsub.subscribe(HEALTH_CHECK_CHANNEL)
#     logger.info(f"Subscribed to channel {HEALTH_CHECK_CHANNEL} for health checks.")
#
#     try:
#         for message in pubsub.listen():
#             if message["type"] == "message":
#                 try:
#                     health_request = json.loads(message["data"])
#                     if health_request.get("action") == "health_check":
#                         # Publish service status
#                         health_status = {"service": SERVICE_NAME, "status": "healthy"}
#                         redis_health_care.publish(HEALTH_STATUS_CHANNEL, json.dumps(health_status))
#                         logger.info(f"Responded to health check: {health_status}")
#                 except json.JSONDecodeError as e:
#                     logger.error(f"Invalid JSON in health check message: {message['data']} - {e}")
#                 except Exception as e:
#                     logger.error(f"Error processing health check: {e}")
#     except KeyboardInterrupt:
#         logger.info("Shutting down health check listener.")
#     except Exception as e:
#         logger.error(f"Unexpected error in health check listener: {e}")
#
# def shutdown_handler(signum, frame):
#     """
#     Handle shutdown signals gracefully.
#     """
#     logger.info("Received shutdown signal. Exiting.")
#     exit(0)


def enqueue_task(task, queue_name):
    """Enqueue a task in Redis."""
    try:
        redis_client.rpush(queue_name, json.dumps(task))
        logger.info(f"Task enqueued in {queue_name}: {task['job_id']}")
    except Exception as e:
        logger.error(f"Error enqueuing task in {queue_name}: {e}")

def validate_task_with_schema(task, schema_path):
    """
    Validate a task using a JSON schema.

    :param task: The task dictionary to validate.
    :param schema_path: Path to the JSON schema file.
    :return: True if valid, False otherwise.
    """
    try:
        with open(schema_path, "r") as schema_file:
            schema = json.load(schema_file)
        validate(instance=task, schema=schema)
        return True
    except ValidationError as e:
        logger.error(f"Task validation failed: {e.message}")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Error loading schema: {e}")
        return False

# def create_audio_task(book_title, selected_title, sections, language, speaker, speaker_type, output_format):
#     """Create and enqueue an audio generation task."""
#     job_id = f"{book_title}-{int(time.time())}"
#     task = {
#         "job_id": job_id,
#         "sections": sections,
#         "language": language,
#         "book_title": book_title,
#         "selected_title": selected_title,
#
#
#         "speaker": speaker,
#         "speaker_type": speaker_type,
#         "output_format": output_format,
#
#         "task_type": "tts_generate",
#         "status": "pending",
#         "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
#         "priority": "normal"
#     }
#     enqueue_task(task, "audio_tasks")



def create_audio_task(book_title, selected_title, sections, language, speaker, speaker_type, output_format ):
    """
    Create and enqueue an audio generation task.
    :param task_id : Unique identifier for the task.
    :param job_id : Unique identifier for the job.
    :param book_title: Title of the book.
    :param selected_title: Title of the selected section.
    :param sections: List of sections and content.
    :param language: Language of the content.
    :param speaker: Speaker identifier.
    :param speaker_type: Type of speaker (e.g., Studio).
    :param output_format: Desired audio format.
    :param status: Status of the task.
    :param timestamp: Timestamp of the task creation.
    :param priority: Priority level of the task.
    """
    # Generate a unique job ID
    job_id = f"{book_title}-{int(time.time())}"
    schema_path = "mq/schema/tts_generate.json"

    # Prepare the task
    task = {
        "task_id": str(uuid.uuid4()),
        "job_id": job_id,
        "book_title": book_title,
        "selected_title": selected_title,
        "sections": sections,
        "language": language,
        "speaker": speaker,
        "speaker_type": speaker_type,
        "output_format": output_format,
        "status": "pending",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "priority": "normal",
    }

    # Validate the task
    if not validate_task_with_schema(task, schema_path):
        logger.error("Task validation failed. Task not enqueued.")
        return

    # Enqueue the task
    enqueue_task(task, "audio_tasks")
    logger.info(f"Task {task['task_id']} added to the queue successfully.")


def create_clone_speaker_task(file_path, speaker_name):
    """Create and enqueue a speaker cloning task."""
    try:
        with open(file_path, "rb") as audio_file:
            encoded_audio = base64.b64encode(audio_file.read()).decode("utf-8")
        task = {"Type": "clone_speaker", "AudioFileBase64": encoded_audio, "SpeakerName": speaker_name}
        enqueue_task(task, "clone_speaker_tasks")
    except Exception as e:
        logger.error(f"Error creating clone speaker task: {e}")


def process_file(file):
    """Process an uploaded file and prepare its content for the UI."""
    if not file:
        return "No file uploaded.", gr.update(choices=[]), None, "", ""

    try:
        raw_result, file_name = extract_text_from_file(file.name)
        title, section_titles, formatted_content = present_text_to_ui(raw_result, file_name)

        full_book_content = aggregate_section_content(title, raw_result.get("Sections", []))
        return title, gr.update(choices=section_titles), formatted_content, full_book_content, json.dumps(raw_result, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        return "Error processing file.", gr.update(choices=[]), None, "", ""

def update_speakers(speaker_type, current_selection=None):
    """Update speaker dropdown based on the selected type."""
    try:
        speakers = STUDIO_SPEAKERS if speaker_type == "Studio" else CLONED_SPEAKERS
        speakers = list(speakers.keys())
        default = speakers[0] if current_selection not in speakers else current_selection
        return gr.update(choices=speakers, value=default)
    except Exception as e:
        logger.error(f"Error updating speakers: {e}")
        return gr.update(choices=[], value=None)


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


# def update_speakers(speaker_type, current_selection=None):
#     """
#     Dynamically update the speaker dropdown based on the speaker type.
#     Automatically select a default speaker if none is currently selected or if the current selection is invalid.
#     """
#     try:
#         # Determine the list of speakers based on the selected type
#         if speaker_type == "Studio":
#             speakers = list(STUDIO_SPEAKERS.keys())
#         elif speaker_type == "Cloned":
#             speakers = list(CLONED_SPEAKERS.keys())
#         else:
#             speakers = []
#
#         if not speakers:
#             logger.warning(f"No speakers found for type: {speaker_type}")
#             return gr.update(choices=[], value=None)
#
#         # Choose a default speaker
#         if current_selection not in speakers:
#             default_speaker = "Asya Anara" if "Asya Anara" in speakers else speakers[0]
#         else:
#             default_speaker = current_selection
#
#         logger.info(f"Speaker dropdown updated for type: {speaker_type} with speakers: {speakers}. Default: {default_speaker}")
#
#         # Update the dropdown with the speaker list and set the default
#         return gr.update(choices=speakers, value=default_speaker)
#
#     except Exception as e:
#         logger.error(f"Error updating speakers: {e}")
#         return gr.update(choices=[], value=None)


def text_to_speech(book_title, selected_title, sections_state, language, speaker_name, speaker_type, output_format):
    """
    Queue a task for audio generation via Redis.
    """
    logger.info(f"Queueing audio generation task for: {selected_title or book_title}")
    logger.debug(f"Language: {language}, Speaker: {speaker_name}, Type: {speaker_type}, Format: {output_format}")
    logger.debug(f"Sections state: {json.dumps(sections_state, indent=2)}")

    sections = sections_state.get("Sections", [])

    # Enqueue the task
    create_audio_task(
        book_title=book_title,
        selected_title=selected_title,
        sections=sections,
        language=language,
        speaker=speaker_name,
        speaker_type=speaker_type,
        output_format=output_format
    )




def get_selected_content(selected_title, sections):
    """
    Retrieve the content of the selected section or the entire book if the title is selected.

    :param selected_title: The title of the selected section or the entire book.
    :param sections: The list of all sections in the book.
    :return: The selected section or subsections as a list.
    """
    if selected_title == sections[0].get("Title", "Unknown Book"):
        # Return the entire book content
        return sections

    for section in sections:
        if section.get("Heading") == selected_title:
            # Return the selected section and its subsections
            return [section]

        # Recursively search subsections
        result = find_selected_section(section.get("Subsections", []), selected_title)
        if result:
            return result

    return []  # Return an empty list if no matching section is found


def find_selected_section(subsections, selected_title):
    """
    Recursively find the section or subsection matching the selected title.

    :param subsections: List of subsections to search.
    :param selected_title: The title to match.
    :return: A list containing the matching section or subsection, or None if not found.
    """
    for subsection in subsections:
        if subsection.get("Heading") == selected_title:
            return [subsection]

        # Recursively search deeper subsections
        result = find_selected_section(subsection.get("Subsections", []), selected_title)
        if result:
            return result

    return None

def get_books():
    """
    Retrieve all unique book titles from Redis.
    """
    keys = redis_client.keys("*:*:*")  # Match all keys with the {Book}:{Index}:{Section} pattern
    books = set()
    for key in keys:
        key = key.decode()  # Decode the bytes key to string
        book_title = key.split(":")[0]  # Extract the book title
        books.add(book_title)
    return sorted(list(books))


def handle_section_selection(selected_value):
    """
    Parse the selected dropdown value to extract the section index and name.
    """
    if not selected_value:
        logger.error("No section selected.")
        return None, None

    try:
        index, section_name = selected_value.split(":", 1)  # Split into index and name
        return index, section_name
    except ValueError:
        logger.error(f"Invalid selection format: {selected_value}")
        return None, None



def get_sections_for_book(book_title):
    """
    Retrieve sections for a specific book from Redis and update dropdown choices.
    """
    if not book_title:
        return gr.update(choices=[], value=None)

    keys = redis_client.keys(f"{book_title}:*:*")  # Match all keys for the book
    sections = []
    for key in keys:
        key = key.decode()  # Decode the key
        parts = key.split(":", 2)
        if len(parts) == 3:
            _, index, section_name = parts
            sections.append(f"{index}:{section_name}")  # Use index and name in dropdown value

    sections = sorted(sections)
    logger.debug(f"Dropdown updated for book '{book_title}' with sections: {sections}")
    return gr.update(choices=sections, value=sections[0] if sections else None)


def play_and_prepare_download(book_title, index, section_name):
    """
    Retrieve and play the audio for the selected book, index, and section.
    Prepare the audio file for playback.

    :param book_title: Title of the book.
    :param index: Index of the section.
    :param section_name: Name of the section.
    :return: Binary audio data or None if audio is not found.
    """
    redis_key = f"{book_title}:{index}:{section_name}"
    logger.debug(f"Attempting to fetch audio for key: {redis_key}")

    # Fetch binary audio from Redis
    audio_binary = redis_client.get(redis_key)

    if not audio_binary:
        logger.warning(f"Audio not found for key: {redis_key}")
        return None

    logger.info(f"Prepared audio for playback.")
    return audio_binary



def update_audio_metadata(book_title, sections):
    """
    Dynamically update Redis with metadata about audio files.

    :param book_title: Title of the book.
    :param sections: List of section titles.
    """
    redis_key = "audio_metadata"
    audio_metadata = redis_client.get(redis_key)
    if not audio_metadata:
        metadata = {}
    else:
        metadata = json.loads(audio_metadata)

    # Update metadata with the new book and sections
    metadata[book_title] = {"Sections": sections}
    redis_client.set(redis_key, json.dumps(metadata))
    logger.info(f"Updated audio metadata for book '{book_title}'")


def fetch_status_from_redis(task_id):
    """
    Fetch the status of a task from Redis.
    """
    try:
        status = redis_client.get(f"status:{task_id}")
        logger.info(f"Task {task_id} status: {status}")
        return status
    except Exception as e:
        logger.error(f"Error fetching status for task {task_id}: {e}")
        return "unknown"



def update_status(task_id):
    status = fetch_status_from_redis(task_id)
    if status == "completed":
        return status, True
    return status, False



get_books()

# Fetch initial data
LANGUAGES, STUDIO_SPEAKERS, CLONED_SPEAKERS = fetch_languages_and_speakers()
# listen_for_health_checks()

# Gradio UI
with gr.Blocks() as Book2Audio:
    sections_state = gr.State([])
    connection_status = gr.Textbox(label="Service Status", value="Checking...", interactive=False)
    # gr.Timer(value=20).tick(he, inputs=[], outputs=[connection_status])
    # gr.Timer(value=10).tick(listen_for_health_checks, inputs=[], outputs=[connection_status])

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
        with gr.Column():
            with gr.Row():
                book_dropdown = gr.Dropdown(label="Select Book", choices=get_books(), value=None)
                section_dropdown = gr.Dropdown(label="Select Section", choices=[], value=None)

            with gr.Row():
                audio_player = gr.Audio(label="Audio Preview", type="filepath")
                generated_audio = gr.Audio(label="Generated Audio", interactive=False)  # For playback
                download_button = gr.File(label="Download Audio")

        json_display = gr.Textbox(label="Full JSON Output", lines=20, interactive=False)

    with gr.Tab("Clone a Speaker"):
        upload_file = gr.Audio(label="Upload Reference Audio", type="filepath")
        clone_speaker_name = gr.Textbox(label="Speaker Name", value="default_speaker")
        clone_button = gr.Button("Clone Speaker")
        cloned_speaker_dropdown = gr.Dropdown(label="Cloned Speaker", choices=list(CLONED_SPEAKERS.keys()), value=None)

    # Update sections dropdown dynamically based on selected book
    book_dropdown.change(
        get_sections_for_book,
        inputs=[book_dropdown],
        outputs=[section_dropdown]
    )
    # Play and prepare download when a section is selected
    section_dropdown.change(
        lambda book, selection: play_and_prepare_download(
            book, *handle_section_selection(selection)
        ),
        inputs=[book_dropdown, section_dropdown],
        outputs=[audio_player]
    )

    # Bind events
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display]
    )
    # Update audio player when a new file is selected

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
    # Event binding
    tts_button.click(
        text_to_speech,
        inputs=[
            book_title, section_titles, sections_state, lang_dropdown, studio_dropdown, speaker_type,
            output_format_dropdown
        ],
        outputs=[]
    )
    process_btn.click(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display]
    )

    clone_button.click(
        create_clone_speaker_task,
        inputs=[upload_file, clone_speaker_name],
        outputs=[]
    )


    Book2Audio.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")
