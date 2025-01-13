def parse_markdown_to_json(markdown_content, remove_code_blocks=True, remove_tables=True):
    """
    Parse Markdown content into structured JSON with hierarchical levels.
    - Removes Markdown formatting like `**`.
    - Optionally removes code blocks and tables.
    """
    def clean_text(text):
        """Removes Markdown formatting (e.g., `**`) from the text."""
        return re.sub(r"\*\*(.*?)\*\*", r"\1", text).strip()

    def is_table_line(line):
        """
        Checks if a line is part of a Markdown table.
        A table line contains `|` and may also have `---` to define headers.
        """
        return "|" in line and not line.strip().startswith("```")

    lines = markdown_content.strip().split("\n")
    if not lines:
        return {"Title": "", "Sections": []}

    title = clean_text(lines[0].strip("# ").strip())
    json_data = {"Title": title, "Sections": []}
    current_section = None
    current_subsection = None
    in_code_block = False
    in_table = False
    code_block_lines = []

    for line in lines[1:]:
        stripped_line = line.strip()

        # Handle code blocks
        if stripped_line.startswith("```"):  # Toggle code block mode
            in_code_block = not in_code_block
            if not in_code_block:  # Closing a code block
                if not remove_code_blocks:
                    code_content = "\n".join(code_block_lines).strip()
                    if current_subsection:
                        current_subsection["Content"] += f"\n\n{code_content}" if current_subsection["Content"] else code_content
                    elif current_section:
                        current_section["Content"] += f"\n\n{code_content}" if current_section["Content"] else code_content
                code_block_lines = []
            continue

        if in_code_block:
            if not remove_code_blocks:
                code_block_lines.append(line)
            continue

        # Handle tables
        if remove_tables:
            if is_table_line(stripped_line):
                in_table = True
                continue
            elif in_table and not stripped_line:  # End of table
                in_table = False
                continue

        # Skip empty lines and horizontal rules
        if not stripped_line or stripped_line == "---":
            continue

        # Handle `#` as top-level sections
        if stripped_line.startswith("# "):
            if current_section:
                if current_subsection:
                    current_section["Subsections"].append(current_subsection)
                    current_subsection = None
                json_data["Sections"].append(current_section)
            current_section = {"Heading": clean_text(stripped_line[2:].strip()), "Content": "", "Subsections": []}

        # Handle `##` as mid-level sections
        elif stripped_line.startswith("## "):
            if current_subsection:
                current_section["Subsections"].append(current_subsection)
            current_subsection = {"Heading": clean_text(stripped_line[3:].strip()), "Content": "", "Subsections": []}

        # Handle `###` as lowest-level sections
        elif stripped_line.startswith("### "):
            if current_subsection:
                current_subsection["Subsections"].append({
                    "Heading": clean_text(stripped_line[4:].strip()),
                    "Content": []
                })

        # Add content to the current section or subsection
        else:
            cleaned_line = clean_text(stripped_line)
            if current_subsection and current_subsection["Subsections"]:
                current_subsection["Subsections"][-1]["Content"].append(cleaned_line)
            elif current_subsection:
                current_subsection["Content"] += f"\n{cleaned_line}" if current_subsection["Content"] else cleaned_line
            elif current_section:
                current_section["Content"] += f"\n{cleaned_line}" if current_section["Content"] else cleaned_line

    # Append the last subsection and section
    if current_subsection:
        current_section["Subsections"].append(current_subsection)
    if current_section:
        json_data["Sections"].append(current_section)

    return json_data
