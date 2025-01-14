import logging

import re

logging.basicConfig(level=logging.DEBUG)


def parse_markdown_to_json(markdown_content, remove_code_blocks=True, remove_tables=True):
    """
    Map Markdown headings and content into a JSON structure following the schema.
    Supports removing code blocks and tables if specified.
    Handles deep nesting like Subsubsubsections.
    """
    def clean_text(text):
        """Removes Markdown formatting."""
        return re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()

    def is_table_line(line):
        """Checks if a line is part of a Markdown table."""
        return "|" in line and not line.strip().startswith("```")

    # Initialize the JSON structure
    json_output = {"Title": "", "Sections": []}
    section_stack = []  # Stack to maintain the current section hierarchy
    in_code_block = False  # Track code block status

    lines = markdown_content.splitlines()
    for line in lines:
        stripped_line = line.strip()

        # Skip empty lines
        if not stripped_line:
            continue

        # Handle code blocks
        if stripped_line.startswith("```"):
            in_code_block = not in_code_block  # Toggle code block mode
            if remove_code_blocks:
                continue  # Skip code block lines entirely
        if in_code_block and remove_code_blocks:
            continue  # Skip all lines within code blocks

        # Handle tables
        if remove_tables and is_table_line(stripped_line):
            continue  # Skip table lines

        # Detect headings
        heading_match = re.match(r"^(#+)\s+(.*)", stripped_line)
        if heading_match:
            level = len(heading_match.group(1))  # Number of '#' determines the level
            heading = clean_text(heading_match.group(2))

            # Create a new section object
            new_section = {"Heading": heading, "Content": "", "Subsections": []}

            # Determine where to insert the new section
            while section_stack and section_stack[-1]['level'] >= level:
                section_stack.pop()  # Pop sections at the same or higher level

            if not section_stack:
                # Top-level section
                json_output["Sections"].append(new_section)
            else:
                # Add as a subsection
                section_stack[-1]["section"]["Subsections"].append(new_section)

            # Push the new section onto the stack
            section_stack.append({"level": level, "section": new_section})
        else:
            # Add content to the most recent section
            if section_stack:
                current_section = section_stack[-1]["section"]
                if current_section["Content"]:
                    current_section["Content"] += "\n" + stripped_line
                else:
                    current_section["Content"] = stripped_line

    # Set the title as the first heading if no explicit title exists
    if json_output["Sections"]:
        json_output["Title"] = json_output["Sections"][0]["Heading"]

    return json_output
