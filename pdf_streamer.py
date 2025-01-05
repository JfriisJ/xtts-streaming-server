import gradio as gr
import requests
import base64
import tempfile
import json
import os


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

def read_pdf_with_plumber(file_path):
    """Read text from a PDF file and skip headers/footers based on position."""
    all_text = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            # Define the header/footer areas (adjust based on your PDF layout)
            text = page.filter(
                lambda obj: obj["top"] > 50 and obj["bottom"] < page.height - 50
            ).extract_text()
            all_text.append(text)
    return " ".join(all_text)


import re

def split_text_into_chunks(text, max_length=250):
    """
    Split text into chunks of up to max_length characters,
    ensuring the split happens at sentence boundaries if possible.
    """
    sentences = re.split(r'(?<=\.) ', text)  # Split by sentences
    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 1 <= max_length:  # +1 for the space
            current_chunk += sentence + " "
        else:
            if current_chunk:  # Save the current chunk
                chunks.append(current_chunk.strip())
            current_chunk = sentence + " "  # Start a new chunk

    if current_chunk:  # Add the last chunk
        chunks.append(current_chunk.strip())

    return chunks


def generate_audio_from_pdf(pdf_file, output_dir, speaker_type, speaker_name_studio, speaker_name_custom, lang):
    """Generate audio for each text chunk in a PDF."""
    pdf_path = pdf_file.name  # Access the actual file path
    text = read_pdf_with_plumber(pdf_path)
    chunks = split_text_into_chunks(text)
    embeddings = STUDIO_SPEAKERS[speaker_name_studio] if speaker_type == 'Studio' else cloned_speakers[speaker_name_custom]

    for i, chunk in enumerate(chunks):
        generated_audio = requests.post(
            SERVER_URL + "/tts",
            json={
                "text": chunk,
                "language": lang,
                "speaker_embedding": embeddings["speaker_embedding"],
                "gpt_cond_latent": embeddings["gpt_cond_latent"]
            }
        ).content
        audio_path = os.path.join(output_dir, f"audio_chunk_{i + 1}.wav")
        with open(audio_path, "wb") as audio_file:
            audio_file.write(base64.b64decode(generated_audio))
        print(f"Saved audio chunk {i + 1} to {audio_path}")


with gr.Blocks() as demo:
    cloned_speaker_names = gr.State(list(cloned_speakers.keys()))
    with gr.Tab("TTS"):
        with gr.Column() as row4:
            with gr.Row() as col4:
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
            speaker_type = gr.Dropdown(label="Speaker type", choices=["Studio", "Cloned"], value="Studio")
        with gr.Column() as col2:
            lang = gr.Dropdown(label="Language", choices=LANUGAGES, value="en")
            text = gr.Textbox(label="text", value="A quick brown fox jumps over the lazy dog.")
            tts_button = gr.Button(value="TTS")
        with gr.Column() as col3:
            generated_audio = gr.Audio(label="Generated audio", autoplay=True)
    with gr.Tab("Clone a new speaker"):
        with gr.Column() as col1:
            upload_file = gr.Audio(label="Upload reference audio", type="filepath")
            clone_speaker_name = gr.Textbox(label="Speaker name", value="default_speaker")
            clone_button = gr.Button(value="Clone speaker")
    with gr.Tab("Generate Audio from PDF"):
        with gr.Column():
            pdf_file = gr.File(label="Upload PDF", type="file")
            generate_pdf_button = gr.Button(value="Generate Audio")
            output_dir = gr.Textbox(label="Output Directory", value="./demo_outputs/generated_audios")

    generate_pdf_button.click(
        fn=generate_audio_from_pdf,
        inputs=[pdf_file, output_dir, speaker_type, speaker_name_studio, speaker_name_custom, lang],
        outputs=[]
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
        server_name="0.0.0.0",
    )
