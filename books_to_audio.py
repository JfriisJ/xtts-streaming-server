import binascii
import os
import base64
import json
import shutil
from docx import Document
import re
import ebooklib
import requests
from ebooklib import epub
from bs4 import BeautifulSoup
import gradio as gr
from pydub import AudioSegment



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

def flatten_sections(sections):
    """
    Flattens the hierarchical sections into a single list for dropdown choices.
    """
    flat_list = []
    for section in sections:
        flat_list.append({"title": section["title"], "content": section["content"]})
        for subsection in section.get("subsections", []):
            flat_list.append({"title": subsection["title"], "content": subsection["content"]})
            for subsubsection in subsection.get("subsubsections", []):
                flat_list.append({"title": subsubsection["title"], "content": subsubsection["content"]})
    return flat_list

def process_file(file, header_height=1, footer_height=1):
    """
    Processes the uploaded file and returns dropdown options, sections state, and initial section content.
    """
    if file is None:
        return gr.update(choices=[], value=None), [], "No file uploaded."



    # Process based on file type
    if file.name.endswith('.pdf'):
        return "not supported"
    elif file.name.endswith('.epub'):
        sections = extract_text_filtered_epub(file.name)
    elif file.name.endswith('.docx'):
        sections = extract_text_filtered_docx(file.name)
    elif file.name.endswith('.txt'):
        sections = extract_text_filtered_txt(file.name)
    else:
        return gr.update(choices=[], value=None), [], "Unsupported file format."

    # Flatten sections for dropdown
    flat_sections = flatten_sections(sections)
    section_titles = [item["title"] for item in flat_sections]
    dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
    initial_preview = flat_sections[0]["content"] if flat_sections else "No content available."

    return dropdown_output, flat_sections, initial_preview


def extract_text_filtered_txt(file_path):
    """
    Process a plain text file and structure it into sections, subsections, and subsubsections.
    """
    sections = []
    section = None
    subsection = None
    subsubsection = None

    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue  # Skip empty lines

        # Detect sections (e.g., "3. ")
        if re.match(r"^\d+\.\s", line):
            if section:
                sections.append(section)
            section = {"title": line, "content": "", "subsections": []}
            subsection = None
            subsubsection = None
        # Detect subsections (e.g., "3.1. ")
        elif re.match(r"^\d+\.\d+\.\s", line):
            if subsection:
                section["subsections"].append(subsection)
            subsection = {"title": line, "content": "", "subsubsections": []}
            subsubsection = None
        # Detect subsubsections (e.g., "3.1.1. ")
        elif re.match(r"^\d+\.\d+\.\d+\.\s", line):
            if subsubsection:
                subsection["subsubsections"].append(subsubsection)
            subsubsection = {"title": line, "content": ""}
        else:
            # Add content to the current level
            if subsubsection:
                subsubsection["content"] += line + " "
            elif subsection:
                subsection["content"] += line + " "
            elif section:
                section["content"] += line + " "

    # Append the last section, subsection, or subsubsection
    if subsubsection:
        subsection["subsubsections"].append(subsubsection)
    if subsection:
        section["subsections"].append(subsection)
    if section:
        sections.append(section)

    return sections


def extract_text_filtered_docx(docx_file):
    """
    Extract text from a DOCX file, separating content by headings (if present),
    and adding hierarchical numbering (e.g., 1, 1.1, 1.1.1).
    """
    document = Document(docx_file)
    sections = []
    section_counter = 0
    subsection_counter = 0
    subsubsection_counter = 0
    current_level = 0

    for paragraph in document.paragraphs:
        if paragraph.style.name.startswith("Heading"):
            heading_level = int(paragraph.style.name[-1])  # Extract heading level (e.g., Heading 1 -> 1)

            # Adjust counters based on the heading level
            if heading_level == 1:
                section_counter += 1
                subsection_counter = 0
                subsubsection_counter = 0
                current_title = f"Section {section_counter}: {paragraph.text.strip()}"
            elif heading_level == 2:
                subsection_counter += 1
                subsubsection_counter = 0
                current_title = f"Subsection {section_counter}.{subsection_counter}: {paragraph.text.strip()}"
            elif heading_level == 3:
                subsubsection_counter += 1
                current_title = f"Subsubsection {section_counter}.{subsection_counter}.{subsubsection_counter}: {paragraph.text.strip()}"
            else:
                print(f"Skipping unsupported heading: {paragraph.text.strip()}")

            # Add the section with its hierarchical number
            sections.append({"title": current_title, "content": ""})

        else:
            # Add paragraph text to the latest section
            if sections:
                sections[-1]["content"] += paragraph.text.strip() + "\n"

    # Filter out empty sections
    return [section for section in sections if section["content"].strip()]


