import base64
import logging
import os

import requests
from health_service import CONVERTER_API


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
    try:
        with open(file_path, "rb") as f:
            response = requests.post(CONVERTER_API + "/convert", files={"file": f}, timeout=10)

        if response.status_code != 200:
            logger.error(f"Failed to convert file. Status code: {response.status_code}, Response: {response.text}")
            raise Exception(f"Error converting file: {response.text}")

        result = response.json()

        if "json_output" not in result:
            logger.error(f"Unexpected response structure: {result}")
            raise Exception("Invalid response structure from converter service.")

        return result["json_output"]

    except requests.RequestException as e:
        logger.exception(f"Request to converter service failed: {e}")
        raise Exception("Request to converter service failed.")
    except ValueError:
        logger.exception("Invalid JSON response from converter service.")
        raise Exception("Error: Invalid JSON response from converter service.")



