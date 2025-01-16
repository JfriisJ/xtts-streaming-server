import pdfplumber
import re
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def format_content(content):
    """
    Format content by detecting lists, bold, italic, and code, and ensuring proper line breaks.

    Args:
        content (str): Raw content text.

    Returns:
        str: Formatted content.
    """
    content = re.sub(r"\*\*(.*?)\*\*", r"**\1**", content)  # Bold
    content = re.sub(r"(?<!\*)\*(.*?)\*(?!\*)", r"*\1*", content)  # Italic
    content = re.sub(r"`(.*?)`", r"`\1`", content)  # Inline code
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
            match = re.match(r"^(Subsubsection \d+)(.*)$", line)
            heading = match.group(1).strip()
            content = match.group(2).strip()
            current_subsubsection = {"Heading": heading, "Content": format_content(content), "Subsections": []}
        elif re.match(r"^Subsubsubsection \d+", line):
            current_subsubsubsection = {"Heading": line.strip(), "Content": "", "Subsections": []}
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

def pdf_to_json(file_path):
    """
    Convert a PDF file to a structured JSON format.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        dict: A JSON-compatible dictionary containing the extracted text.
    """
    try:
        with pdfplumber.open(file_path) as pdf:
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

        if result:
            with open("output.json", "w") as f:
                json.dump(result, f, indent=2)
            print("Output saved to output.json")

        return result

    except Exception as e:
        print(f"Error converting PDF to JSON: {e}")
        logging.error(f"Error converting PDF to JSON: {e}")
        return None

if __name__ == "__main__":
    # Example usage
    file_path = "example.pdf"
    result = pdf_to_json(file_path)
    if result:
        with open("output.json", "w") as f:
            json.dump(result, f, indent=2)
        print("Output saved to output.json")
