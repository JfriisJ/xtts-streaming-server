```bash
docker build -t libreoffice-api .

```

```bash
docker run --rm -p 5000:5000 -v "$(pwd)/uploads:/app/uploads" -v "$(pwd)/outputs:/app/outputs" libreoffice-api

```

```bash

curl -X POST -F "file=@/path/to/your/file.pdf" -F "target_format=html" http://localhost:5000/convert

```

{
"message": "Conversion successful",
"filename": "file.html",
"content": "PGh0bWw+CiAgPGhlYWQ+CiAgICA8dGl0bGU+VGl0bGUgSGVyZTwvdGl0bGU+CiAgPC9oZWFkPgog..."
}

```bash
curl -X GET http://localhost:5000/formats

```

File Type Handling
File Type	Processing Logic
Markdown (.md)	- Directly parsed into JSON using the parse_markdown_to_json function.
- Does not require conversion to .odt.
EPUB (.epub)	- Converted to .odt using pandoc.
- The .odt file is then parsed into a JSON structure based on heading styles.
HTML (.html)	- Converted to .odt using pandoc.
- The .odt file is parsed for headings and categorized.
DOCX (.docx)	- Converted to .odt using LibreOffice in headless mode.
- Parsed to extract text and structured as JSON.
ODT (.odt)	- Parsed directly without additional conversion to extract headings and content.
Plain Text (.txt)	- Converted to .odt using LibreOffice (optional).
- Plain text usually lacks headings, so it may be grouped under a single category (e.g., Paragraphs or General Content).
PDF (.pdf)	- Requires external tools like pdf2txt or pdftohtml for conversion to .odt.
- After conversion, the resulting .odt file is processed as above.