
from spellchecker import SpellChecker
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def spell_check_and_replace(text):
    spell = SpellChecker()
    words = text.split()
    corrected_text = []
    for word in words:
        logger.info(f"Checking word: '{word}'")
        if spell.unknown([word]):
            suggestion = spell.correction(word)
            logger.info(f"Suggestion: '{suggestion}'")
            if suggestion and suggestion != word:
                logger.info(f"Word changed: '{word}' -> '{suggestion}'")
            corrected_text.append(suggestion if suggestion else word)
        else:
            corrected_text.append(word)
    return " ".join(corrected_text)

def process_json_content(data):
    logger.info("Processing JSON content for spell checking.")
    for record in data:
        if "text" in record:
            logger.info(f"Processing text: {record['text']}")
            corrected_text = spell_check_and_replace(record["text"])
            record["text"] = corrected_text
    return data
