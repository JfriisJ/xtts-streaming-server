import re

from audio_service.utils.logging_utils import setup_logger

logger = setup_logger(name="FileUtils")

def clean_filename(filename: str) -> str:
    """
    Renser et filnavn ved at fjerne eller erstatte ugyldige tegn.

    :param filename: Det originale filnavn.
    :return: Et renset filnavn.
    """
    return re.sub(r'[<>:"/\\|?*]', '_', filename).strip()


import os


def ensure_directory_exists(directory: str) -> None:
    """
    Opretter en mappe, hvis den ikke allerede findes.

    :param directory: Stien til mappen.
    """
    if not os.path.exists(directory):
        os.makedirs(directory)


def save_binary_file(data: bytes, file_path: str) -> None:
    """
    Gemmer binære data til en fil.

    :param data: Binære data.
    :param file_path: Filens placering.
    """
    with open(file_path, 'wb') as file:
        file.write(data)


def read_binary_file(file_path: str) -> bytes:
    """
    Læser indholdet af en binær fil.

    :param file_path: Filens placering.
    :return: Filens binære indhold.
    """
    with open(file_path, 'rb') as file:
        return file.read()


import base64


def encode_to_base64(file_path: str) -> str:
    """
    Encoder en fil til Base64-format.

    :param file_path: Stien til filen.
    :return: Base64-encodet streng.
    """
    with open(file_path, 'rb') as file:
        return base64.b64encode(file.read()).decode('utf-8')


def decode_from_base64(base64_string: str, output_path: str) -> None:
    """
    Decoder Base64-streng og gemmer som en fil.

    :param base64_string: Base64-encodet streng.
    :param output_path: Placeringen hvor filen skal gemmes.
    """
    data = base64.b64decode(base64_string)
    with open(output_path, 'wb') as file:
        file.write(data)


def is_valid_filename(filename: str) -> bool:
    """
    Validerer et filnavn baseret på almindelige restriktioner.

    :param filename: Filnavnet, der skal valideres.
    :return: `True`, hvis filnavnet er gyldigt; ellers `False`.
    """
    invalid_characters = r'[<>:"/\\|?*\x00-\x1F]'
    return not bool(re.search(invalid_characters, filename))
