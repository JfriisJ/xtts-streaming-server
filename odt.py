def extract_odt_structure(odt_file_path):
    from lxml import etree
    from zipfile import ZipFile

    def get_full_text(element):
        """Recursively extract text from an XML element and its children."""
        texts = []
        if element.text:
            texts.append(element.text.strip())
        for child in element:
            texts.append(get_full_text(child))
        if element.tail:
            texts.append(element.tail.strip())
        return " ".join(filter(None, texts))

    try:
        print(f"Opening ODT file: {odt_file_path}")

        # Open the ODT file as a ZIP archive
        with ZipFile(odt_file_path, 'r') as odt_zip:
            # Extract and parse meta.xml for title and author
            if 'meta.xml' in odt_zip.namelist():
                with odt_zip.open('meta.xml') as meta_file:
                    meta_content = meta_file.read()
                    meta_root = etree.fromstring(meta_content)
                    namespaces = {
                        'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
                        'dc': 'http://purl.org/dc/elements/1.1/'
                    }
                    # Extract title and author
                    title = meta_root.find('.//dc:title', namespaces)
                    author = meta_root.find('.//meta:initial-creator', namespaces)
                    title_text = title.text if title is not None else "Unknown Title"
                    author_text = author.text if author is not None else "Unknown Author"
                    print(f"Title: {title_text}")
                    print(f"Author: {author_text}")
            else:
                print("meta.xml not found in ODT file. Skipping metadata extraction.")
                title_text, author_text = "Unknown Title", "Unknown Author"

            # Extract and parse content.xml for headings
            if 'content.xml' in odt_zip.namelist():
                with odt_zip.open('content.xml') as content_file:
                    content = content_file.read()
                    content_root = etree.fromstring(content)
                    print("Parsed content.xml into an XML tree.")
                    namespaces = {'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0'}

                    # Find headings
                    headings = []
                    for heading in content_root.findall('.//text:h', namespaces):
                        level = heading.attrib.get(f'{{{namespaces["text"]}}}outline-level')
                        full_text = get_full_text(heading)  # Extract all nested text
                        if level:
                            level = int(level)
                        else:
                            print(f"Warning: Missing outline-level for heading: {full_text}")
                            level = 1  # Default to Level 1 if not specified
                        headings.append((level, full_text))
                        print(f"Found heading: {full_text}, Level: {level}")
            else:
                print("content.xml not found in ODT file. Skipping content extraction.")
                headings = []

        return {
            "title": title_text,
            "author": author_text,
            "headings": headings,
        }

    except Exception as e:
        print(f"Error during ODT extraction: {e}")
        raise ValueError(f"Error extracting content from ODT file: {e}")

# Usage
odt_file_path = "converter/outputs/Apples to Cider.odt"  # Replace with your file path
document_structure = extract_odt_structure(odt_file_path)

print("\nExtracted Structure:")
print(f"Title: {document_structure['title']}")
print(f"Author: {document_structure['author']}")
print("Headings:")
for level, text in document_structure['headings']:
    print(f"  Level {level}: {text}")
