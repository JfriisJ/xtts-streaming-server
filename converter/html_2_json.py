import logging
import os
import zipfile
from xml.etree.ElementTree import parse
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.DEBUG)

def parse_html_to_json(html_content):
    """
    Parse HTML content into a JSON structure.
    """
    def clean_text(text):
        return text.strip() if text else ""

    def parse_section(tag, level):
        section = {"Heading": clean_text(tag.get_text()), "Content": "", "Subsections": []}
        next_sibling = tag.find_next_sibling()

        while next_sibling:
            if next_sibling.name and next_sibling.name.startswith(f"h{level}"):
                break
            elif next_sibling.name and next_sibling.name.startswith(f"h{level+1}"):
                section["Subsections"].append(parse_section(next_sibling, level + 1))
            elif next_sibling.name == "p":
                paragraph_text = clean_text(next_sibling.get_text())
                if paragraph_text:
                    section["Content"] += f"\n{paragraph_text}" if section["Content"] else paragraph_text
            next_sibling = next_sibling.find_next_sibling()

        return section

    # Ensure HTML content is read properly
    if isinstance(html_content, str) and os.path.isfile(html_content):
        with open(html_content, "r", encoding="utf-8") as file:
            html_content = file.read()

    soup = BeautifulSoup(html_content, 'html.parser')
    title = clean_text(soup.title.string) if soup.title else "Untitled"
    sections = [parse_section(heading, 1) for heading in soup.find_all('h1')]

    return {"Title": title, "Sections": sections}

def parse_epub_to_json(file_path):
    """
    Parse EPUB content into a JSON structure by extracting and converting HTML content.
    """
    try:
        with zipfile.ZipFile(file_path, 'r') as epub_zip:
            if 'META-INF/container.xml' not in epub_zip.namelist():
                raise RuntimeError("Missing container.xml in EPUB file.")

            container = epub_zip.read('META-INF/container.xml').decode('utf-8')
            tree = parse(container)
            root_file_path = tree.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile').attrib['full-path']

            if root_file_path not in epub_zip.namelist():
                raise RuntimeError(f"Root file not found: {root_file_path}")

            html_content = epub_zip.read(root_file_path).decode('utf-8')

        return parse_html_to_json(html_content)
    except Exception as e:
        logging.error(f"Failed to parse EPUB: {e}")
        raise RuntimeError("Error parsing EPUB.")
