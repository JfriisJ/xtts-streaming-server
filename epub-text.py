import os
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup


# Function to extract and split the content
def split_epub_by_sections(epub_file):
    # Load the EPUB book
    book = epub.read_epub(epub_file)

    sections = []  # To store sections and their content

    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Parse the content using BeautifulSoup
            soup = BeautifulSoup(item.content, 'html.parser')

            # Identify headings and content
            for tag in soup.find_all(['h1', 'h2', 'h3']):
                heading = tag.get_text().strip()
                section_content = []

                # Extract content under the heading
                for sibling in tag.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3']:
                        break  # Stop if another heading is found
                    section_content.append(sibling.get_text().strip())

                sections.append({
                    'heading': heading,
                    'content': '\n'.join(section_content)
                })

    # Save each section as a separate text file
    output_dir = os.path.splitext(epub_file)[0] + '_sections'
    os.makedirs(output_dir, exist_ok=True)

    for i, section in enumerate(sections):
        filename = os.path.join(output_dir, f'section_{i + 1}.txt')
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"{section['heading']}\n\n")
            f.write(section['content'])

    print(f"Sections saved in directory: {output_dir}")


# Run the function on the uploaded EPUB file
split_epub_by_sections('Software Architecture in Practice.epub')
