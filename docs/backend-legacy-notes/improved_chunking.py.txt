import re
from typing import List

def chunk_by_paragraphs(text: str, max_chunks: int = 10) -> List[str]:
    """
    Split text into chunks by paragraphs, ensuring reasonable chunk sizes.
    
    Args:
        text: The text to chunk
        max_chunks: Maximum number of chunks to create
        
    Returns:
        List of text chunks
    """
    # Clean the text
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Split by double newlines or other paragraph markers
    paragraphs = re.split(r'\n\s*\n|\.\s+(?=[A-Z])', text)
    paragraphs = [p.strip() for p in paragraphs if p.strip()]
    
    if not paragraphs:
        return []
        
    # If very few paragraphs, return them directly
    if len(paragraphs) <= max_chunks:
        return paragraphs
        
    # Otherwise, combine paragraphs to reduce number of chunks
    result = []
    current_chunk = []
    
    for para in paragraphs:
        current_chunk.append(para)
        
        # If we've collected enough paragraphs or this is the last one
        if len(current_chunk) >= len(paragraphs) / max_chunks:
            result.append(" ".join(current_chunk))
            current_chunk = []
    
    # Add any remaining paragraphs
    if current_chunk:
        result.append(" ".join(current_chunk))
    
    return result