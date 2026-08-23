"""
Evidence and confidence tracking module.
P4 requirement: Every extraction and RAG answer must carry source, page, evidence, confidence.
Shared response wrapper for all extractions and queries.
"""

import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class Evidence:
    """
    Standard evidence structure for all extractions and RAG responses.
    P4 requirement: source document, page, evidence snippet, confidence.
    """
    source_document: str
    page: int
    evidence_snippet: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class ExtractedField:
    """
    Extracted field with full evidence tracking.
    """
    field: str
    value: Any
    confidence: float
    evidence: Evidence
    field_type: Optional[str] = None
    required: Optional[bool] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "field": self.field,
            "value": self.value,
            "confidence": self.confidence,
            "evidence": self.evidence.to_dict()
        }
        if self.field_type:
            result["field_type"] = self.field_type
        if self.required is not None:
            result["required"] = self.required
        return result


@dataclass
class RAGResponse:
    """
    RAG system response with mandatory source citations.
    """
    query: str
    response: str
    evidence: List[Evidence]
    search_type: str
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "query": self.query,
            "response": self.response,
            "evidence": [e.to_dict() for e in self.evidence],
            "search_type": self.search_type,
            "confidence": self.confidence
        }


class EvidenceTracker:
    """
    Utility class for finding and attaching evidence to extractions.
    """
    
    @staticmethod
    def find_evidence(
        value: Any,
        chunks: List[str],
        chunk_metadata: List[Dict[str, Any]],
        filename: str,
        context_window: int = 100
    ) -> Evidence:
        """
        Find evidence snippet for an extracted value.
        
        Args:
            value: The extracted value to find
            chunks: List of text chunks
            chunk_metadata: Metadata for each chunk
            filename: Source document filename
            context_window: Characters to include around match
            
        Returns:
            Evidence object with source, page, snippet, confidence
        """
        if value is None or not str(value).strip():
            return Evidence(
                source_document=filename,
                page=0,
                evidence_snippet="Value not found in document",
                confidence=0.0
            )
        
        value_str = str(value).strip()
        
        # Search through chunks for the value
        for idx, chunk in enumerate(chunks):
            if value_str.lower() in chunk.lower():
                # Find the position in the chunk
                pos = chunk.lower().find(value_str.lower())
                
                # Extract context window
                start = max(0, pos - context_window)
                end = min(len(chunk), pos + len(value_str) + context_window)
                snippet = chunk[start:end].strip()
                
                # Add ellipsis if truncated
                if start > 0:
                    snippet = "..." + snippet
                if end < len(chunk):
                    snippet = snippet + "..."
                
                # Get metadata
                metadata = chunk_metadata[idx] if idx < len(chunk_metadata) else {}
                page = metadata.get("page", idx + 1)
                ocr_confidence = metadata.get("ocr_confidence")
                
                # Calculate confidence (use OCR confidence if available)
                confidence = ocr_confidence if ocr_confidence is not None else 0.85
                
                return Evidence(
                    source_document=filename,
                    page=page,
                    evidence_snippet=snippet,
                    confidence=confidence
                )
        
        # If exact match not found, return fuzzy evidence from first chunk
        if chunks:
            metadata = chunk_metadata[0] if chunk_metadata else {}
            snippet = chunks[0][:200] + "..." if len(chunks[0]) > 200 else chunks[0]
            
            return Evidence(
                source_document=filename,
                page=metadata.get("page", 1),
                evidence_snippet=f"[Approximate] {snippet}",
                confidence=0.5  # Lower confidence for fuzzy match
            )
        
        # No chunks available
        return Evidence(
            source_document=filename,
            page=0,
            evidence_snippet="No text available",
            confidence=0.0
        )
    
    @staticmethod
    def create_rag_evidence(
        retrieved_documents: List[Dict[str, Any]]
    ) -> List[Evidence]:
        """
        Create evidence list from retrieved documents for RAG responses.
        
        Args:
            retrieved_documents: List of retrieved document chunks with metadata
            
        Returns:
            List of Evidence objects
        """
        evidence_list = []
        
        for doc in retrieved_documents:
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            score = doc.get("score", 0.0)
            
            # Extract snippet (first 200 chars)
            snippet = text[:200] + "..." if len(text) > 200 else text
            
            evidence = Evidence(
                source_document=metadata.get("filename", metadata.get("source", "Unknown")),
                page=metadata.get("page", 0),
                evidence_snippet=snippet,
                confidence=float(score)
            )
            
            evidence_list.append(evidence)
        
        return evidence_list
    
    @staticmethod
    def aggregate_confidence(evidence_list: List[Evidence]) -> float:
        """
        Calculate aggregate confidence from multiple evidence items.
        
        Args:
            evidence_list: List of evidence items
            
        Returns:
            Aggregate confidence score (0.0 to 1.0)
        """
        if not evidence_list:
            return 0.0
        
        # Use weighted average with top evidences having more weight
        sorted_evidence = sorted(evidence_list, key=lambda e: e.confidence, reverse=True)
        
        total_weight = 0.0
        weighted_sum = 0.0
        
        for i, evidence in enumerate(sorted_evidence[:5]):  # Top 5 evidences
            weight = 1.0 / (i + 1)  # Decreasing weight
            weighted_sum += evidence.confidence * weight
            total_weight += weight
        
        return weighted_sum / total_weight if total_weight > 0 else 0.0


def create_extracted_field(
    field_name: str,
    value: Any,
    confidence: float,
    evidence: Evidence,
    field_type: Optional[str] = None,
    required: Optional[bool] = None
) -> ExtractedField:
    """
    Factory function to create an ExtractedField with evidence.
    
    Args:
        field_name: Name of the field
        value: Extracted value
        confidence: Confidence score
        evidence: Evidence object
        field_type: Type of the field (optional)
        required: Whether field is required (optional)
        
    Returns:
        ExtractedField object
    """
    return ExtractedField(
        field=field_name,
        value=value,
        confidence=confidence,
        evidence=evidence,
        field_type=field_type,
        required=required
    )


def create_rag_response(
    query: str,
    response: str,
    retrieved_documents: List[Dict[str, Any]],
    search_type: str = "hybrid"
) -> RAGResponse:
    """
    Factory function to create a RAG response with evidence.
    
    Args:
        query: User query
        response: Generated response
        retrieved_documents: Retrieved document chunks
        search_type: Type of search used
        
    Returns:
        RAGResponse object
    """
    tracker = EvidenceTracker()
    evidence_list = tracker.create_rag_evidence(retrieved_documents)
    confidence = tracker.aggregate_confidence(evidence_list)
    
    return RAGResponse(
        query=query,
        response=response,
        evidence=evidence_list,
        search_type=search_type,
        confidence=confidence
    )
