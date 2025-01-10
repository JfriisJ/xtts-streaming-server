import os
import base64
import json
import shutil
import re
import requests
import gradio as gr
from pydub import AudioSegment
from zipfile import ZipFile
from lxml import etree


#-------------------------------------------------------------------------------------------
SERVER_URL = 'http://localhost:8000'
OUTPUT = "./demo_outputs"
cloned_speakers = {}
os.makedirs(os.path.join(OUTPUT, "cloned_speakers"), exist_ok=True)
os.makedirs(os.path.join(OUTPUT, "generated_audios"), exist_ok=True)
print("File structure prepared.")


print("Preparing file structure...")
if not os.path.exists(OUTPUT):
    os.mkdir(OUTPUT)
    os.mkdir(os.path.join(OUTPUT, "cloned_speakers"))
    os.mkdir(os.path.join(OUTPUT, "generated_audios"))
elif os.path.exists(os.path.join(OUTPUT, "cloned_speakers")):
    print("Loading existing cloned speakers...")
    for file in os.listdir(os.path.join(OUTPUT, "cloned_speakers")):
        if file.endswith(".json"):
            with open(os.path.join(OUTPUT, "cloned_speakers", file), "r") as fp:
                cloned_speakers[file[:-5]] = json.load(fp)
    print("Available cloned speakers:", ", ".join(cloned_speakers.keys()))

try:
    print("Getting metadata from server ...")
    LANGUAGES = requests.get(SERVER_URL + "/languages").json()
    print("Available languages:", ", ".join(LANGUAGES))
    STUDIO_SPEAKERS = requests.get(SERVER_URL + "/studio_speakers").json()
    print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS.keys()))
except:
    raise Exception("Please make sure the server is running first.")

#-------------------------------------------------------------------------------------------
#Test the tts function
import time

def test_tts(text, lang, speaker_type, speaker_name_studio, speaker_name_custom, stream=False):
    start_time = time.time()
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
    endpoint = "/tts_stream" if stream else "/tts"
    payload = {
        "text": text,
        "language": lang,
        "speaker_embedding": embeddings["speaker_embedding"],
        "gpt_cond_latent": embeddings["gpt_cond_latent"]
    }
    if stream:
        payload["add_wav_header"] = True
        payload["stream_chunk_size"] = "10"

    response = requests.post(SERVER_URL + endpoint, json=payload, stream=stream)
    if response.status_code == 200:
        print(f"TTS request ({'streaming' if stream else 'normal'}) completed in {time.time() - start_time:.2f} seconds.")
    else:
        print(f"TTS request failed: {response.status_code} - {response.text}")

#-------------------------------------------------------------------------------------------
# Flatten Sections for Dropdown
def flatten_sections(sections, prefix=""):
    """
    Flattens a hierarchical structure into a flat list with titles prefixed by their depth.
    """
    flat_list = []

    def add_section(section, depth=1):
        flat_list.append({"title": f"{prefix} {section['style']}: {section['title']}", "content": section["content"]})
        for subsection in section.get("subsections", []):
            add_section(subsection, depth + 1)

    for section in sections:
        add_section(section)

    return flat_list


def process_file(file):
    if file is None:
        print("No file uploaded.")
        return gr.update(choices=[], value=None), [], "No file uploaded."

    try:
        doc_structure = extract_odt_structure(file.name)
        book_title = doc_structure.get("title", "Unknown Book")  # Default to "Unknown Book" if no title
        sections = doc_structure.get("sections", [])
        if not sections:
            print("No sections found in document.")
            return gr.update(choices=[], value=None), [], "No sections found in the document."

        flat_sections = [{"title": f"{sec['style']}: {sec['title']}", "content": sec.get("content", "")} for sec in sections]
        section_titles = [sec["title"] for sec in flat_sections]

        print(f"Sections extracted: {len(flat_sections)}")
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = flat_sections[0]["content"] if flat_sections else "No content available."

        return dropdown_output, flat_sections, initial_preview, book_title
    except Exception as e:
        print(f"Error processing file: {e}")
        return gr.update(choices=[], value=None), [], f"Error processing file: {e}", "Unknown Book"

