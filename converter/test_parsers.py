import os
import json
import pytest
from jsonschema import validate, ValidationError
from md_2_json import parse_markdown_to_json
from html_2_json import parse_html_to_json, parse_epub_to_json
from converter import convert_odt_to_html, convert_pdf_to_html

# Load the schema
with open("json_schema.json", "r") as schema_file:
    JSON_SCHEMA = json.load(schema_file)

# Helper function to validate JSON
def validate_json_output(json_output):
    try:
        validate(instance=json_output, schema=JSON_SCHEMA)
        return True
    except ValidationError as e:
        pytest.fail(f"Schema validation failed: {e}")

@pytest.fixture
def sample_files():
    """Provide paths to sample files."""
    return {
        "markdown": "samples/sample.md",
        "html": "samples/sample.html",
        "epub": "samples/sample.epub",
        "odt": "samples/sample.odt",
        "pdf": "samples/sample.pdf",
    }

# Markdown Parser Test
def test_parse_markdown_to_json(sample_files):
    with open(sample_files["markdown"], "r", encoding="utf-8") as md_file:
        markdown_content = md_file.read()
    json_output = parse_markdown_to_json(markdown_content)
    assert validate_json_output(json_output)
    assert "Title" in json_output
    assert "Sections" in json_output

# HTML Parser Test
def test_parse_html_to_json(sample_files):
    with open(sample_files["html"], "r", encoding="utf-8") as html_file:
        html_content = html_file.read()
    json_output = parse_html_to_json(html_content)
    assert validate_json_output(json_output)
    assert "Title" in json_output
    assert "Sections" in json_output

# EPUB Parser Test
def test_parse_epub_to_json(sample_files):
    json_output = parse_epub_to_json(sample_files["epub"])
    assert validate_json_output(json_output)
    assert "Title" in json_output
    assert "Sections" in json_output

# ODT Parser Test
def test_convert_odt_to_html(sample_files):
    html_path = convert_odt_to_html(sample_files["odt"], "/tmp")
    with open(html_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()
    json_output = parse_html_to_json(html_content)
    assert validate_json_output(json_output)

# PDF Parser Test
def test_convert_pdf_to_html(sample_files):
    html_path = convert_pdf_to_html(sample_files["pdf"], "/tmp")
    with open(html_path, "r", encoding="utf-8") as html_file:
        html_content = html_file.read()
    json_output = parse_html_to_json(html_content)
    assert validate_json_output(json_output)

# Generate sample files for testing various formats

import os

# Define the sample contents for each format
samples = {
    "markdown": "# Title\n## Section 1\n### Subsection 1.1\n#### Subsubsection 1.1.1\n##### Subsubsubsection 1.1.1.1\nContent here.",
    "html": "<html><head><title>Title</title></head><body><h1>Title</h1><h2>Section 1</h2><h3>Subsection 1.1</h3><h4>Subsubsection 1.1.1</h4><h5>Subsubsubsection 1.1.1.1</h5><p>Content here.</p></body></html>",
    "epub": b'PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb3\xf8\x83\xf4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00	\x00META-INF/container.xml<?xml version="1.0"?>\n<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0"><rootfiles><rootfile full-path="content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb3\xf8\x83\xf4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00	\x00content.opf<?xml version="1.0"?>\n<package xmlns="http://www.idpf.org/2007/opf" version="2.0"><metadata><dc:title>Title</dc:title></metadata><manifest><item id="html" href="index.html" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="html"/></spine></package>PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb3\xf8\x83\xf4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00	\x00index.html<html><head><title>Title</title></head><body><h1>Title</h1><h2>Section 1</h2><h3>Subsection 1.1</h3><h4>Subsubsection 1.1.1</h4><h5>Subsubsubsection 1.1.1.1</h5><p>Content here.</p></body></html>PK\x01\x02\x14\x03\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb3\xf8\x83\xf4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x00\x00META-INF/container.xmlPK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00B\x00\x00\x00\xA2\x00\x00\x00\x00\x00',
    "odt": b'PK\x03\x04\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb3\xf8\x83\xf4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00	\x00content.xml<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"><office:body><office:text><text:h text:style-name="Heading_20_1" text:outline-level="1">Title</text:h><text:h text:style-name="Heading_20_2" text:outline-level="2">Section 1</text:h><text:h text:style-name="Heading_20_3" text:outline-level="3">Subsection 1.1</text:h><text:h text:style-name="Heading_20_4" text:outline-level="4">Subsubsection 1.1.1</text:h><text:h text:style-name="Heading_20_5" text:outline-level="5">Subsubsubsection 1.1.1.1</text:h><text:p>Content here.</text:p></office:text></office:body></office:document-content>PK\x01\x02\x14\x03\x14\x00\x06\x00\x08\x00\x00\x00!\x00\xb3\xf8\x83\xf4\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x13\x00\x00\x00content.xmlPK\x05\x06\x00\x00\x00\x00\x01\x00\x01\x00\x37\x00\x00\x00\x94\x00\x00\x00\x00\x00',
    "pdf": b'%PDF-1.4\n%...\n1 0 obj\n<< /Title (Title) >>\nendobj\n4 0 obj\n<< /Type /Page /Contents 5 0 R >>\nendobj\nxref\ntrailer\n<< /Root 1 0 R >>\nstartxref\n%%EOF'
}

# Create the directory structure and write files
os.makedirs("samples", exist_ok=True)

for format_name, content in samples.items():
    file_path = f"samples/sample.{format_name}"
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(file_path, mode) as f:
        f.write(content)

# Confirm file creation
os.listdir("samples")
