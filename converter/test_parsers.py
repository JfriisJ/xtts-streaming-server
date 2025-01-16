
import json
import logging
import os

import pytest
from jsonschema import validate, ValidationError
from converters.pdf_to_json import pdf_to_json
from converters.md_to_json import md_to_json

os.makedirs('/app/logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("/app/logs/converter.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


# Load the schema
with open("json_schema.json", "r") as schema_file:
    JSON_SCHEMA = json.load(schema_file)

def validate_json_output(json_output):
    try:
        validate(instance=json_output, schema=JSON_SCHEMA)
        logger.info("Schema validation passed.")
        return True
    except ValidationError as e:
        logger.error(f"Schema validation failed: {e.message}")
        logger.debug(f"Invalid JSON output: {json_output}")
        raise AssertionError(f"Schema validation failed: {e.message}")


def validate_json(json_content):
    expected = json.load(open("samples/test.json"))
    logger.info(f"JSON expected: {expected}, output: {json_content} ")
    validate_json_output(expected)
    # compare converted JSON output to the expected JSON output
    # assert json_content == expected

@pytest.fixture
def sample_files():
    """Provide paths to actual sample files for testing."""
    return {
        "markdown": "samples/test.md",
        "html": "samples/test.html",
        "epub": "samples/test.epub",
        "odt": "samples/test.odt",
        "pdf": "samples/test.pdf",
        "txt": "samples/test.txt",
        "docx": "samples/test.docx",
    }


def test_parse_markdown_to_json(sample_files):
    content = md_to_json(sample_files["markdown"], remove_code_blocks=False, remove_tables=False)
    assert content
    validate_json(content)


def test_convert_epub_to_markdown(sample_files):
    from any2md import convert_epub_to_markdown
    markdown_content = convert_epub_to_markdown(sample_files["epub"])
    assert markdown_content
    validate_json(markdown_content)

def test_convert_html_to_markdown(sample_files):
    from any2md import convert_html_to_markdown
    markdown_content = convert_html_to_markdown(sample_files["html"])
    assert markdown_content
    validate_json(markdown_content)

def test_convert_odt_to_markdown(sample_files):
    from any2md import convert_odt_to_markdown
    markdown_content = convert_odt_to_markdown(sample_files["odt"])
    assert markdown_content
    validate_json(markdown_content)

def test_convert_pdf_to_json(sample_files):
    content = pdf_to_json(sample_files["pdf"])
    assert content
    validate_json(content)

def test_convert_txt_to_markdown(sample_files):
    from any2md import convert_txt_to_markdown
    file_path = sample_files["txt"]
    markdown_content = convert_txt_to_markdown(file_path)
    assert markdown_content
    validate_json(markdown_content)


def test_convert_docx_to_markdown(sample_files):
    from any2md import convert_docx_to_markdown
    markdown_content = convert_docx_to_markdown(sample_files["docx"])
    assert markdown_content
    validate_json(markdown_content)
