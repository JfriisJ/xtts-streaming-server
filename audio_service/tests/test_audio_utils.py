import pytest
from ..utils.audio_utils import split_text_into_chunks

def test_split_text_into_chunks():
    text = "This is a test. Another test follows."
    result = split_text_into_chunks(text, max_chars=10, max_tokens=5)
    assert result == ["This is a", "test. Another", "test follows."]