#-------------------------------------------------------------------------------------------

#-------------------------------------------------------------------------------------------
def extract_odt_structure(odt_file_path):
    def get_full_text(element):
        """Recursively extract text from an XML element and its children."""
        texts = []
        if element.text:
            texts.append(element.text.strip())
        for child in element:
            texts.append(get_full_text(child))
        if element.tail:
            texts.append(element.tail.strip())
        return " ".join(filter(None, texts))

    # Mapping from outline levels to ODT styles
    outline_to_style = {
        1: "Title",
        2: "Heading 1",
        3: "Heading 2",
        4: "Heading 3",
        5: "Heading 4",
        6: "Heading 5",
    }

    try:
        with ZipFile(odt_file_path, 'r') as odt_zip:
            book_title = "Unknown Book"  # Default title
            if 'meta.xml' in odt_zip.namelist():
                with odt_zip.open('meta.xml') as meta_file:
                    meta_content = meta_file.read()
                    meta_root = etree.fromstring(meta_content)
                    namespaces = {
                        'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
                        'dc': 'http://purl.org/dc/elements/1.1/'
                    }
                    title = meta_root.find('.//dc:title', namespaces)
                    book_title = title.text.strip() if title is not None else "Unknown Book"

            # Extract and parse content.xml for headings and content
            if 'content.xml' in odt_zip.namelist():
                with odt_zip.open('content.xml') as content_file:
                    content = content_file.read()
                    content_root = etree.fromstring(content)
                    namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}

                    headings = []
                    current_content = []
                    last_heading = None

                    for element in content_root.iter():
                        tag = element.tag.split('}')[-1]  # Remove namespace
                        if tag == "h":  # Heading
                            # Save the content of the last heading
                            if last_heading is not None:
                                last_heading["content"] = "\n".join(current_content).strip()
                                current_content = []

                            level = element.attrib.get(f'{{{namespaces["text"]}}}outline-level')
                            style = outline_to_style.get(int(level), f"Unknown Level ({level})") if level else "Unknown Style"

                            full_text = get_full_text(element)  # Extract all nested text
                            last_heading = {"style": style, "title": full_text, "content": ""}
                            headings.append(last_heading)

                            # Use the first heading as the book title if meta.xml is unavailable
                            if book_title == "Unknown Book" and style == "Title":
                                book_title = full_text

                        elif tag == "p":  # Paragraph
                            # Collect content for the current heading
                            if last_heading is not None:
                                paragraph_text = get_full_text(element).strip()
                                if paragraph_text:
                                    current_content.append(paragraph_text)

                    # Handle the last heading's content
                    if last_heading is not None:
                        last_heading["content"] = "\n".join(current_content).strip()

            else:
                headings = []

        print(f"Extracted book title: {book_title}")
        return {"title": book_title, "sections": headings}

    except Exception as e:
        raise ValueError(f"Error extracting content from ODT file: {e}")


#-------------------------------------------------------------------------------------------
def generate_audio(selected_title, sections, book_title):
    if not selected_title:
        print("No title selected for TTS.")
        return None

    if not sections:
        print("No sections available for TTS.")
        return None

    # Aggregate content for the selected title
    aggregated_content = get_aggregated_content(selected_title, sections)
    if not aggregated_content:
        print(f"No content found for section: {selected_title}")
        return None

    # Create folder named after the book title
    folder_name = clean_filename(book_title)
    folder_path = os.path.join("demo_outputs", "generated_audios", folder_name)
    os.makedirs(folder_path, exist_ok=True)

    # Generate audio
    try:
        print(f"Generating audio for: {selected_title}")
        audio_path = text_to_audio(
            text=aggregated_content,
            heading=selected_title,
            lang="en",  # Default to English
            speaker_type="Studio",  # Default speaker type
            speaker_name_studio=list(STUDIO_SPEAKERS.keys())[0],  # Default studio speaker
            speaker_name_custom=None  # No custom speaker by default
        )

        # Move the audio to the folder
        if audio_path:
            new_audio_path = os.path.join(folder_path, os.path.basename(audio_path))
            shutil.move(audio_path, new_audio_path)
            print(f"Audio saved to: {new_audio_path}")
            return new_audio_path
        else:
            print("Audio generation failed.")
            return None
    except Exception as e:
        print(f"Error generating audio: {e}")
        return None



