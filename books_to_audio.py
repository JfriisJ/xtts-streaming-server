import binascii
import os
import tempfile
import base64
import json

import pdfplumber
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


def process_file(file, header_height=1, footer_height=1):
    """
    Processes the uploaded file and returns dropdown options, sections state, and initial section content.
    """
    if file is None:
        return gr.update(choices=[], value=None), [], "No file uploaded."

    if file.name.endswith('.pdf'):
        sections = extract_text_filtered_pdf(file.name, header_height, footer_height)
        section_titles = [section["title"] for section in sections]
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = sections[0]["content"] if sections else "No content available."
        return dropdown_output, sections, initial_preview

    elif file.name.endswith('.epub'):
        sections = extract_text_filtered_epub(file.name)
        section_titles = [section["title"] for section in sections]
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = sections[0]["content"] if sections else "No content available."
        return dropdown_output, sections, initial_preview

    elif file.name.endswith('.docx'):
        sections = extract_text_filtered_docx(file.name)
        section_titles = [section["title"] for section in sections]
        dropdown_output = gr.update(choices=section_titles, value=section_titles[0] if section_titles else None)
        initial_preview = sections[0]["content"] if sections else "No content available."
        return dropdown_output, sections, initial_preview

    elif file.name.endswith('.txt'):
        with open(file.name, 'r', encoding='utf-8') as f:
            text = f.read()
        dropdown_output = gr.update(choices=["Text File Content"], value="Text File Content")
        initial_preview = text
        return dropdown_output, [{"title": "Text File Content", "content": text}], initial_preview

    else:
        return gr.update(choices=[], value=None), [], "Unsupported file format."




def update_pdf_controls(file):
    """
    Dynamically updates the visibility of PDF-specific controls.
    """
    if file is None:
        return (
            gr.update(visible=False),  # preview_page_selector
            gr.update(visible=False),  # header_preview_slider
            gr.update(visible=False),  # footer_preview_slider
            gr.update(visible=False)   # preview_image
        )

    if file.name.endswith('.pdf'):
        return (
            gr.update(visible=True),  # preview_page_selector
            gr.update(visible=True),  # header_preview_slider
            gr.update(visible=True),  # footer_preview_slider
            gr.update(visible=True)   # preview_image
        )
    else:
        return (
            gr.update(visible=False),  # preview_page_selector
            gr.update(visible=False),  # header_preview_slider
            gr.update(visible=False),  # footer_preview_slider
            gr.update(visible=False)   # preview_image
        )


def extract_text_filtered_docx(docx_file):
    """
    Extract text from a DOCX file, separating content by headings (if present).
    """
    document = Document(docx_file)
    sections = []
    current_section = None
    current_text = []

    for paragraph in document.paragraphs:
        if paragraph.style.name.startswith("Heading"):
            # Save current section before starting a new one
            if current_section and current_text:
                sections.append({"title": current_section, "content": "\n".join(current_text)})
                current_text = []
            current_section = paragraph.text.strip()
        else:
            # Add paragraph text to the current section
            if paragraph.text.strip():
                current_text.append(paragraph.text.strip())

    # Save the last section
    if current_section and current_text:
        sections.append({"title": current_section, "content": "\n".join(current_text)})

    return sections

