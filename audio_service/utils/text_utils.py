import json

from transformers import GPT2TokenizerFast

from audio_service.utils.logging_utils import setup_logger



# Logging setup
logger = setup_logger(name="TextUtils")

def aggregate_section_with_subsections(section, depth=1):
    """
    Aggregate content of a section and its subsections, allowing up to 5 levels.
    """
    if depth > 5:
        return ""  # Ignore deeper levels

    heading_marker = "#" * depth  # Use up to 5 # for heading markers
    heading = section.get("Heading", "").strip()
    content = section.get("Content", "")

    if isinstance(content, list):
        content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
    elif isinstance(content, str):
        content = content.strip()
    else:
        content = ""

    aggregated_content = f"{heading_marker} {heading}\n\n{content}"

    for subsection in section.get("Subsections", []):
        aggregated_content += "\n\n" + aggregate_section_with_subsections(subsection, depth + 1)

    return aggregated_content


def split_text_into_tuples(sections):
    """
    Splits the text into tuples of (index, section_name, content),
    ensuring a maximum depth of 5 levels in the hierarchy.
    """
    tuples = []
    section_counts = {}

    def process_section(section, level=1, index_prefix="1"):
        """
        Recursively process sections and limit hierarchy to 5 levels.
        """
        if level > 5:  # Ignore levels deeper than 5
            return

        if index_prefix not in section_counts:
            section_counts[index_prefix] = 0
        section_counts[index_prefix] += 1

        index_parts = index_prefix.split(".")
        if len(index_parts) < level:
            index_parts.append("0")
        index_parts[level - 1] = str(section_counts[index_prefix])
        while len(index_parts) < 5:
            index_parts.append("0")

        current_index = ".".join(index_parts[:5])
        heading = section.get("Heading", "").strip()
        content = section.get("Content", "")

        if isinstance(content, list):
            content = "\n".join([str(item).strip() for item in content if isinstance(item, str)])
        elif isinstance(content, str):
            content = content.strip()
        else:
            content = ""

        combined_content = f"{heading}\n\n{content}"
        tuples.append((current_index, heading, combined_content))

        for subsection in section.get("Subsections", []):
            process_section(subsection, level + 1, current_index)

    for section in sections:
        process_section(section)

    return tuples

def get_aggregated_content(selected_title, sections, include_subsections=True):
    """
    Aggregates content for the selected section and all its nested subsections.
    Includes headings and content in a hierarchical structure.
    """
    logger.debug(f"Aggregating content for title: {selected_title}")
    logger.debug(f"Sections provided: {json.dumps(sections, indent=2)}")  # Log sections for debugging

    aggregated_content = []

    def collect_content(section, include, depth=0):
        indent = "  " * depth
        heading = section.get("Heading", "").strip()
        content = section.get("Content", "")

        # Match the selected title to start including content
        if heading.lower() == selected_title.lower():
            include = True
            logger.debug(f"{indent}Matched section: '{heading}'")

        if include:
            # Add the heading
            if heading:
                aggregated_content.append(f"{indent}{heading}")
                logger.debug(f"{indent}Added heading: {heading}")

            # Add the content (handle both string and list types)
            if isinstance(content, str) and content.strip():
                aggregated_content.append(f"{indent}  {content.strip()}")
                logger.debug(f"{indent}Added content: {content[:100]}...")
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, str):
                        aggregated_content.append(f"{indent}  {item.strip()}")
                        logger.debug(f"{indent}Added content item: {item.strip()}")

        # Process subsections recursively
        if include_subsections and "Subsections" in section:
            for subsection in section.get("Subsections", []):
                collect_content(subsection, include, depth + 1)

    # Iterate over top-level sections
    for section in sections:
        collect_content(section, include=False)

    result = "\n\n".join(filter(None, aggregated_content))
    logger.info(f"Aggregated content: {result[:500]}...")  # Log the first 500 characters
    return result