def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None,
                  output_format="wav"):
    # Get the first line as the file name
    first_line = text.splitlines()[0] if text else "Untitled"
    file_name = clean_filename(first_line)

    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[
        speaker_name_custom]
    chunks = split_text_into_chunks(heading + "\n" + text)

    cache_dir = os.path.join("demo_outputs", "cache")
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        response = requests.post(
            SERVER_URL + "/tts",
            json={
                "text": chunk,
                "language": lang,
                "speaker_embedding": embeddings["speaker_embedding"],
                "gpt_cond_latent": embeddings["gpt_cond_latent"]
            }
        )
        if response.status_code != 200:
            print(f"Error: Server returned status {response.status_code} for chunk: {chunk}")
            continue

        decoded_audio = base64.b64decode(response.content)
        audio_path = os.path.join(cache_dir, f"{file_name}_{idx + 1}.wav")
        with open(audio_path, "wb") as fp:
            fp.write(decoded_audio)
            cached_audio_paths.append(audio_path)

    if len(cached_audio_paths) > 0:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        final_path = os.path.join("demo_outputs", "generated_audios", f"{file_name}.{output_format}")
        os.rename(combined_audio_path, final_path)
        shutil.rmtree(cache_dir)
        return final_path
    else:
        return None


def split_text_into_chunks(text, max_chars=250, max_tokens=350):

    sentences = re.split(r'(?<=\.) ', text)
    chunks = []
    current_chunk = ""
    current_tokens = 0
    for sentence in sentences:
        sentence_tokens = len(sentence) // 4
        if len(current_chunk) + len(sentence) <= max_chars and current_tokens + sentence_tokens <= max_tokens:
            current_chunk += sentence + " "
            current_tokens += sentence_tokens
        else:
            if len(sentence) > max_chars or sentence_tokens > max_tokens:
                sentence_parts = [sentence[i:i + max_chars] for i in range(0, len(sentence), max_chars)]
                for part in sentence_parts:
                    part_tokens = len(part) // 4
                    if len(current_chunk) + len(part) <= max_chars and current_tokens + part_tokens <= max_tokens:
                        current_chunk += part + " "
                        current_tokens += part_tokens
                    else:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = part + " "
                        current_tokens = part_tokens
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                current_tokens = sentence_tokens
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks


def concatenate_audios(audio_paths, output_format="wav"):
    """
    Kombinerer flere lydfiler til én og eksporterer i det valgte format.
    """
    combined = AudioSegment.empty()
    for path in audio_paths:
        audio = AudioSegment.from_file(path)
        combined += audio

    output_path = os.path.join("demo_outputs", "generated_audios", f"combined_audio_temp.{output_format}")
    combined.export(output_path, format=output_format)
    return output_path