def extract_text_filtered_pdf(pdf_file, header_height, footer_height):
    """
    Extract structured text from a PDF, organized by headings (H1, H2, H3),
    and dynamically filter out headers, footers, ToC, and irrelevant sections.
    """
    sections = []
    current_section = None
    current_text = []

    def is_toc_line(line):
        """Determine if a line is part of the Table of Contents."""
        # Match patterns like: "1. Introduction .......... 1" or "1.1 Background ..... 3"
        return re.match(r'^\s*\d+(\.\d+)*\s+.+\.{3,}\s*\d+\s*$', line)

    def is_metadata_or_irrelevant(section):
        """Filter out metadata-like or irrelevant sections."""
        content = section["content"].strip()
        if len(content) < 20:  # Exclude very short content
            return True
        if re.match(r'^([\.\s\d]+)$', content):  # Contains only dots or numbers
            return True
        if re.search(r'\.{3,}', content):  # Contains dotted leaders
            return True
        return False

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            # Filter content to exclude headers and footers
            filtered_text = page.filter(
                lambda obj: header_height < obj["top"] < page.height - footer_height
            ).extract_text()

            if not filtered_text:
                continue

            for line in filtered_text.split("\n"):
                line = line.strip()
                if not line or is_toc_line(line):  # Skip empty lines and ToC lines
                    continue

                # Detect headings and group content under them
                if re.match(r"^\d+\.\s.+", line):  # H1 example (e.g., "1. Title")
                    if current_section and current_text:  # Save non-empty sections
                        sections.append({"title": current_section, "content": " ".join(current_text)})
                        current_text = []
                    current_section = line
                elif re.match(r"^\d+\.\d+\s.+", line):  # H2 example (e.g., "1.1 Subtitle")
                    if current_section and current_text:  # Save non-empty sections
                        sections.append({"title": current_section, "content": " ".join(current_text)})
                        current_text = []
                    current_section = line
                elif re.match(r"^\d+\.\d+\.\d+\s.+", line):  # H3 example (e.g., "1.1.1 Sub-subtitle")
                    if current_section and current_text:  # Save non-empty sections
                        sections.append({"title": current_section, "content": " ".join(current_text)})
                        current_text = []
                    current_section = line
                else:
                    # Append regular content under the current section
                    current_text.append(line)

    # Save the last section
    if current_section and current_text:
        sections.append({"title": current_section, "content": " ".join(current_text)})

    # Filter out irrelevant sections and empty content
    return [section for section in sections if section["content"].strip() and not is_metadata_or_irrelevant(section)]


def extract_text_filtered_epub(epub_file):
    book = epub.read_epub(epub_file)
    sections = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.content, 'html.parser')
            body = soup.find('body')
            if not body:
                continue
            for tag in body.find_all(['h1', 'h2', 'h3']):
                section_title = tag.get_text().strip()
                section_content = []
                for sibling in tag.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3']:
                        break
                    text = sibling.get_text().strip()
                    if text.isdigit() or "Chapter" in text or len(text) < 3:
                        continue
                    section_content.append(text)
                if section_content:
                    sections.append({"title": section_title, "content": "\n".join(section_content)})
    return sections


def text_to_audio_with_heading(text, heading, lang="en", speaker_type="Studio", speaker_name_studio=None, speaker_name_custom=None):
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
    chunks = split_text_into_chunks(heading + "\n" + text)
    generated_audio_paths = []
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
        generated_audio = response.content
        try:
            decoded_audio = base64.b64decode(generated_audio)
        except binascii.Error as e:
            print(f"Error decoding audio for chunk: {e}")
            continue
        audio_path = os.path.join("demo_outputs", "generated_audios", f"{heading}_{idx + 1}.wav")
        with open(audio_path, "wb") as fp:
            fp.write(decoded_audio)
            generated_audio_paths.append(audio_path)

    # If multiple audio paths, concatenate them into a single file
    if len(generated_audio_paths) > 1:
        combined_audio_path = concatenate_audios(generated_audio_paths)
        final_path = os.path.join("demo_outputs", "generated_audios", f"{heading}.wav")
        os.rename(combined_audio_path, final_path)
        return final_path  # Return single combined file path
    elif generated_audio_paths:
        return generated_audio_paths[0]  # Return single file path
    else:
        return None  # Return None if no audio was generated


