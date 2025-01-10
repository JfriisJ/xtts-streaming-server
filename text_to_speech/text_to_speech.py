import requests
from flask import Flask, request, jsonify, send_file, Response
import os
import tempfile
import logging
import base64

# Ensure the logs directory exists
os.makedirs('/app/logs', exist_ok=True)

# Initialize Flask app
app = Flask(__name__)

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/app/logs/text_to_speech.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# API Endpoints from main.py
BASE_URL = "http://localhost:8002"
CLONE_SPEAKER_API = f"{BASE_URL}/clone_speaker"
TTS_API = f"{BASE_URL}/tts"
TTS_STREAM_API = f"{BASE_URL}/tts_stream"
STUDIO_SPEAKERS_API = f"{BASE_URL}/studio_speakers"
LANGUAGES_API = f"{BASE_URL}/languages"

@app.route('/clone_speaker', methods=['POST'])
def clone_speaker():
    """Clones a speaker using the /clone_speaker endpoint in main.py."""
    file = request.files.get('wav_file')
    if not file:
        return jsonify({"error": "No audio file provided"}), 400

    try:
        files = {"wav_file": file.stream}
        response = requests.post(CLONE_SPEAKER_API, files=files)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error cloning speaker: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/tts', methods=['POST'])
def tts():
    """Performs TTS using the /tts endpoint in main.py."""
    data = request.json
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    try:
        response = requests.post(TTS_API, json=data)
        response.raise_for_status()
        audio_data = response.json().get("audio")
        if not audio_data:
            return jsonify({"error": "No audio data returned"}), 500

        # Save and return audio file
        temp_audio_path = tempfile.NamedTemporaryFile(delete=False, suffix=".wav").name
        with open(temp_audio_path, "wb") as f:
            f.write(base64.b64decode(audio_data))

        return send_file(temp_audio_path, mimetype="audio/wav", as_attachment=True)
    except requests.exceptions.RequestException as e:
        logger.error(f"Error generating TTS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/tts_stream', methods=['POST'])
def tts_stream():
    """Streams TTS audio using the /tts_stream endpoint in main.py."""
    data = request.json
    if not data:
        return jsonify({"error": "Invalid input"}), 400

    try:
        def stream_audio():
            response = requests.post(TTS_STREAM_API, json=data, stream=True)
            response.raise_for_status()
            for chunk in response.iter_content(chunk_size=4096):
                yield chunk

        return Response(stream_audio(), content_type="audio/wav")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error streaming TTS: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/studio_speakers', methods=['GET'])
def studio_speakers():
    """Fetches studio speakers using the /studio_speakers endpoint in main.py."""
    try:
        response = requests.get(STUDIO_SPEAKERS_API)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching studio speakers: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/languages', methods=['GET'])
def languages():
    """Fetches supported languages using the /languages endpoint in main.py."""
    try:
        response = requests.get(LANGUAGES_API)
        response.raise_for_status()
        return response.json(), 200
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching languages: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=8003)
