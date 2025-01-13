from fastapi import HTTPException
import os

import logging
import zipfile
from xml.etree.ElementTree import parse


# Setup logging
os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/converter.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def parse_odt_to_json(odt_file_path):
    """Extracts and organizes text from an ODT file into JSON."""
    try:
        with zipfile.ZipFile(odt_file_path, 'r') as odt_zip:
            with odt_zip.open('content.xml') as content_file:
                tree = parse(content_file)
                root = tree.getroot()

        namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}
        styled_content = {
            "Title": [],
            "Heading 1": [],
            "Heading 2": [],
            "Heading 3": [],
            "Heading 4": [],
            "Heading 5": [],
            "Paragraphs": []
        }

        for paragraph in root.findall('.//text:p', namespaces):
            style_name = paragraph.attrib.get(f'{{{namespaces["text"]}}}style-name', "Default")
            text_content = paragraph.text or ""
            text_content = text_content.strip()

            if not text_content:
                continue

            if style_name.startswith("Title"):
                styled_content["Title"].append(text_content)
            elif style_name.startswith("Heading_20_1"):
                styled_content["Heading 1"].append(text_content)
            elif style_name.startswith("Heading_20_2"):
                styled_content["Heading 2"].append(text_content)
            elif style_name.startswith("Heading_20_3"):
                styled_content["Heading 3"].append(text_content)
            elif style_name.startswith("Heading_20_4"):
                styled_content["Heading 4"].append(text_content)
            elif style_name.startswith("Heading_20_5"):
                styled_content["Heading 5"].append(text_content)
            else:
                styled_content["Paragraphs"].append(text_content)

        return {k: v for k, v in styled_content.items() if v}
    except Exception as e:
        logger.error(f"Error extracting text from ODT file: {e}")
        raise HTTPException(status_code=500, detail="Error extracting text from ODT file.")