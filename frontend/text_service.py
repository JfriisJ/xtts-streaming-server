import base64
import logging

import requests
from health_service import TEXT_SERVICE_API, CONVERTER_API


# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# extract text from file
def extract_text_from_file(file_path):
    # Check if the file is an ODT file and send it to the text service
    if not file_path.endswith(".odt"):
        convert_file_to_odt(file_path)
    else:
        return requests.post(TEXT_SERVICE_API + "/process", files={"file": open(file_path, "rb")}).json()



def convert_file_to_odt(file_path):
    # Convert the PDF to text using the converter service as a base64 string
    result_converted = requests.post(CONVERTER_API + "/convert", files={"file": open(file_path, "rb")}).json()
    # decode base64 and save as a odt file
    with open("temp.odt", "wb") as f:
        f.write(base64.b64decode(result_converted["file"]))
    extract_text_from_file("temp.odt")