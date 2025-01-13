import base64
import logging
import os

import requests
from health_service import TEXT_SERVICE_API, CONVERTER_API


# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def extract_text_from_file(file_path):
    if not file_path.endswith(".odt"):
        file_path = convert_file_to_odt(file_path)

    with open(file_path, "rb") as f:
        response = requests.post(TEXT_SERVICE_API + "/process", files={"file": f})
    if response.status_code != 200:
        raise Exception(f"Error extracting text: {response.text}")

    try:
        result = response.json()
    except ValueError:
        raise Exception("Error: Invalid JSON response from text service.")

    if "detail" in result and "Error extracting content" in result["detail"]:
        raise Exception(f"Text extraction error: {result['detail']}")

    return result


def convert_file_to_odt(file_path):
    # Convert the file to ODT using the converter service
    with open(file_path, "rb") as f:
        response = requests.post(CONVERTER_API + "/convert", files={"file": f})
    if response.status_code != 200:
        raise Exception(f"Error converting file: {response.text}")

    temp_file_path = "temp.odt"
    with open(temp_file_path, "wb") as f:
        f.write(response.content)

    # Validate the file
    if os.path.getsize(temp_file_path) == 0:
        raise Exception("Error: Converted ODT file is empty or invalid.")

    return temp_file_path

