import logging
import os
import requests
from health_service import CONVERTER_API
import json
from matplotlib.font_manager import json_dump

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
        logger.info(json.dumps(result, indent=4))
        return result, os.path.basename(file_path)

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

def format_section(section, depth=0, max_depth=1000, visited=None):
    """
    Format a single section and its subsections recursively with proper handling of strings.
    """
    if depth > max_depth:
        logger.error(f"Exceeded maximum depth of {max_depth} at section: {section.get('Heading', 'Untitled Section')}")
        return f"{'  ' * depth}Recursion limit reached for this section.\n"

    if visited is None:
        visited = set()

    section_id = id(section)
    if section_id in visited:
        logger.error(f"Circular reference detected in section: {section.get('Heading', 'Untitled Section')}")
        return f"{'  ' * depth}Circular reference detected.\n"
    visited.add(section_id)

    indent = "  " * depth
    formatted_text = f"{indent}{section.get('Heading', 'Untitled Section')}\n"

    content = section.get("Content", "")
    if isinstance(content, str):
        # Avoid splitting text into individual characters
        formatted_text += f"{indent}{content.strip()}\n"
    elif isinstance(content, list):
        # Properly handle lists as concatenated strings
        formatted_text += f"{indent}" + " ".join(content).strip() + "\n"

    for subsection in section.get("Subsections", []):
        formatted_text += format_section(subsection, depth + 1, max_depth, visited)

    visited.remove(section_id)
    return formatted_text



def present_text_to_ui(result, file_name):
    """
    Format the JSON output for display in the UI, including nested sections and subsections.
    Adds the book title as a section.
    """
    try:
        title = result.get("Title", file_name)
        sections = result.get("Sections", [])

        if not sections:
            logger.warning("No sections found in the response.")
            return title, [], "No sections found."

        # Add the book title as a synthetic section
        synthetic_section = {
            "Heading": title,
            "Content": "",
            "Subsections": sections[:]  # Shallow copy to prevent circular references
        }
        sections.insert(0, synthetic_section)

        # Format all sections for display
        formatted_sections = "\n".join([format_section(section) for section in sections])

        # Extract top-level section titles for the dropdown
        section_titles = [section.get("Heading", "Untitled Section") for section in sections]

        logger.info("Formatted response for UI display.")
        return title, section_titles, formatted_sections

    except Exception as e:
        logger.exception("Error formatting response for UI.")
        raise Exception("Failed to format response for UI.") from e


def aggregate_section_content(selected_title, sections, include_subsections=True):
    """
    Aggregate content for the selected title and its subsections, including headings.
    """
    logger.debug(f"Aggregating content for title: {selected_title}")

    aggregated_content = []

    def collect_content(section, include=False, depth=0):
        if not isinstance(section, dict):
            logger.warning(f"Invalid section format at depth {depth}: {section}")
            return

        if section.get("Heading") == selected_title or include:
            include = True
            heading = section.get("Heading", "Untitled Section")
            logger.debug(f"Matched section: '{heading}' at depth {depth}")

            # Add the heading with proper formatting
            aggregated_content.append(f"{'  ' * depth}{heading}")

        content = section.get("Content", "")
        if include and isinstance(content, str):
            # Add content with proper formatting
            aggregated_content.append(f"{'  ' * (depth + 1)}{content.strip()}")
        elif include and isinstance(content, list):
            # Handle list content
            aggregated_content.extend(f"{'  ' * (depth + 1)}{item.strip()}" for item in content if isinstance(item, str))

        # Process subsections
        if include_subsections and include:
            for subsection in section.get("Subsections", []):
                collect_content(subsection, include, depth + 1)

    # Process each section
    for section in sections:
        collect_content(section)

    result = "\n\n".join(filter(None, aggregated_content))
    logger.debug(f"Final aggregated content: {result[:500]}...")  # Log only the first 500 characters
    return result



