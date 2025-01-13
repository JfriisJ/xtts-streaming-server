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
    Extract text from a file using the converter service.
    """
    try:
        # Open and send the file to the converter service
        with open(file_path, "rb") as f:
            response = requests.post(f"{CONVERTER_API}/convert", files={"file": f}, timeout=10)
            response.raise_for_status()

        # Parse the JSON response
        result = response.json()
        if "json_output" not in result:
            logger.error(f"Unexpected response structure: {result}")
            raise ValueError("Invalid response structure from converter service.")

        logger.info("Successfully extracted text.")
        return result["json_output"], os.path.basename(file_path)

    except requests.ConnectionError as e:
        logger.error("Failed to connect to the converter service.")
        raise Exception("Unable to connect to the converter service.") from e

    except requests.Timeout as e:
        logger.error("Request to the converter service timed out.")
        raise Exception("Converter service timed out.") from e

    except requests.RequestException as e:
        logger.exception("Request to converter service failed.")
        raise Exception("Request to converter service failed.") from e

    except ValueError as e:
        logger.exception("Invalid JSON response from converter service.")
        raise Exception("Error parsing response from converter service.") from e

def format_section(section, depth=0):
    """
    Format a single section and its subsections recursively.
    """
    indent = "  " * depth  # Indentation for nested levels
    formatted_text = f"{indent}{section.get('Heading', 'Untitled Section')}\n"

    # Add the content of the section
    content = section.get("Content", "")
    if isinstance(content, list):
        formatted_text += "\n".join([f"{indent}- {item}" for item in content]) + "\n"
    elif content:
        formatted_text += f"{indent}{content}\n"

    # Recursively format subsections
    for subsection in section.get("Subsections", []):
        formatted_text += format_section(subsection, depth + 1)

    return formatted_text

def present_text_to_ui(result, file_name):
    """
    Format the JSON output for display in the UI, including nested sections and subsections.
    """
    try:
        title = result.get("Title", file_name)
        sections = result.get("Sections", [])

        if not sections:
            logger.warning("No sections found in the response.")
            return title, [], "No sections found."
        json_data = {"Title": title, "Sections": []}
        if not isinstance(json_data["Sections"], list):
            json_data["Sections"] = [json_data["Sections"]]

        # Format all sections
        formatted_sections = "\n".join([format_section(section) for section in sections])

        # Extract top-level section titles for dropdown
        section_titles = [section.get("Heading", "Untitled Section") for section in sections]


        logger.info("Formatted response for UI display.")
        return title, section_titles, formatted_sections

    except Exception as e:
        logger.exception("Error formatting response for UI.")
        raise Exception("Failed to format response for UI.") from e
