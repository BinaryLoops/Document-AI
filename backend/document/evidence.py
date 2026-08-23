def find_evidence(value, chunks: list[str], chunk_metadata: list[dict], filename: str) -> dict:
    """
    Given an extracted field value, locate which source chunk it actually
    came from and build a standard evidence record — this is the shared
    wrapper every extraction and RAG answer routes through.
    """
    if not value:
        return {"source_document": filename, "page": None, "evidence_snippet": None}

    value_str = str(value).strip()
    for text, meta in zip(chunks, chunk_metadata):
        idx = text.find(value_str)
        if idx != -1:
            start, end = max(0, idx - 60), min(len(text), idx + len(value_str) + 60)
            return {
                "source_document": filename,
                "page": meta.get("page", "unknown"),
                "evidence_snippet": text[start:end].strip(),
            }

    # LLM sometimes reformats a value (e.g. date format) so it won't match
    # verbatim — still return a record rather than silently dropping the citation
    return {"source_document": filename, "page": "unknown", "evidence_snippet": None}