def clean_filename(filename):
    """
    Cleans the filename by removing or replacing invalid characters.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()

def text_to_audio_streaming(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None,
                            speaker_name_custom=None, output_format="wav"):
    # Get embeddings
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[
        speaker_name_custom]
    print("Speaker Embedding:", embeddings["speaker_embedding"])
    print("GPT Condition Latent:", embeddings["gpt_cond_latent"])

    # Split text into manageable chunks
    chunks = split_text_into_chunks(heading + "\n" + text)

    # Create a cache directory for intermediate files
    cache_dir = os.path.join("demo_outputs", "cache")
    if not os.path.exists(cache_dir):
        os.mkdir(cache_dir)

    cached_audio_paths = []
    for idx, chunk in enumerate(chunks):
        # Prepare JSON payload for the streaming API
        stream_input = {
            "text": chunk,
            "language": lang,
            "speaker_embedding": embeddings["speaker_embedding"],
            "gpt_cond_latent": embeddings["gpt_cond_latent"],
            "add_wav_header": True,
            "stream_chunk_size": "20"  # Adjust this as needed
        }

        try:
            with requests.post(SERVER_URL + "/tts_stream", json=stream_input, stream=True, timeout=60) as response:
                if response.status_code != 200:
                    print(f"Error: Server returned status {response.status_code}. Response: {response.text}")
                    continue

                audio_path = os.path.join(cache_dir, f"{heading}_{idx + 1}.wav")
                with open(audio_path, "wb") as audio_file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:  # Skip empty chunks
                            audio_file.write(chunk)
                    cached_audio_paths.append(audio_path)
        except requests.exceptions.RequestException as e:
            print(f"Network error during streaming: {e}")
        except Exception as e:
            print(f"Error during streaming TTS request: {e}")

    # Combine cached audio files into one
    if cached_audio_paths:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        final_path = os.path.join("demo_outputs", "generated_audios", f"{heading}.{output_format}")
        os.rename(combined_audio_path, final_path)

        # Clear cache
        shutil.rmtree(cache_dir)

        return final_path
    else:
        return None
#-------------------------------------------------------------------------------------------
def build_hierarchy(sections):
    hierarchy = []
    stack = []

    style_to_level = {
        "Title": 1,
        "Heading 1": 2,
        "Heading 2": 3,
        "Heading 3": 4,
        "Heading 4": 5,
        "Heading 5": 6,
    }

    for section in sections:
        if "style" not in section or "title" not in section:
            print(f"Invalid section: {section}")
            continue

        level = style_to_level.get(section["style"], 1)
        while stack and style_to_level.get(stack[-1]["style"], 1) >= level:
            stack.pop()

        if stack:
            parent = stack[-1]
            parent.setdefault("subsections", []).append(section)
        else:
            hierarchy.append(section)

        stack.append(section)

    return hierarchy


def get_aggregated_content(selected_title, sections, include_subsections=True):
    aggregated_content = []

    def collect_content(section, include, depth=0):
        indent = "  " * depth
        if section.get("title") == selected_title:
            include = True
            print(f"{indent}*** Matched section: '{section['title']}' (Style: {section.get('style', 'Unknown Style')})")

        if include:
            aggregated_content.append(section.get("content", ""))

        for subsection in section.get("subsections", []):
            collect_content(subsection, include, depth + 1)

    for section in sections:
        collect_content(section, include=False)

    return "\n\n".join(filter(None, aggregated_content))


def display_section(selected_title, sections):
    if not selected_title:
        print("No title selected.")
        return "No content available: No title selected."
    if not sections:
        print("No sections available.")
        return "No content available: No sections found."

    aggregated_content = get_aggregated_content(selected_title, sections)
    if aggregated_content:
        return aggregated_content
    else:
        print(f"No content found for '{selected_title}'")
        return "No content found for the selected section."


#-------------------------------------------------------------------------------------------

# Gradio Interface
with gr.Blocks() as demo:
    sections_state = gr.State([])

    with gr.Row():
        file_input = gr.File(
            label="Upload ODT File",
            file_types=[".odt"],
        )

    with gr.Tab("Process ODT"):
        with gr.Row():
            with gr.Column():
                process_button = gr.Button("Process File")
                section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
                section_preview = gr.Textbox(label="Section Content", lines=10, interactive=True)
                tts_button = gr.Button("Generate Audio")
                audio_output = gr.Audio(label="Generated Audio", interactive=False)

        # File Input Change Action
        file_input.change(
            process_file,
            inputs=[file_input],
            outputs=[section_titles, sections_state, section_preview, gr.State("Unknown Book")],
        )

        # Section Titles Dropdown Change Action
        section_titles.change(
            display_section,
            inputs=[section_titles, sections_state],
            outputs=[section_preview],
        )

        # TTS Button Click Action
        tts_button.click(
            generate_audio,
            inputs=[section_titles, sections_state, gr.State("Unknown Book")],
            outputs=[audio_output],
        )

        process_button.click(
            process_file,
            inputs=[file_input],
            outputs=[section_titles, sections_state, section_preview],
        )

    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )