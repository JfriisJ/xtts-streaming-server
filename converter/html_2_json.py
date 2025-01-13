from bs4 import BeautifulSoup

def parse_html_to_json(html_content):
    """
    Parse HTML content into structured JSON with headings, content, and subsections.
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    # Utility function to clean and normalize text
    def clean_text(text):
        return text.strip() if text else ""

    # Recursive function to parse a heading and its subsections
    def parse_section(tag, level):
        section = {
            "Heading": clean_text(tag.get_text()),
            "Content": "",
            "Subsections": []
        }
        next_sibling = tag.find_next_sibling()
        while next_sibling:
            if next_sibling.name and next_sibling.name.startswith(f"h{level}"):
                break  # Stop if the next sibling is a heading of the same or higher level
            elif next_sibling.name and next_sibling.name.startswith(f"h{level+1}"):
                # Add a subsection if the sibling is a lower-level heading
                section["Subsections"].append(parse_section(next_sibling, level + 1))
            elif next_sibling.name == "ul" or next_sibling.name == "ol":
                # Parse lists as structured content
                list_items = [
                    clean_text(li.get_text()) for li in next_sibling.find_all("li")
                ]
                section["Content"] = list_items if isinstance(section["Content"], list) else list_items
            elif next_sibling.name == "p":
                # Add paragraph content
                paragraph_text = clean_text(next_sibling.get_text())
                if paragraph_text:
                    if isinstance(section["Content"], list):
                        section["Content"].append(paragraph_text)
                    else:
                        section["Content"] += f"\n{paragraph_text}"
            next_sibling = next_sibling.find_next_sibling()

        return section

    # Identify main title
    title = clean_text(soup.title.string) if soup.title else "Untitled"

    # Parse all sections starting from <h1>
    sections = []
    for heading in soup.find_all('h1'):
        sections.append(parse_section(heading, 1))

    return {
        "Title": title,
        "Sections": sections
    }
