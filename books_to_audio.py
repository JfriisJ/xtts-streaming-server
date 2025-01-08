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
    Flattens sections and their chapters into a single list for Gradio dropdown choices.
    """
    flat_list = []
    for section in sections:
        flat_list.append({"title": section["title"], "content": section["content"]})
        for chapter in section.get("chapters", []):
            flat_list.append({"title": f"{section['title']} > {chapter['title']}", "content": chapter["content"]})
    return flat_list


def process_file(file):
    """
    Processes the uploaded file and returns dropdown options, sections state, and initial section content.
    """
    if file is None:
        return gr.update(choices=[], value=None), [], "No file uploaded."

    print(f"Processing file: {file.name}")

    try:
        # Process based on file type
        if file.name.endswith('.epub'):
            sections = extract_text_filtered_epub(file.name)
        elif file.name.endswith('.docx'):
            sections = extract_text_filtered_docx(file.name)
        elif file.name.endswith('.txt'):
            sections = extract_text_filtered_txt(file.name, file.name)
        elif file.name.endswith('.pdf'):
            text_from_pdf = extract_text_with_pymupdf(file.name)
            if "No meaningful content" in text_from_pdf[0]:
                return gr.update(choices=[], value=None), [], text_from_pdf[0]
            sections = extract_text_filtered_txt(text_from_pdf, file.name)
        else:
            supported_formats = [".epub", ".txt", ".pdf", ".docx"]
            return gr.update(choices=[], value=None), [], f"Unsupported file format. Please upload one of: {', '.join(supported_formats)}."

        # Flatten and deduplicate sections
        flat_sections = flatten_sections(sections)
        unique_sections = deduplicate_sections(flat_sections)
        section_titles = [item["title"] for item in unique_sections]
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = unique_sections[0]["content"] if unique_sections else "No content available."

        print(f"Dropdown choices: {section_titles}")
        print(f"Initial preview: {initial_preview[:100]}...")

        return dropdown_output, unique_sections, initial_preview

    except Exception as e:
        print(f"Error processing file {file.name}: {e}")
        return gr.update(choices=[], value=None), [], f"An error occurred: {str(e)}"



#------------------------------------------------------------------------------------------------------------
#PDF to text
import fitz  # PyMuPDF
import re
def extract_text_with_pymupdf(file):
    """
    Extract text from a PDF using PyMuPDF, capturing both chapters and uppercase sections.
    Filters out irrelevant lines, overly long sentences, and short uppercase lines.
    """
    text_content = []
    page_number_pattern = re.compile(r"^\s*Page\s*\d+\s*[:\-]*", re.IGNORECASE)  # Matches "Page X:"
    irrelevant_line_pattern = re.compile(r"(ISBN|Version|copyright|©|rights reserved)", re.IGNORECASE)
    sentence_like_pattern = re.compile(r"[.?!]$")  # Ends with sentence punctuation
    chapter_pattern = re.compile(r"^(CHAPTER|Chapter)\s*\d+", re.IGNORECASE)  # Matches "CHAPTER 1", "Chapter 2"

    with fitz.open(file) as pdf_document:
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            text = page.get_text().strip()

            # Remove page numbers
            text = page_number_pattern.sub("", text).strip()

            # Process lines
            lines = text.split('\n')
            processed_lines = []
            for line in lines:
                line = line.strip()

                # Skip irrelevant lines
                if irrelevant_line_pattern.search(line):
                    continue

                # Mark chapters explicitly
                if chapter_pattern.match(line):
                    processed_lines.append(f"__CHAPTER__{line}")
                    continue

                # Mark uppercase lines as sections if meaningful
                if (
                    line.isupper()
                    and 3 <= len(line.split()) <= 10  # Word count threshold
                    and len(line) > 15  # Minimum character length
                    and not sentence_like_pattern.search(line)  # Avoid sentence-like lines
                ):
                    processed_lines.append(f"__SECTION__{line}")
                else:
                    processed_lines.append(line)

            text_content.append("\n".join(processed_lines))  # Append cleaned content

    if not text_content:
        return ["No meaningful content extracted from the PDF."]
    return text_content


#------------------------------------------------------------------------------------------------------------

import re

def deduplicate_sections(sections):
    """
    Remove duplicate or redundant section titles.
    """
    seen = set()
    unique_sections = []
    for section in sections:
        if section["title"] not in seen:
            seen.add(section["title"])
            unique_sections.append(section)
    return unique_sections


def extract_text_filtered_txt(input_data, file_name):
    """
    Process text and group chapters under their corresponding sections.
    Lines marked as __CHAPTER__ or __SECTION__ are used to build a hierarchical structure.
    If no sections are detected, all content is grouped under a single section named after the uploaded file.
    """
    sections = []
    current_section = None
    seen_sections = set()  # Track seen sections to avoid duplicates
    seen_chapters = set()  # Track seen chapters to avoid duplicates

    if isinstance(input_data, list):
        lines = [line for page in input_data for line in page.split('\n')]
    elif isinstance(input_data, str):
        with open(input_data, "r", encoding="utf-8") as file:
            lines = file.readlines()
    else:
        raise TypeError("Expected str (file path) or list (text content)")

    print(f"Total lines to process: {len(lines)}")

    for line in lines:
        line = line.strip()
        if not line or re.match(r"^\d+$", line):  # Skip empty or irrelevant numeric lines
            continue

        # Detect sections
        if line.startswith("__SECTION__"):
            section_title = line.replace("__SECTION__", "").strip()

            if section_title not in seen_sections:
                # Finalize the previous section if it exists
                if current_section:
                    sections.append(current_section)

                # Start a new section
                current_section = {"title": section_title, "content": "", "chapters": []}
                seen_sections.add(section_title)
                print(f"New section detected: {section_title}")

        # Detect chapters
        elif line.startswith("__CHAPTER__"):
            chapter_title = line.replace("__CHAPTER__", "").strip()

            if current_section and chapter_title not in seen_chapters:
                current_section["chapters"].append({"title": chapter_title, "content": ""})
                seen_chapters.add(chapter_title)
                print(f"New chapter detected under section '{current_section['title']}': {chapter_title}")

        # Add content to the current section or chapter
        else:
            if current_section:
                if current_section["chapters"]:
                    # Add to the last chapter
                    current_section["chapters"][-1]["content"] += line + " "
                else:
                    # Add to the section content if no chapters exist yet
                    current_section["content"] += line + " "
            else:
                # If no section, initialize with the file name as the title
                if not current_section:
                    section_title = os.path.splitext(os.path.basename(file_name))[0]
                    current_section = {"title": section_title, "content": line + " ", "chapters": []}

    # Finalize the last section
    if current_section:
        sections.append(current_section)

    print(f"Total unique sections processed: {len(sections)}")
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