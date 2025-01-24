import json
import os
import logging
import time

import gradio as gr
import redis
import base64
from interfaces.producer_interface import ProducerInterface
from mq import push_to_queue
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

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
redis_client = redis.StrictRedis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True, db=0)



class RedisProducer(ProducerInterface):
    def send_message(self, task, queue_name="audio_tasks"):
        """
        Push a task to the Redis queue.
        """
        push_to_queue(task, queue_name)


def create_task_and_enqueue(book_title, sections, language, speaker, speaker_type, output_format):
    """
    Create a task and enqueue it in Redis.
    """
    task = {
        "Title": book_title,
        "Sections": sections,
        "Language": language,
        "Speaker": speaker,
        "SpeakerType": speaker_type,
        "AudioFormat": output_format,
        "ID": f"{book_title}-{int(time.time())}",
        "Status": "pending",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "Priority": "normal"
    }
    producer = RedisProducer()
    producer.send_message(task)


def enqueue_clone_speaker_task(file_path, speaker_name, queue_name="clone_speaker_tasks"):
    """
    Enqueue a task to clone a speaker with the audio file encoded in Base64.

    :param file_path: Path to the audio file for cloning.
    :param speaker_name: Name of the cloned speaker.
    :param queue_name: Redis queue name for the clone speaker task.
    """
    try:
        # Read the audio file and encode it to Base64
        with open(file_path, "rb") as audio_file:
            encoded_audio = base64.b64encode(audio_file.read()).decode("utf-8")

        # Create the task payload
        task = {
            "Type": "clone_speaker",
            "AudioFileBase64": encoded_audio,
            "SpeakerName": speaker_name
        }

        # Enqueue the task
        redis_client.rpush(queue_name, json.dumps(task))
        logger.info(f"Enqueued clone speaker task for '{speaker_name}' in queue '{queue_name}'")

    except Exception as e:
        logger.error(f"Error enqueuing clone speaker task: {e}")



def fetch_languages_and_speakers():
    """
    Fetch languages and speakers data from Redis.
    """
    try:
        # Fetch languages and speakers from Redis
        languages = redis_client.get("data:tts:languages")
        studio_speakers = redis_client.get("data:tts:studio_speakers")
        cloned_speakers = redis_client.get("data:tts:cloned_speakers")

        # Parse the JSON data if present
        languages = json.loads(languages) if languages else []  # Expecting a list
        studio_speakers = json.loads(studio_speakers) if studio_speakers else {}  # Expecting a dictionary
        cloned_speakers = json.loads(cloned_speakers) if cloned_speakers else {}  # Expecting a dictionary
        return languages, studio_speakers, cloned_speakers
    except Exception as e:
        logger.error(f"Error fetching languages and speakers from Redis: {e}")
        return [], {}, {}  # Return empty list and dictionary as fallback

languages, studio_speakers, cloned_speakers = fetch_languages_and_speakers()

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


def update_speakers(speaker_type, current_selection=None):
    """
    Dynamically update the speaker dropdown based on the speaker type.
    Automatically select a default speaker if none is currently selected or if the current selection is invalid.
    """
    try:
        # Determine the list of speakers based on the selected type
        if speaker_type == "Studio":
            speakers = list(studio_speakers.keys())
        elif speaker_type == "Cloned":
            speakers = list(cloned_speakers.keys())
        else:
            speakers = []

        if not speakers:
            logger.warning(f"No speakers found for type: {speaker_type}")
            return gr.update(choices=[], value=None)

        # Choose a default speaker
        if current_selection not in speakers:
            default_speaker = "Asya Anara" if "Asya Anara" in speakers else speakers[0]
        else:
            default_speaker = current_selection

        logger.info(f"Speaker dropdown updated for type: {speaker_type} with speakers: {speakers}. Default: {default_speaker}")

        # Update the dropdown with the speaker list and set the default
        return gr.update(choices=speakers, value=default_speaker)

    except Exception as e:
        logger.error(f"Error updating speakers: {e}")
        return gr.update(choices=[], value=None)


def text_to_speech(book_title, selected_title, sections_state, language, speaker_name, speaker_type, output_format):
    """
    Queue a task for audio generation via Redis.
    """
    logger.info(f"Queueing audio generation task for: {selected_title or book_title}")
    logger.debug(f"Language: {language}, Speaker: {speaker_name}, Type: {speaker_type}, Format: {output_format}")
    logger.debug(f"Sections state: {json.dumps(sections_state, indent=2)}")

    sections = sections_state.get("Sections", [])

    # Enqueue the task
    create_task_and_enqueue(
        book_title=book_title,
        sections=sections,
        language=language,
        speaker=speaker_name,
        speaker_type=speaker_type,
        output_format=output_format
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
            lang_dropdown = gr.Dropdown(label="Language", choices=languages, value="en" if "en" in languages else None)
            output_format_dropdown = gr.Dropdown(
                label="Output Format",
                choices=["wav", "mp3"],
                value="wav",
                interactive=True
            )  # New dropdown for format selection

        with gr.Row():
            with gr.Column():
                process_btn = gr.Button("Process File")
                book_title = gr.Textbox(label="Book Title", value="Unknown Book", interactive=False)
                section_titles = gr.Dropdown(label="Select Section", choices=[], value=None, interactive=True)
            section_preview = gr.Textbox(label="Section Content", lines=20, interactive=True)

        with gr.Row():
            tts_button = gr.Button("Generate Audio")
            generated_audio = gr.Audio(label="Generated Audio", interactive=False)  # For playback
            file_selector = gr.Dropdown(label="Select Audio File", choices=[],
                                        interactive=True)  # Dropdown for file selection

            download_links = gr.Files(label="Download Generated Audio")  # For downloads

        json_display = gr.Textbox(label="Full JSON Output", lines=20, interactive=False)

    with gr.Tab("Clone a Speaker"):
        upload_file = gr.Audio(label="Upload Reference Audio", type="filepath")
        clone_speaker_name = gr.Textbox(label="Speaker Name", value="default_speaker")
        clone_button = gr.Button("Clone Speaker")
        cloned_speaker_dropdown = gr.Dropdown(label="Cloned Speaker", choices=list(cloned_speakers.keys()), value=None)

        # Bind events
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[book_title, section_titles, sections_state, section_preview, json_display]
    )
    # Update audio player when a new file is selected
    file_selector.change(
        lambda selected_file: selected_file,  # Update the audio player with the selected file
        inputs=[file_selector],
        outputs=[generated_audio]
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
        enqueue_clone_speaker_task,
        inputs=[upload_file, clone_speaker_name],
        outputs=[]
    )

    Book2Audio.launch(share=False, debug=False, server_port=3009, server_name="0.0.0.0")
