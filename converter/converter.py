import subprocess
import os
import logging
from flask import Flask, request, jsonify

# Initialize Flask app
app = Flask(__name__)

# Directories for uploads and outputs
UPLOAD_FOLDER = '/app/uploads'
OUTPUT_FOLDER = '/app/outputs'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Configure logging
LOG_FOLDER = '/app/logs'
os.makedirs(LOG_FOLDER, exist_ok=True)

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_FOLDER, 'converter.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@app.route('/convert', methods=['POST'])
def convert():
    logger.info("Received a file conversion request.")

    if 'file' not in request.files:
        logger.warning("No file uploaded in the request.")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        logger.warning("Empty filename received in the request.")
        return jsonify({"error": "Empty filename"}), 400

    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(file.filename)[0]}.odt")

    # Save the uploaded file
    file.save(input_path)
    logger.info(f"File saved at {input_path}")

    try:
        if file.filename.endswith('.epub'):
            logger.info("Detected EPUB file. Using Pandoc for conversion.")
            subprocess.run(
                ['pandoc', input_path, '-f', 'epub', '-t', 'odt', '-o', output_path],
                check=True
            )
        else:
            logger.info("Using LibreOffice for conversion.")
            subprocess.run(
                ['libreoffice', '--headless', '--convert-to', 'odt', '--outdir', OUTPUT_FOLDER, input_path],
                check=True
            )

        # Check if the output file exists
        if not os.path.exists(output_path):
            logger.error(f"Conversion failed: Output file {output_path} not created.")
            return jsonify({"error": "Output file not created", "details": output_path}), 500

        logger.info(f"Conversion successful: Output file created at {output_path}")
        return jsonify({
            "message": "Conversion successful",
            "output_path": output_path
        }), 200

    except subprocess.CalledProcessError as e:
        logger.error(f"Conversion failed: {e}")
        return jsonify({"error": "Conversion failed", "details": str(e)}), 500

    except Exception as e:
        logger.exception("Unexpected error occurred during conversion.")
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500

    finally:
        # Cleanup temporary files
        if os.path.exists(input_path):
            os.remove(input_path)
            logger.info(f"Temporary file {input_path} deleted.")

if __name__ == '__main__':
    logger.info("Starting the converter service on port 5000.")
    app.run(host='0.0.0.0', port=5000)
