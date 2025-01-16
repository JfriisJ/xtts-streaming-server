import logging
from converters.pdf_to_json import pdf_to_json
from converters.md_to_json import md_to_json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def convert_file(content, ext):
    try:
        if ext == ".pdf":
            return pdf_to_json(content)
        # elif ext == ".epub":
        #     return epub_to_json.convert(file_path)
        # elif ext in [".html", ".htm"]:
        #     return html_to_json.convert(file_path)
        # elif ext == ".csv":
        #     return csv_to_json.convert(file_path)
        # elif ext == ".txt":
        #     return txt_to_json.convert(file_path)
        # elif ext == ".docx":
        #     return docx_to_json.convert(file_path)
        # elif ext == ".odt":
        #     return odt_to_json.convert(file_path)
        elif ext == ".md":
            return md_to_json(content, remove_code_blocks=True, remove_tables=True)
        else:
            raise ValueError(f"Unsupported file type: {ext}")
    except Exception as e:
        logging.error(f"Failed to convert file to JSON: {e}")
        return None
