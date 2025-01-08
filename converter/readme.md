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

{
  "pdf": ["html", "txt", "docx"],
  "docx": ["pdf", "html", "txt"],
  "epub": ["html", "txt"],
  "odt": ["pdf", "html", "txt"]
}