def preview_pdf_with_header_footer(pdf_file, header_height, footer_height, page_number):
    import pdfplumber

    with pdfplumber.open(pdf_file.name) as pdf:
        if page_number < 1 or page_number > len(pdf.pages):
            return "Invalid page number selected."
        page = pdf.pages[page_number - 1]
        img = page.to_image()

        # Draw header and footer areas
        img.draw_rects([{"x0": 0, "top": 0, "x1": page.width, "bottom": header_height}], stroke="red", fill=(255, 0, 0, 77))
        img.draw_rects([{"x0": 0, "top": page.height - footer_height, "x1": page.width, "bottom": page.height}], stroke="blue", fill=(0, 0, 255, 77))

        temp_image_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        img.save(temp_image_path)
        return temp_image_path


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

def concatenate_audios(audio_paths):
    combined = AudioSegment.empty()
    for path in audio_paths:
        audio = AudioSegment.from_file(path)
        combined += audio
    output_path = os.path.join("demo_outputs", "generated_audios", "combined_audio_temp.wav")
    combined.export(output_path, format="wav")
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
            value="Asya Anara" if "Asya Anara" in STUDIO_SPEAKERS.keys() else None,
        )
        speaker_name_custom = gr.Dropdown(
            label="Cloned speaker",
            choices=cloned_speaker_names.value,
            value=cloned_speaker_names.value[0] if len(cloned_speaker_names.value) != 0 else None,
        )


    # PDF-specific controls (initially hidden)
    with gr.Row() as pdf_controls:
        preview_page_selector = gr.Number(visible=False, label="Page Number", value=1, precision=0)
        header_preview_slider = gr.Slider(visible=False, label="Header Height", minimum=0, maximum=200, value=0, step=1)
        footer_preview_slider = gr.Slider(visible=False, label="Footer Height", minimum=0, maximum=200, value=0, step=1)
        preview_image = gr.Image(visible=False, label="Preview with Header/Footer")

    # Text/Section Processing Tab
    with gr.Tab("Process Text/EPUB/PDF/docx"):
        with gr.Row():
            with gr.Column() as process_col:
                process_button = gr.Button("Process File")
                section_titles = gr.Dropdown(label="Select Section", choices=[], interactive=True, value=None)
                section_preview = gr.Textbox(label="Preview Section Content", lines=10)
            with gr.Column() as audio_col:
                generate_audio_button = gr.Button("Generate Audio")
                audio_output = gr.Audio(label="Generated Audio")

        generate_audio_button.click(
            text_to_audio_with_heading,
            inputs=[section_preview, section_titles, lang, speaker_type, speaker_name_studio, speaker_name_custom],
            outputs=[audio_output]
        )

        # File Input Change Action
    file_input.change(
        process_file,
        inputs=[file_input],
        outputs=[section_titles, sections_state, section_preview]
    )

    # Dynamically Update PDF Controls Visibility
    file_input.change(
        update_pdf_controls,
        inputs=[file_input],
        outputs=[
            preview_page_selector,
            header_preview_slider,
            footer_preview_slider,
            preview_image
        ]
    )

    # Dynamically Update Preview on Slider or Page Changes
    preview_page_selector.change(
        preview_pdf_with_header_footer,
        inputs=[file_input, header_preview_slider, footer_preview_slider, preview_page_selector],
        outputs=[preview_image]
    )

    header_preview_slider.change(
        preview_pdf_with_header_footer,
        inputs=[file_input, header_preview_slider, footer_preview_slider, preview_page_selector],
        outputs=[preview_image]
    )

    footer_preview_slider.change(
        preview_pdf_with_header_footer,
        inputs=[file_input, header_preview_slider, footer_preview_slider, preview_page_selector],
        outputs=[preview_image]
    )

    section_titles.change(
        display_section,
        inputs=[section_titles, sections_state],
        outputs=[section_preview]
    )

    process_button.click(
        process_file,
        inputs=[file_input, header_preview_slider, footer_preview_slider],
        outputs=[section_titles, sections_state, section_preview]  # Include `section_preview`
    )

    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )