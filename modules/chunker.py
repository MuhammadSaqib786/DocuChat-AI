import re

def simple_chunk_text(text, max_words=200):
    """
    Splits text into chunks of up to max_words words.
    Returns a list of strings (chunks).
    """
    # Remove excessive whitespace and newlines
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = ' '.join(words[i:i+max_words])
        chunks.append(chunk)
    return chunks
