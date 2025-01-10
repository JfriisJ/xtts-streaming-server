# Updated logging for text_extraction.py
import logging
from flask import Flask, request, jsonify
from zipfile import ZipFile
from lxml import etree
import os

# Ensure the logs directory exists
os.makedirs('/app/logs', exist_ok=True)

# Initialize logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("/app/logs/text_extraction.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Extract ODT Structure
def extract_odt_structure(odt_file_path):
    def get_full_text(element):
        """Recursively extract text from an XML element and its children."""
        texts = []
        if element.text:
            texts.append(element.text.strip())
        for child in element:
            texts.append(get_full_text(child))
        if element.tail:
            texts.append(element.tail.strip())
        return " ".join(filter(None, texts))

    outline_to_style = {
        1: "Title",
        2: "Heading 1",
        3: "Heading 2",
        4: "Heading 3",
        5: "Heading 4",
        6: "Heading 5",
    }

    try:
        logger.info(f"Extracting ODT structure from {odt_file_path}")
        with ZipFile(odt_file_path, 'r') as odt_zip:
            book_title = "Unknown Book"
            if 'meta.xml' in odt_zip.namelist():
                with odt_zip.open('meta.xml') as meta_file:
                    meta_content = meta_file.read()
                    meta_root = etree.fromstring(meta_content)
                    namespaces = {
                        'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
                        'dc': 'http://purl.org/dc/elements/1.1/'
                    }
                    title = meta_root.find('.//dc:title', namespaces)
                    book_title = title.text.strip() if title is not None else "Unknown Book"

            if 'content.xml' in odt_zip.namelist():
                with odt_zip.open('content.xml') as content_file:
                    content = content_file.read()
                    content_root = etree.fromstring(content)
                    namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}

                    headings = []
                    current_content = []
                    last_heading = None

                    for element in content_root.iter():
                        tag = element.tag.split('}')[-1]
                        if tag == "h":
                            if last_heading is not None:
                                last_heading["content"] = "\n".join(current_content).strip()
                                current_content = []

                            level = element.attrib.get(f'{{{namespaces["text"]}}}outline-level')
                            style = outline_to_style.get(int(level), f"Unknown Level ({level})") if level else "Unknown Style"

                            full_text = get_full_text(element)
                            last_heading = {"style": style, "title": full_text, "content": ""}
                            headings.append(last_heading)

                            if book_title == "Unknown Book" and style == "Title":
                                book_title = full_text

                        elif tag == "p":
                            if last_heading is not None:
                                paragraph_text = get_full_text(element).strip()
                                if paragraph_text:
                                    current_content.append(paragraph_text)

                    if last_heading is not None:
                        last_heading["content"] = "\n".join(current_content).strip()

            else:
                headings = []

        logger.info("Extraction successful.")
        return {"title": book_title, "sections": headings}

    except Exception as e:
        logger.error(f"Error extracting content from ODT file: {e}")
        raise ValueError(f"Error extracting content from ODT file: {e}")

@app.route('/process', methods=['POST'])
def process_file():
    if 'file' not in request.files:
        logger.warning("No file uploaded.")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    temp_file_path = os.path.join("/tmp", file.filename)
    file.save(temp_file_path)

    try:
        logger.debug(f"Processing file: {temp_file_path}")
        doc_structure = extract_odt_structure(temp_file_path)
        os.remove(temp_file_path)
        return jsonify(doc_structure), 200
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        os.remove(temp_file_path)
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info("Starting text extraction service on port 8001")
    app.run(host="0.0.0.0", port=8001)
