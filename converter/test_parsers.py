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

