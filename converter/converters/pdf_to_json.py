import pdfplumber
import re
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def format_content(content):
    """
    Format content by detecting lists, bold, italic, and code.

    Args:
        content (str): Raw content text.

    Returns:
        str: Formatted content.
    """
    # Format ordered lists
    content = re.sub(r"^(\d+)\.\s", r"\1. ", content, flags=re.MULTILINE)  # Ordered list
    # Format unordered lists
    content = re.sub(r"^[-]\s", "- ", content, flags=re.MULTILINE)  # Unordered list
    # Add line breaks after list items
    content = re.sub(r"(\d+\.\s.*?)(?=\n\S|$)", r"\1\n", content, flags=re.MULTILINE)
    content = re.sub(r"(-\s.*?)(?=\n\S|$)", r"\1\n", content, flags=re.MULTILINE)
    # Bold
    content = re.sub(r"\*\*(.*?)\*\*", r"**\1**", content)
    # Italic
    content = re.sub(r"\*(.*?)\*", r"*\1*", content)
    # Inline code
    content = re.sub(r"`(.*?)`", r"`\1`", content)
    # Ensure proper line breaks for Markdown formatting
    content = re.sub(r"(?<=\S)\n(?=\S)", "\n\n", content)  # Add breaks between lines
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
    excluded_content = []
    current_section = None
    current_subsection = None
    current_subsubsection = None
    current_subsubsubsection = None

    def append_to_parent():
        """Appends the current item to its appropriate parent."""
        nonlocal current_section, current_subsection, current_subsubsection, current_subsubsubsection
        if current_subsubsubsection and current_subsubsection:
            print(f"Adding subsubsubsection: {current_subsubsubsection}")
            current_subsubsection[2].append(current_subsubsubsection)
            current_subsubsubsection = None
        if current_subsubsection and current_subsection:
            print(f"Adding subsubsection: {current_subsubsection}")
            current_subsection[2].append(current_subsubsection)
            current_subsubsection = None
        if current_subsection and current_section:
            print(f"Adding subsection: {current_subsection}")
            current_section[2].append(current_subsection)
            current_subsection = None

    for line in lines:
        print(f"Processing line: {line}")  # Debugging output
        if re.match(r"^Section \d+", line):
            append_to_parent()
            if current_section:
                print(f"Adding section: {current_section}")
                sections.append(current_section)
            current_section = (line, "", [], [], [])
            print(f"Created new section: {current_section}")
        elif re.match(r"^Subsection \d+", line):
            append_to_parent()
            current_subsection = (line, "", [], [])
            print(f"Created new subsection: {current_subsection}")
        elif re.match(r"^Subsubsection \d+", line):
            append_to_parent()
            heading, _, content = line.partition(" This subsubsection has content represented as a list:")
            current_subsubsection = (
                heading.strip(),
                format_content(content.strip()),
                []
            )
            print(f"Created new subsubsection: {current_subsubsection}")
        elif re.match(r"^Subsubsubsection \d+", line):
            heading, _, content = line.partition(" ")
            current_subsubsubsection = (
                heading.strip(),
                format_content(content.strip()),
                []
            )
            print(f"Created new subsubsubsection: {current_subsubsubsection}")
        elif current_subsubsubsection:
            current_subsubsubsection = (
                current_subsubsubsection[0],
                current_subsubsubsection[1] + format_content(line) + "\n",
                current_subsubsubsection[2]
            )
            print(f"Updated subsubsubsection: {current_subsubsubsection}")
        elif current_subsubsection:
            current_subsubsection = (
                current_subsubsection[0],
                current_subsubsection[1] + format_content(line) + "\n",
                current_subsubsection[2]
            )
            print(f"Updated subsubsection: {current_subsubsection}")
        elif current_subsection:
            current_subsection = (
                current_subsection[0],
                current_subsection[1] + line + "\n",
                current_subsection[2],
                current_subsection[3]
            )
            print(f"Updated subsection: {current_subsection}")
        elif current_section:
            current_section = (
                current_section[0],
                current_section[1] + line + "\n",
                current_section[2],
                current_section[3],
                current_section[4]
            )
            print(f"Updated section: {current_section}")
        else:
            excluded_content.append(line)

    append_to_parent()  # Append any remaining items
    if current_section:
        print(f"Adding section: {current_section}")
        sections.append(current_section)

    if excluded_content:
        logging.info(f"Excluded content: {excluded_content}")

    return sections

def tuples_to_dicts(tuples):
    """
    Convert tuple-based hierarchical data to dictionary-based JSON structure.

    Args:
        tuples (tuple): Hierarchical data as tuples.

    Returns:
        dict: Dictionary representation of the data.
    """
    return {
        "Heading": tuples[0],
        "Content": tuples[1].strip(),
        "Subsections": [
            {
                "Heading": sub[0],
                "Content": sub[1].strip(),
                "Subsections": [
                    {
                        "Heading": subsub[0],
                        "Content": subsub[1].strip(),
                        "Subsections": [
                            {
                                "Heading": subsubsub[0],
                                "Content": subsubsub[1].strip(),
                                "Subsections": []
                            }
                            for subsubsub in subsub[2]
                        ]
                    }
                    for subsub in sub[2]
                ]
            }
            for sub in tuples[2]
        ]
    }

def pdf_to_json(file_path):
    """
    Convert a PDF file to a structured JSON format.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        dict: A JSON-compatible dictionary containing the extracted text.
    """
    try:
        logging.info(f"Converting PDF file: {file_path}")

        with pdfplumber.open(file_path) as pdf:
            title = ""
            all_sections = []

            for i, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    if i == 0:  # Assuming the title is on the first page
                        lines = text.splitlines()
                        if lines:
                            title = lines[0]  # Take the first line as the title
                    sections = parse_sections(text.splitlines())
                    all_sections.extend(sections)

        # Convert tuple-based structure to JSON-compatible dictionaries
        all_sections = [tuples_to_dicts(section) for section in all_sections]

        # Ensure Main Title has proper structure
        result = {
            "Title": title,
            "Sections": [{
                "Heading": title,
                "Content": "",
                "Subsections": all_sections
            }]
        }

        logging.info("PDF conversion successful.")

        # Print the JSON result
        print(json.dumps(result, indent=2))

        return result

    except Exception as e:
        logging.error(f"Error converting PDF to JSON: {e}")
        return None
