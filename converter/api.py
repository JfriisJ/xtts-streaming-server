import subprocess
import os
from flask import Flask, request, jsonify

app = Flask(__name__)
UPLOAD_FOLDER = '/app/uploads'
OUTPUT_FOLDER = '/app/outputs'

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400

    input_path = os.path.join(UPLOAD_FOLDER, file.filename)
    output_path = os.path.join(OUTPUT_FOLDER, f"{os.path.splitext(file.filename)[0]}.odt")

    # Save the uploaded file
    file.save(input_path)

    try:
        if file.filename.endswith('.epub'):
            # Use Pandoc for EPUB files
            subprocess.run(
                ['pandoc', input_path, '-f', 'epub', '-t', 'odt', '-o', output_path],
                check=True
            )
        else:
            # Use LibreOffice for other formats
            subprocess.run(
                ['libreoffice', '--headless', '--convert-to', 'odt', '--outdir', OUTPUT_FOLDER, input_path],
                check=True
            )

        # Check if the output file exists
        if not os.path.exists(output_path):
            return jsonify({"error": "Output file not created", "details": output_path}), 500

        return jsonify({
            "message": "Conversion successful",
            "output_path": output_path
        }), 200

    except subprocess.CalledProcessError as e:
        return jsonify({"error": "Conversion failed", "details": str(e)}), 500

    except Exception as e:
        return jsonify({"error": "Unexpected error", "details": str(e)}), 500

    finally:
        # Cleanup temporary files
        if os.path.exists(input_path):
            os.remove(input_path)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
