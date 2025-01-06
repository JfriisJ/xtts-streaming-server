import ebooklib
import gradio as gr
import requests
import base64
import tempfile
import json
import os


SERVER_URL = 'http://localhost:8000'
OUTPUT = "./demo_outputs"
cloned_speakers = {}

from threading import Event

stop_event = Event()
header_slider = gr.Slider(label="Header Height", minimum=0, maximum=200, value=50, step=1)
footer_slider = gr.Slider(label="Footer Height", minimum=0, maximum=200, value=60, step=1)

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
    LANUGAGES = requests.get(SERVER_URL + "/languages").json()
    print("Available languages:", ", ".join(LANUGAGES))
    STUDIO_SPEAKERS = requests.get(SERVER_URL + "/studio_speakers").json()
    print("Available studio speakers:", ", ".join(STUDIO_SPEAKERS.keys()))
except:
    raise Exception("Please make sure the server is running first.")


def clone_speaker(upload_file, clone_speaker_name, cloned_speaker_names):
    files = {"wav_file": ("reference.wav", open(upload_file, "rb"))}
    embeddings = requests.post(SERVER_URL + "/clone_speaker", files=files).json()
    with open(os.path.join(OUTPUT, "cloned_speakers", clone_speaker_name + ".json"), "w") as fp:
        json.dump(embeddings, fp)
    cloned_speakers[clone_speaker_name] = embeddings
    cloned_speaker_names.append(clone_speaker_name)
    return upload_file, clone_speaker_name, cloned_speaker_names, gr.Dropdown.update(choices=cloned_speaker_names)

def tts(text, speaker_type, speaker_name_studio, speaker_name_custom, lang):
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]
    generated_audio = requests.post(
        SERVER_URL + "/tts",
        json={
            "text": text,
            "language": lang,
            "speaker_embedding": embeddings["speaker_embedding"],
            "gpt_cond_latent": embeddings["gpt_cond_latent"]
        }
    ).content
    generated_audio_path = os.path.join("demo_outputs", "generated_audios", next(tempfile._get_candidate_names()) + ".wav")
    with open(generated_audio_path, "wb") as fp:
        fp.write(base64.b64decode(generated_audio))
        return fp.name

import PyPDF2  # Add this to requirements if not already there

def read_pdf(file_path):
    """Read text from a PDF file."""
    with open(file_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
    return text

import pdfplumber
import re

def read_pdf_with_plumber(file_path, pages=None, header_height=50, footer_height=60):
    """
    Read text from a PDF file, skip headers/footers, fix hyphenated word splits,
    and process only specified pages.
    """
    all_text = []
    with pdfplumber.open(file_path) as pdf:
        # Determine pages to process
        selected_pages = range(len(pdf.pages)) if pages is None else pages

        for page_num in selected_pages:
            if page_num < len(pdf.pages):  # Ensure the page exists
                page = pdf.pages[page_num]
                # Filter objects to exclude headers and footers dynamically
                text = page.filter(
                    lambda obj: (
                        header_height < obj["top"] < page.height - footer_height
                    )
                ).extract_text()

                if text:
                    # Remove hyphenation at line breaks
                    text = re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)
                    # Replace line breaks with spaces to preserve sentence structure
                    text = text.replace("\n", " ")

                all_text.append(text)
    return " ".join(all_text)


from ebooklib import epub

def read_epub(file_path):
    """Extract text from an EPUB file."""
    book = epub.read_epub(file_path)
    text = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            text.append(item.get_content().decode())
    return " ".join(text)

def read_txt(file_path):
    """Read text from a TXT file."""
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

def split_text_into_chunks(text, max_chars=250, max_tokens=300):
    """
    Split text into chunks of up to max_chars characters and max_tokens tokens,
    ensuring the split happens at sentence boundaries if possible.
    """
    import re
    sentences = re.split(r'(?<=\.) ', text)  # Split by sentences
    chunks = []
    current_chunk = ""
    current_tokens = 0

    for sentence in sentences:
        # Estimate token count for the sentence (1 token ≈ 4 characters)
        sentence_tokens = len(sentence) // 4

        # Ensure chunk stays within character and token limits
        if len(current_chunk) + len(sentence) <= max_chars and current_tokens + sentence_tokens <= max_tokens:
            current_chunk += sentence + " "
            current_tokens += sentence_tokens
        else:
            # If a single sentence exceeds the limits, split the sentence itself
            if len(sentence) > max_chars or sentence_tokens > max_tokens:
                sentence_parts = [sentence[i:i+max_chars] for i in range(0, len(sentence), max_chars)]
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
                # Finalize the current chunk and start a new one
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
                current_tokens = sentence_tokens

    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def parse_page_range(page_range):
    """
    Parse a page range string (e.g., "1-3,5") into a list of zero-based page indices.
    """
    pages = []
    for part in page_range.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            pages.extend(range(start - 1, end))  # Convert to zero-based indices
        else:
            pages.append(int(part) - 1)
    return pages



def generate_audio_from_file(file, output_dir, speaker_type, speaker_name_studio, speaker_name_custom, lang, page_range, header_height, footer_height):
    """Generate audio for text extracted from PDF, EPUB, or TXT files."""
    stop_event.clear()
    file_path = file.name  # Access the shared file path
    file_title = os.path.splitext(os.path.basename(file_path))[0]  # Get the file title without extension
    file_ext = os.path.splitext(file_path)[1].lower()  # Get the file extension

    # Read text based on file type
    if file_ext == '.pdf':
        pages = parse_page_range(page_range)
        text = read_pdf_with_plumber(file_path, pages=pages, header_height=header_height, footer_height=footer_height)
    elif file_ext == '.epub':
        text = read_epub(file_path)
    elif file_ext == '.txt':
        text = read_txt(file_path)
    else:
        raise ValueError("Unsupported file type. Please upload a PDF, EPUB, or TXT file.")

    # Split text into chunks
    chunks = split_text_into_chunks(text)
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]

    for i, chunk in enumerate(chunks):
        if stop_event.is_set():
            print("Process stopped by user.")
            break

        if len(chunk) > 250:
            print(f"Warning: Chunk {i + 1} exceeds 250 characters and might cause truncation.")

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
            print(f"Error generating audio for chunk {i + 1}: {response.json()}")
            continue

        try:
            generated_audio = response.content
            decoded_audio = base64.b64decode(generated_audio)
        except base64.binascii.Error as e:
            print(f"Error decoding base64 for chunk {i + 1}: {e}")
            continue

        # Create a unique filename using the file title and chunk number
        audio_filename = f"{file_title}_{i + 1}.wav"
        audio_path = os.path.join(output_dir, audio_filename)
        with open(audio_path, "wb") as audio_file:
            audio_file.write(decoded_audio)
        print(f"Saved audio chunk {i + 1} to {audio_path}")




def stop_process():
    """Set the stop flag to interrupt the current process."""
    stop_event.set()
    return "Process stopped."

def preview_file_with_area(file, header_height, footer_height, page_number):
    """Preview the content of the uploaded file based on its type."""
    import pdfplumber

    file_path = file.name
    file_ext = os.path.splitext(file_path)[1].lower()

    if file_ext == ".pdf":
        try:
            # Handle PDF preview
            with pdfplumber.open(file_path) as pdf:
                if page_number < 1 or page_number > len(pdf.pages):
                    return "Invalid page number selected."
                page = pdf.pages[int(page_number) - 1]  # Convert 1-based to 0-based index
                img = page.to_image()

                # Draw header and footer areas
                header_fill = (255, 0, 0, 77)  # Red with 30% opacity
                footer_fill = (0, 0, 255, 77)  # Blue with 30% opacity
                img.draw_rects([{"x0": 0, "top": 0, "x1": page.width, "bottom": header_height}], stroke="red", fill=header_fill)
                img.draw_rects([{"x0": 0, "top": page.height - footer_height, "x1": page.width, "bottom": page.height}], stroke="blue", fill=footer_fill)

                # Save the image to a temporary file and return its path
                temp_image_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
                img.save(temp_image_path)
                return temp_image_path, None  # Image preview for PDF
        except Exception as e:
            return f"Error processing PDF: {e}", None

    elif file_ext == ".txt":
        # Handle TXT preview
        try:
            with open(file_path, "r", encoding="utf-8") as txt_file:
                lines = txt_file.readlines()
            # Preview the first few lines
            preview_text = "".join(lines[:10])  # Show first 10 lines
            return None, f"Preview of TXT file:\n\n{preview_text}"  # Text preview
        except Exception as e:
            return None, f"Error processing TXT file: {e}"

    elif file_ext == ".epub":
        # Handle EPUB preview
        try:
            text = read_epub(file_path)
            preview_text = text[:1000]  # Show the first 1000 characters
            return None, f"Preview of EPUB file:\n\n{preview_text}"  # Text preview
        except Exception as e:
            return None, f"Error processing EPUB file: {e}"

    else:
        return None, "Unsupported file type. Please upload a PDF, TXT, or EPUB file."


with gr.Blocks() as demo:
    cloned_speaker_names = gr.State(list(cloned_speakers.keys()))

    # TTS and Studio Speaker Settings
    speaker_name_studio = gr.Dropdown(
        label="Studio speaker",
        choices=STUDIO_SPEAKERS.keys(),
        value="Asya Anara" if "Asya Anara" in STUDIO_SPEAKERS.keys() else None,
    )
    lang = gr.Dropdown(label="Language", choices=LANUGAGES, value="en")
    speaker_name_custom = gr.Dropdown(
        label="Cloned speaker",
        choices=cloned_speaker_names.value,
        value=cloned_speaker_names.value[0] if len(cloned_speaker_names.value) != 0 else None,
    )

    # TTS Tab
    with gr.Tab("TTS"):
        with gr.Column() as row4:
            speaker_name_studio
            speaker_name_custom
            speaker_type = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
            text = gr.Textbox(label="text", value="A quick brown fox jumps over the lazy dog.")
            tts_button = gr.Button(value="TTS")
            generated_audio = gr.Audio(label="Generated audio", autoplay=True)

    # Clone Speaker Tab
    with gr.Tab("Clone a new speaker"):
        with gr.Column() as col1:
            upload_file = gr.Audio(label="Upload reference audio", type="filepath")
            clone_speaker_name = gr.Textbox(label="Speaker name", value="default_speaker")
            clone_button = gr.Button(value="Clone speaker")



    # Generate Audio Tab
    with gr.Tab("Generate Audio from file"):
        # Shared components
        file = gr.File(label="Upload File", type="filepath", file_types=[".pdf", ".txt", ".epub"])
        page_range = gr.Textbox(label="Page Range (e.g., 1-3,5)", value="1", placeholder="Enter pages to process")
        page_selector = gr.Number(label="Page Number", value=1, precision=0)  # Page selector for preview




        with gr.Column() as col3:
            speaker_name_studio
            speaker_name_custom
            with gr.Tab("PDF"):
                header_slider = gr.Slider(label="Header Height", minimum=0, maximum=400, value=50, step=1)
                footer_slider = gr.Slider(label="Footer Height", minimum=0, maximum=400, value=50, step=1)
                preview_image = gr.Image(label="Content Area Preview")  # For PDF previews
            with gr.Tab("EPUB/TXT"):
                preview_text = gr.Textbox(label="File Content Preview", lines=10)  # For TXT/EPUB previews
            # Optionally include a preview button (manual refresh)
            preview_button = gr.Button(value="Refresh Preview")
            output_dir = gr.Textbox(label="Output Directory", value="./demo_outputs/generated_audios")
            generate_audio_button = gr.Button(value="Generate Audio")
            stop_button = gr.Button(value="Stop")
            stop_message = gr.Label(value="", label="Process Status")
            processing_message = gr.Label(value="", label="Processing...")

    preview_button.click(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=[preview_image, preview_text],
    )

    # Dynamically update preview based on sliders or page changes
    header_slider.change(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )
    footer_slider.change(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )
    page_selector.change(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )
    # Preview button for manual refresh (optional)

    preview_button.click(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )

    # Preview Button Action
    page_selector.change(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )

    # Preview Button Action
    preview_button.click(
        fn=preview_file_with_area,
        inputs=[file, header_slider, footer_slider, page_selector],
        outputs=preview_image
    )
    # Generate Audio Button Action
    generate_audio_button.click(
        fn=generate_audio_from_file,
        inputs=[file, output_dir, speaker_type, speaker_name_studio, cloned_speaker_names, lang, page_range, header_slider, footer_slider],
        outputs=processing_message,
    )

    clone_button.click(
        fn=clone_speaker,
        inputs=[upload_file, clone_speaker_name, cloned_speaker_names],
        outputs=[upload_file, clone_speaker_name, cloned_speaker_names, speaker_name_custom],
    )

    tts_button.click(
        fn=tts,
        inputs=[text, speaker_type, speaker_name_studio, speaker_name_custom, lang],
        outputs=[generated_audio],
    )

    stop_button.click(
        fn=stop_process,
        inputs=[],
        outputs=stop_message,
    )

if __name__ == "__main__":
    print("Warming up server...")
    with open("test/default_speaker.json", "r") as fp:
        warmup_speaker = json.load(fp)
    resp = requests.post(
        SERVER_URL + "/tts",
        json={
            "text": "This is a warmup request.",
            "language": "en",
            "speaker_embedding": warmup_speaker["speaker_embedding"],
            "gpt_cond_latent": warmup_speaker["gpt_cond_latent"],
        }
    )
    resp.raise_for_status()
    print("Starting the demo...")
    demo.launch(
        share=False,
        debug=False,
        server_port=3009,
        server_name="localhost",
    )
