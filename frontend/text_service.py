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
    """
    Forward JSON data from the converter service.
    """
    with open(file_path, "rb") as f:
        response = requests.post(CONVERTER_API + "/convert", files={"file": f})
    if response.status_code != 200:
        raise Exception(f"Error converting file: {response.text}")

    try:
        result = response.json()
    except ValueError:
        raise Exception("Error: Invalid JSON response from converter service.")

    if "detail" in result and "Error" in result["detail"]:
        raise Exception(f"Conversion error: {result['detail']}")

    return result

