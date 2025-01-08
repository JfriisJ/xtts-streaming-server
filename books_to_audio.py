import os
import base64
import json
import shutil
import re
import requests
from bs4 import BeautifulSoup
import gradio as gr
from pydub import AudioSegment


#-------------------------------------------------------------------------------------------
SERVER_URL = 'http://localhost:8000'
OUTPUT = "./demo_outputs"
cloned_speakers = {}

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



def test_tts(text, lang, speaker_type, speaker_name_studio, speaker_name_custom):
    # Warm-up code here...
    start_time = time.time()
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
    response = requests.post(
        SERVER_URL + "/tts",
        json={
            "text": text,
            "language": lang,
            "speaker_embedding": embeddings["speaker_embedding"],
            "gpt_cond_latent": embeddings["gpt_cond_latent"]
        }
    )
    if response.status_code == 200:
        print(f"TTS request completed in {time.time() - start_time:.2f} seconds.")
    else:
        print(f"TTS request failed: {response.status_code} - {response.text}")


def test_tts_streaming(text, lang, speaker_type, speaker_name_studio, speaker_name_custom):
    # Warm-up code here...
    start_time = time.time()
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
    response = requests.post(
        SERVER_URL + "/tts_stream",
        json={
            "text": text,
            "language": lang,
            "speaker_embedding": embeddings["speaker_embedding"],
            "gpt_cond_latent": embeddings["gpt_cond_latent"],
            "add_wav_header": True,
            "stream_chunk_size": "10"
        },
        stream=True
    )
    if response.status_code == 200:
        print(f"TTS streaming request completed in {time.time() - start_time:.2f} seconds.")
    else:
        print(f"TTS streaming request failed: {response.status_code} - {response.text}")

test_tts("Hello, how are you doing today?", "en", "Studio", "Abrahan Mack", None)
test_tts_streaming("Hello, how are you doing today?", "en", "Studio", "Abrahan Mack", None)


#-------------------------------------------------------------------------------------------
def flatten_sections(sections):
    """
    Recursively flattens hierarchical sections into a single list for dropdown choices.
    """
    flat_list = []

    def add_section(section):
        flat_list.append({"title": section["title"], "content": section["content"]})
        for subsection in section.get("subsections", []):
            add_section(subsection)

    for section in sections:
        add_section(section)

    return flat_list



def process_file(file):
    if file is None:
        return gr.update(choices=[], value=None), [], "No file uploaded."

    try:
        sections = extract_text_filtered_odt(file.name)
        if not sections:
            return gr.update(choices=[], value=None), [], "No sections found in the document."

        flat_sections = flatten_sections(sections)
        section_titles = [item["title"] for item in flat_sections]
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = flat_sections[0]["content"] if flat_sections else "No content available."

        return dropdown_output, flat_sections, initial_preview

    except Exception as e:
        return gr.update(choices=[], value=None), [], f"Error processing ODT file: {e}"




#-------------------------------------------------------------------------------------------


def extract_text_filtered_odt(odt_file_path):
    from lxml import etree
    from zipfile import ZipFile

    try:
        print(f"Opening ODT file: {odt_file_path}")

        with ZipFile(odt_file_path, 'r') as odt_zip:
            if 'content.xml' not in odt_zip.namelist():
                raise ValueError("content.xml not found in ODT file.")
            with odt_zip.open('content.xml') as content_file:
                content = content_file.read()

        root = etree.fromstring(content)
        namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}

        sections = []
        current_section = {"title": "Untitled Section", "content": "", "subsections": []}
        heading_count = 0
        paragraph_count = 0

        for element in root.iter():
            # Skip irrelevant or empty tags
            if element.text is None or not element.text.strip():
                continue

            if element.tag.endswith('h'):
                heading_count += 1
                title = element.text.strip()
                # Handle section creation
                if current_section and current_section["content"]:
                    sections.append(current_section)
                current_section = {"title": title, "content": "", "subsections": []}
            elif element.tag.endswith('p'):
                paragraph_count += 1
                text = element.text.strip()
                current_section["content"] += text + "\n"

        # Append the final section
        if current_section and current_section["content"]:
            sections.append(current_section)

        print(f"Extraction complete. Total sections: {len(sections)}, headings: {heading_count}, paragraphs: {paragraph_count}")
        return sections

    except Exception as e:
        print(f"Error during ODT extraction: {e}")
        raise ValueError(f"Error extracting content from ODT file: {e}")



#-------------------------------------------------------------------------------------------

# Function to group content into sections based on numeric patterns
def group_by_sections(text_blocks):
    sections = []
    current_section = None

    for block in text_blocks:
        # Match section/subsection headers (e.g., 1., 1.1, 2.5.1)
        header_match = re.match(r"^\d+(\.\d+)*\s", block)
        if header_match:
            # Start a new section
            if current_section:
                sections.append(current_section)
            current_section = {"title": block.strip(), "content": ""}
        else:
            # Add content to the current section
            if current_section:
                current_section["content"] += block.strip() + "\n"
                print(block)

    # Append the last section if any
    if current_section:
        print(current_section)
        sections.append(current_section)

    return sections


#-------------------------------------------------------------------------------------------



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


def display_section(selected_title, sections):
    for section in sections:
        if section["title"] == selected_title:
            return section["content"]
    return "Section not found."


with gr.Blocks() as demo:
    sections_state = gr.State([])

    # File Upload Row
    with gr.Row():
        file_input = gr.File(
            label="Upload ODT File",
            file_types=[".odt"],  # Only allow ODT files
        )

    # Text/Section Processing Tab
    with gr.Tab("Process ODT"):
        with gr.Row():
            with gr.Column() as process_col:
                # Button to Process File
                process_button = gr.Button("Process File")
                # Dropdown for Section Titles
                section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
                # Textbox to Preview Section Content
                section_preview = gr.Textbox(label="Section Content", lines=10, interactive=True)
            with gr.Column() as tts_col:
                with gr.Row():
                    # Dropdown for TTS Output Format
                    output_format = gr.Dropdown(label="Output Format", choices=["wav", "mp3"], value="wav")
                    # Button to Generate Audio
                    tts_button = gr.Button("Generate Audio")
                # Audio Output
                audio_output = gr.Audio(label="Generated Audio")

        # File Input Change Action
        file_input.change(
            process_file,
            inputs=[file_input],
            outputs=[section_titles, sections_state, section_preview],
        )

        # Section Titles Dropdown Change Action
        section_titles.change(
            display_section,
            inputs=[section_titles, sections_state],
            outputs=[section_preview],
        )

        # Process Button Click Action
        process_button.click(
            process_file,
            inputs=[file_input],
            outputs=[section_titles, sections_state, section_preview],
        )

        # TTS Button Click Action
        tts_button.click(
            text_to_audio,
            inputs=[section_preview, section_titles, output_format],
            outputs=[audio_output],
        )

    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )
