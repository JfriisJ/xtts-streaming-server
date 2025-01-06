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




def split_text_into_chunks(text, max_chars=250, max_tokens=350):
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


def combine_audio_files(output_dir, combined_filename="combined_audio.wav"):
    """Combine all audio files in a directory into a single file."""
    from pydub import AudioSegment

    audio_files = [
        os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith('.wav')
    ]
    if not audio_files:
        return "No audio files found to combine."

    combined = AudioSegment.empty()
    for file in sorted(audio_files):
        try:
            audio = AudioSegment.from_file(file)
            combined += audio
        except Exception as e:
            print(f"Error processing {file}: {e}")

    combined_file_path = os.path.join(output_dir, combined_filename)
    combined.export(combined_file_path, format="wav")
    return f"Combined audio saved at {combined_file_path}"


def generate_audio_from_pdf(pdf_file, output_dir, speaker_type, speaker_name_studio, speaker_name_custom, lang,
                            page_range, header_height, footer_height, audio_file_name):
    """Generate audio for each text chunk in specified pages of a PDF."""
    stop_event.clear()

    pdf_path = pdf_file.name
    pdf_title = os.path.splitext(os.path.basename(pdf_path))[0]

    # Use the provided name or default to the PDF name
    base_audio_name = audio_file_name.strip() if audio_file_name.strip() else pdf_title

    pages = parse_page_range(page_range)

    text = read_pdf_with_plumber(pdf_path, pages=pages, header_height=header_height, footer_height=footer_height)
    chunks = split_text_into_chunks(text)
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[
        speaker_name_custom]

    for i, chunk in enumerate(chunks):
        if stop_event.is_set():
            break

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
            continue

        try:
            generated_audio = response.content
            decoded_audio = base64.b64decode(generated_audio)
        except base64.binascii.Error as e:
            print(f"Error decoding audio chunk {i + 1}: {e}")
            continue

        audio_filename = f"{base_audio_name}_{i + 1}.wav"
        audio_path = os.path.join(output_dir, audio_filename)
        with open(audio_path, "wb") as audio_file:
            audio_file.write(decoded_audio)

    combined_filename = f"{base_audio_name}_combined.wav"
    combine_audio_files(output_dir, combined_filename)


def stop_process():
    """Set the stop flag to interrupt the current process."""
    stop_event.set()
    return "Process stopped."

def preview_pdf_with_area(pdf_file, header_height, footer_height, page_number):
    """Visualize the content area of the selected page of the PDF."""
    import pdfplumber

    # Load the selected page of the PDF for preview
    with pdfplumber.open(pdf_file.name) as pdf:
        if page_number < 1 or page_number > len(pdf.pages):
            return "Invalid page number selected."
        page = pdf.pages[int(page_number) - 1]  # Convert 1-based page_number to 0-based index
        img = page.to_image()

        # Draw header and footer areas
        header_fill = (255, 0, 0, 77)  # Red with 30% opacity
        footer_fill = (0, 0, 255, 77)  # Blue with 30% opacity
        img.draw_rects([{"x0": 0, "top": 0, "x1": page.width, "bottom": header_height}], stroke="red", fill=header_fill)
        img.draw_rects([{"x0": 0, "top": page.height - footer_height, "x1": page.width, "bottom": page.height}], stroke="blue", fill=footer_fill)

        # Save the image to a temporary file and return its path
        temp_image_path = tempfile.NamedTemporaryFile(suffix=".png", delete=False).name
        img.save(temp_image_path)
        return temp_image_path

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
    process_status = gr.Label(value="Idle", label="Process Status")

    # TTS Tab
    with gr.Tab("TTS"):
        with gr.Column() as col1:
            speaker_name_studio
            speaker_name_custom
            speaker_type = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
            text = gr.Textbox(label="text", value="A quick brown fox jumps over the lazy dog.")
            tts_button = gr.Button(value="TTS")
            generated_audio = gr.Audio(label="Generated audio", autoplay=True)

    # Clone Speaker Tab
    with gr.Tab("Clone a new speaker"):
        with gr.Column() as col2:
            upload_file = gr.Audio(label="Upload reference audio", type="filepath")
            clone_speaker_name = gr.Textbox(label="Speaker name", value="default_speaker")
            clone_button = gr.Button(value="Clone speaker")

    # Generate Audio Tab
    with gr.Tab("Generate Audio from PDF"):

        with gr.Row() as row1:
            with gr.Column() as col3:
            # Shared components
                pdf_file = gr.File(label="Upload PDF", type="filepath")  # Shared PDF upload
                audio_file_name = gr.Textbox(label="Audio File Name (Leave blank to use PDF name)", value="", placeholder="Enter a custom name for the audio file")

            with gr.Column() as col4:
                preview_button = gr.Button(value="Refresh Preview")
                generate_audio_button = gr.Button(value="Generate Audio")
                combine_audio_button = gr.Button(value="Combine Audio Files")
                stop_button = gr.Button(value="Stop")

        with gr.Row() as row2:
            preview_image = gr.Image(label="Content Area Preview")
            with gr.Column() as col5:
                header_slider = gr.Slider(label="Header Height", minimum=0, maximum=1000, value=50, step=1)
                footer_slider = gr.Slider(label="Footer Height", minimum=0, maximum=1000, value=50, step=1)
                page_range = gr.Textbox(label="Page Range (e.g., 1-3,5)", value="1", placeholder="Enter pages to process")
                page_selector = gr.Number(label="Page Number", value=1, precision=0)  # Page selector for preview
                output_dir = gr.Textbox(label="Output Directory", value="./demo_outputs/generated_audios")


    combine_audio_button.click(  # Action for combining audio
        fn=combine_audio_files,
        inputs=[output_dir, gr.Textbox(value="combined_audio.wav", visible=False)],  # Output filename
        outputs=[process_status],
    )

    # Preview Button Action
    preview_button.click(
        fn=preview_pdf_with_area,
        inputs=[pdf_file, header_slider, footer_slider, page_selector],
        outputs=preview_image
    )

    # Generate Audio Button Action
    generate_audio_button.click(
        fn=generate_audio_from_pdf,
        inputs=[pdf_file, output_dir, speaker_type, speaker_name_studio, cloned_speaker_names, lang, page_range,
                header_slider, footer_slider, audio_file_name],
        outputs=[process_status],
    )

    header_slider.change(
        fn=preview_pdf_with_area,
        inputs=[pdf_file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )
    footer_slider.change(
        fn=preview_pdf_with_area,
        inputs=[pdf_file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )
    page_selector.change(
        fn=preview_pdf_with_area,
        inputs=[pdf_file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )

    # Preview Button Action
    page_selector.change(
        fn=preview_pdf_with_area,
        inputs=[pdf_file, header_slider, footer_slider, page_selector],
        outputs=preview_image,
    )

    clone_button.click(
        fn=clone_speaker,
        inputs=[upload_file, clone_speaker_name, cloned_speaker_names],
        outputs=[upload_file, clone_speaker_name, cloned_speaker_names, speaker_name_custom, process_status],
    )

    tts_button.click(
        fn=tts,
        inputs=[text, speaker_type, speaker_name_studio, speaker_name_custom, lang],
        outputs=[generated_audio, process_status],
    )



    stop_button.click(
        fn=stop_process,
        inputs=[],
        outputs=[process_status],
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
