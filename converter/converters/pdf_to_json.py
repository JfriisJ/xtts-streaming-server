import pdfplumber
import re
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def pdf_to_json(file_path):
    """
    Convert a PDF file to a structured JSON format.

    Args:
        file_path (str): The path to the PDF file.

    Returns:
        dict: A JSON-compatible dictionary containing the extracted text.
    """
    def parse_sections(text):
        """
        Parse text into sections and subsections based on headings.

        Args:
            text (str): The text to parse.

        Returns:
            list: A structured list of sections and their content.
        """
        lines = text.splitlines()
        sections = []
        current_section = None
        current_subsection = None
        current_subsubsection = None

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

        for line in lines:
            if re.match(r"^Section \d+", line):
                if current_section:
                    sections.append(current_section)
                current_section = {"Heading": line, "Content": "", "Subsections": []}
                current_subsection = None
                current_subsubsection = None
            elif re.match(r"^Subsection \d+", line):
                if current_subsection:
                    current_section["Subsections"].append(current_subsection)
                current_subsection = {"Heading": line, "Content": "", "Subsections": []}
                current_subsubsection = None
            elif re.match(r"^Subsubsection \d+", line):
                if current_subsubsection:
                    current_subsection["Subsections"].append(current_subsubsection)
                # Split the heading and content for Subsubsection
                heading, _, content = line.partition(" This subsubsection has content represented as a list:")
                current_subsubsection = {
                    "Heading": heading.strip(),
                    "Content": format_content(content.strip()),
                    "Subsections": []
                }
            elif current_subsubsection:
                if "Subsubsubsection" in line:
                    # Extract nested subsubsubsection
                    parts = line.split(" ", 1)
                    if len(parts) > 1:
                        subsubsubsection = {
                            "Heading": parts[0] + " " + parts[1].split(" ", 1)[0],
                            "Content": format_content(parts[1].split(" ", 1)[1]),
                            "Subsections": []
                        }
                        current_subsubsection["Subsections"].append(subsubsubsection)
                else:
                    current_subsubsection["Content"] += format_content(line) + "\n"
            elif current_subsection:
                current_subsection["Content"] += line + "\n"
            elif current_section:
                current_section["Content"] += line + "\n"

        # Finalize any remaining sections/subsections
        if current_subsubsection and current_subsection:
            current_subsection["Subsections"].append(current_subsubsection)
        if current_subsection and current_section:
            current_section["Subsections"].append(current_subsection)
        if current_section:
            sections.append(current_section)

        # Format content for all sections and subsections
        for section in sections:
            section["Content"] = format_content(section["Content"])
            for subsection in section.get("Subsections", []):
                subsection["Content"] = format_content(subsection["Content"])
                for subsubsection in subsection.get("Subsections", []):
                    subsubsection["Content"] = format_content(subsubsection["Content"])
                    for subsubsubsection in subsubsection.get("Subsections", []):
                        subsubsubsection["Content"] = format_content(subsubsubsection["Content"])

        return sections

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
                    sections = parse_sections(text)
                    all_sections.extend(sections)

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