def extract_text_filtered_epub(epub_file):
    """
    Extract structured text from an EPUB file with hierarchical numbering
    (e.g., Section 1, Subsection 1.1, Subsubsection 1.1.1).
    """
    book = epub.read_epub(epub_file)
    sections = []
    section_counter = 0
    subsection_counter = 0
    subsubsection_counter = 0

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            body = soup.find('body')
            if not body:
                continue

            for tag in body.find_all(['h1', 'h2', 'h3']):
                section_title = tag.get_text().strip()

                # Determine heading level and assign numbering
                if tag.name == 'h1':
                    section_counter += 1
                    subsection_counter = 0
                    subsubsection_counter = 0
                    numbered_title = f"Section {section_counter}: {section_title}"
                elif tag.name == 'h2':
                    subsection_counter += 1
                    subsubsection_counter = 0
                    numbered_title = f"Subsection {section_counter}.{subsection_counter}: {section_title}"
                elif tag.name == 'h3':
                    subsubsection_counter += 1
                    numbered_title = f"Subsubsection {section_counter}.{subsection_counter}.{subsubsection_counter}: {section_title}"
                else:
                    print(f"Skipping unsupported tag: {tag.name}")

                # Extract content for the current section
                section_content = []
                for sibling in tag.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3']:
                        break  # Stop at the next heading
                    text = sibling.get_text().strip()
                    if text.isdigit() or "Chapter" in text or len(text) < 3:
                        continue
                    section_content.append(text)

                # Append section with its hierarchical numbering
                if section_content:
                    sections.append({"title": numbered_title, "content": "\n".join(section_content)})

    return sections


def text_to_audio(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None, output_format="wav"):
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
    chunks = split_text_into_chunks(heading + "\n" + text)

    # Opret en cache-mappe
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

        try:
            decoded_audio = base64.b64decode(response.content)
        except binascii.Error as e:
            print(f"Error decoding audio for chunk: {e}")
            continue

        audio_path = os.path.join(cache_dir, f"{heading}_{idx + 1}.wav")
        with open(audio_path, "wb") as fp:
            fp.write(decoded_audio)
            cached_audio_paths.append(audio_path)

    # Kombiner cachede filer og eksportér i ønsket format
    if len(cached_audio_paths) > 0:
        combined_audio_path = concatenate_audios(cached_audio_paths, output_format)
        final_path = os.path.join("demo_outputs", "generated_audios", f"{heading}.{output_format}")
        os.rename(combined_audio_path, final_path)

        # Ryd cache
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


def display_section(selected_title, sections):
    for section in sections:
        if section["title"] == selected_title:
            return section["content"]
    return "Section not found."


# Gradio Interface
with gr.Blocks() as demo:
    cloned_speaker_names = gr.State(list(cloned_speakers.keys()))
    sections_state = gr.State([])


    with gr.Row():
        file_input = gr.File(label="Upload Text, EPUB, PDF or Docx File", file_types=[".epub", ".txt", ".pdf", ".docx"])

    with gr.Row():
        speaker_type = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
        lang = gr.Dropdown(label="Language", choices=LANGUAGES, value="en")
        speaker_name_studio = gr.Dropdown(
            label="Studio speaker",
            choices=STUDIO_SPEAKERS.keys(),
            value="Abrahan Mack" if "Abrahan Mack" in STUDIO_SPEAKERS.keys() else None,
        )
        speaker_name_custom = gr.Dropdown(
            label="Cloned speaker",
            choices=cloned_speaker_names.value,
            value=cloned_speaker_names.value[0] if len(cloned_speaker_names.value) != 0 else None,
        )


    # Text/Section Processing Tab
    with gr.Tab("Process Text/EPUB/docx"):
        with gr.Row():
            with gr.Column() as process_col:
                process_button = gr.Button("Process File")
                section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
                section_preview = gr.Textbox(label="Preview Section Content", lines=10)
            with gr.Column() as audio_col:
                with gr.Row():
                    output_format = gr.Dropdown(label="Output Format", choices=["wav", "mp3"], value="wav")
                    generate_audio_button = gr.Button("Generate Audio")
                audio_output = gr.Audio(label="Generated Audio")

        generate_audio_button.click(
            text_to_audio,
            inputs=[section_preview, section_titles, lang, speaker_type, speaker_name_studio, speaker_name_custom,
                    output_format],
            outputs=[audio_output]
        )

        # File Input Change Action
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[section_titles, sections_state, section_preview]
    )



    section_titles.change(
        display_section,
        inputs=[section_titles, sections_state],
        outputs=[section_preview]
    )

    process_button.click(
        process_file,
        inputs=[file_input],
        outputs=[section_titles, sections_state, section_preview]  # Include `section_preview`
    )

    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )