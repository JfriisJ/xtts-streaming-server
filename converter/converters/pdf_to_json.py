import pdfplumber
import re
import logging
import fitz  # PyMuPDF
from matplotlib.font_manager import json_dump

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def extract_headers_with_pymupdf(file_path):
    """
    Extract headers using PyMuPDF based on font size.

    Args:
        file_path (str): Path to the PDF file.

    Returns:
        list: A list of detected headers.
    """
    doc = fitz.open(file_path)
    headers = []
    for page in doc:
        blocks = page.get_text("dict")["blocks"]
        for block in blocks:
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["size"] > 12:  # Assume headers have larger font sizes
                        headers.append(span["text"].strip())
    return headers

def format_content(content):
    """
    Format content by detecting lists, bold, italic, and code, and ensuring proper line breaks.

    Args:
        content (str): Raw content text.

    Returns:
        str: Formatted content.
    """
    # Format list items
    content = re.sub(r"(?<!\S)-(\s*)", r"- ", content)  # Fix bullet lists
    content = re.sub(r"(\d+)\.\s*", r"\1. ", content)  # Fix ordered lists

    # Format inline styles
    content = re.sub(r"\*\*(.*?)\*\*", r"**\1**", content)  # Bold
    content = re.sub(r"(?<!\*)\*(.*?)\*(?!\*)", r"*\1*", content)  # Italic
    content = re.sub(r"`(.*?)`", r"`\1`", content)  # Inline code

    # Ensure proper line breaks
    content = re.sub(r"\s*-\s*", r"\n- ", content)  # Add newlines before bullet lists
    content = re.sub(r"(\d+\.\s+.*?)(?=\d+\.\s|$)", r"\1\n", content, flags=re.DOTALL)  # Newline for ordered lists

    return content.strip()

def parse_sections(lines):
    """
    Parse text into sections and subsections based on headings.

    Args:
        lines (list): List of lines from the text.

    Returns:
        list: A structured list of sections and their content.
    """
    sections = []
    current_section = None
    current_subsection = None
    current_subsubsection = None
    current_subsubsubsection = None

    def append_to_parent():
        nonlocal current_section, current_subsection, current_subsubsection, current_subsubsubsection
        if current_subsubsubsection:
            current_subsubsection["Subsections"].append(current_subsubsubsection)
            current_subsubsubsection = None
        if current_subsubsection:
            current_subsection["Subsections"].append(current_subsubsection)
            current_subsubsection = None
        if current_subsection:
            current_section["Subsections"].append(current_subsection)
            current_subsection = None

    for line in lines:
        if re.match(r"^Section \d+", line):
            append_to_parent()
            if current_section:
                sections.append(current_section)
            current_section = {"Heading": line.strip(), "Content": "", "Subsections": []}
        elif re.match(r"^Subsection \d+", line):
            append_to_parent()
            current_subsection = {"Heading": line.strip(), "Content": "", "Subsections": []}
        elif re.match(r"^Subsubsection \d+", line):
            # Split heading and content if applicable
            match = re.match(r"^(Subsubsection \d+\.\d+\.\d+)\s*(.*)$", line)
            if match:
                heading = match.group(1).strip()
                content = match.group(2).strip()
                current_subsubsection = {"Heading": heading, "Content": format_content(content), "Subsections": []}
            else:
                logging.warning(f"Could not parse Subsubsection line: {line}")
        elif re.match(r"^Subsubsubsection \d+", line):
            # Split heading and content for subsubsubsection
            match = re.match(r"^(Subsubsubsection \d+\.\d+\.\d+\.\d+)\s*(.*)$", line)
            if match:
                heading = match.group(1).strip()
                content = match.group(2).strip()
                current_subsubsubsection = {"Heading": heading, "Content": format_content(content), "Subsections": []}
            else:
                logging.warning(f"Could not parse Subsubsubsection line: {line}")
        elif current_subsubsubsection:
            current_subsubsubsection["Content"] += format_content(line) + "\n"
        elif current_subsubsection:
            current_subsubsection["Content"] += format_content(line) + "\n"
        elif current_subsection:
            current_subsection["Content"] += format_content(line) + "\n"
        elif current_section:
            current_section["Content"] += format_content(line) + "\n"

    append_to_parent()
    if current_section:
        sections.append(current_section)

    return sections

def pdf_to_json(content):
    """
    Convert a PDF file to a structured JSON format.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        dict: A JSON-compatible dictionary containing the extracted text.
    """
    try:
        # Extract headers with PyMuPDF
        headers = extract_headers_with_pymupdf(content)
        logging.info(f"Extracted headers: {headers}")

        with pdfplumber.open(content) as pdf:
            title = "Main Title"  # Default title if not explicitly provided
            all_sections = []

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    lines = text.splitlines()
                    if i == 0 and lines:
                        title = lines[0].strip()  # First line as title
                    sections = parse_sections(lines)
                    all_sections.extend(sections)

        # Ensure main structure matches the JSON schema
        result = {
            "Title": title,
            "Sections": [{
                "Heading": title,
                "Content": "",
                "Subsections": all_sections
            }]
        }

        return result

    except Exception as e:
        logging.error(f"Error converting PDF to JSON: {e}", exc_info=True)
        return None