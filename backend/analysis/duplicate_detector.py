"""
Duplicate and Version Detection.
P14 requirement: Use embeddings to flag duplicates, field diff for version comparison.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class DuplicateDetector:
    """
    Detect duplicate documents and compare versions using embeddings and field diffs.
    """
    
    # Similarity thresholds
    THRESHOLD_EXACT_DUPLICATE = 0.98
    THRESHOLD_LIKELY_DUPLICATE = 0.90
    THRESHOLD_POSSIBLE_DUPLICATE = 0.75
    
    def __init__(self, embedding_model):
        """
        Initialize duplicate detector.
        
        Args:
            embedding_model: Embedding model instance
        """
        self.embedding_model = embedding_model
        logger.info("DuplicateDetector initialized")
    
    def detect_duplicates(
        self,
        documents: List[Dict[str, Any]],
        threshold: float = THRESHOLD_LIKELY_DUPLICATE
    ) -> List[Dict[str, Any]]:
        """
        Detect duplicate documents using embedding similarity.
        
        Args:
            documents: List of documents with text content
            threshold: Similarity threshold for duplicate detection
            
        Returns:
            List of duplicate pairs
        """
        if len(documents) < 2:
            return []
        
        # Generate document-level embeddings
        doc_embeddings = []
        for doc in documents:
            # Combine chunks for document-level embedding
            text = self._get_document_text(doc)
            if text:
                embedding = self.embedding_model.embed(text)
                doc_embeddings.append(embedding)
            else:
                doc_embeddings.append(None)
        
        # Find duplicate pairs
        duplicates = []
        
        for i in range(len(documents)):
            if doc_embeddings[i] is None:
                continue
                
            for j in range(i + 1, len(documents)):
                if doc_embeddings[j] is None:
                    continue
                
                # Calculate cosine similarity
                similarity = self._cosine_similarity(
                    doc_embeddings[i],
                    doc_embeddings[j]
                )
                
                if similarity >= threshold:
                    duplicate_type = self._classify_duplicate_type(similarity)
                    
                    duplicates.append({
                        'document_a': {
                            'document_id': documents[i].get('document_id'),
                            'filename': documents[i].get('filename')
                        },
                        'document_b': {
                            'document_id': documents[j].get('document_id'),
                            'filename': documents[j].get('filename')
                        },
                        'similarity_score': float(similarity),
                        'duplicate_type': duplicate_type,
                        'confidence': self._calculate_confidence(similarity),
                        'message': self._generate_duplicate_message(duplicate_type, similarity)
                    })
        
        logger.info(f"Detected {len(duplicates)} potential duplicates")
        return duplicates
    
    def compare_versions(
        self,
        document_a: Dict[str, Any],
        document_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Compare two versions of the same document to detect changes.
        
        Args:
            document_a: First document with extracted fields
            document_b: Second document with extracted fields
            
        Returns:
            Version comparison report
        """
        fields_a = {
            f.get('field'): f.get('value')
            for f in document_a.get('extracted_fields', [])
        }
        fields_b = {
            f.get('field'): f.get('value')
            for f in document_b.get('extracted_fields', [])
        }
        
        # Find changed fields
        changed_fields = []
        all_fields = set(fields_a.keys()) | set(fields_b.keys())
        
        for field in all_fields:
            value_a = fields_a.get(field)
            value_b = fields_b.get(field)
            
            if value_a != value_b:
                change_type = self._determine_change_type(value_a, value_b)
                
                changed_fields.append({
                    'field': field,
                    'previous_value': value_a,
                    'new_value': value_b,
                    'change_type': change_type,
                    'similarity': self._text_similarity(
                        str(value_a) if value_a else '',
                        str(value_b) if value_b else ''
                    )
                })
        
        # Calculate overall document similarity
        text_a = self._get_document_text(document_a)
        text_b = self._get_document_text(document_b)
        
        embedding_a = self.embedding_model.embed(text_a) if text_a else None
        embedding_b = self.embedding_model.embed(text_b) if text_b else None
        
        overall_similarity = (
            float(self._cosine_similarity(embedding_a, embedding_b))
            if embedding_a is not None and embedding_b is not None
            else 0.0
        )
        
        return {
            'document_a_id': document_a.get('document_id'),
            'document_b_id': document_b.get('document_id'),
            'overall_similarity': overall_similarity,
            'changed_fields': changed_fields,
            'total_changes': len(changed_fields),
            'change_summary': self._generate_change_summary(changed_fields)
        }
    
    def _get_document_text(self, document: Dict[str, Any]) -> str:
        """Extract full text from document."""
        chunks = document.get('chunks', [])
        if chunks:
            # Limit to first 5000 chars to avoid embedding limits
            return ' '.join(chunks)[:5000]
        
        # Fallback: combine extracted field values
        extracted_fields = document.get('extracted_fields', [])
        if extracted_fields:
            text_parts = [
                str(f.get('value', ''))
                for f in extracted_fields
                if f.get('value')
            ]
            return ' '.join(text_parts)[:5000]
        
        return ''
    
    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between vectors."""
        if vec1 is None or vec2 is None:
            return 0.0
        
        # Ensure 1D arrays
        if vec1.ndim > 1:
            vec1 = vec1.flatten()
        if vec2.ndim > 1:
            vec2 = vec2.flatten()
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm_a = np.linalg.norm(vec1)
        norm_b = np.linalg.norm(vec2)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    def _classify_duplicate_type(self, similarity: float) -> str:
        """Classify duplicate type based on similarity."""
        if similarity >= self.THRESHOLD_EXACT_DUPLICATE:
            return "EXACT_DUPLICATE"
        elif similarity >= self.THRESHOLD_LIKELY_DUPLICATE:
            return "LIKELY_DUPLICATE"
        else:
            return "POSSIBLE_DUPLICATE"
    
    @staticmethod
    def _calculate_confidence(similarity: float) -> str:
        """Calculate confidence level."""
        if similarity >= 0.98:
            return "VERY_HIGH"
        elif similarity >= 0.90:
            return "HIGH"
        elif similarity >= 0.80:
            return "MEDIUM"
        else:
            return "LOW"
    
    @staticmethod
    def _generate_duplicate_message(duplicate_type: str, similarity: float) -> str:
        """Generate human-readable duplicate message."""
        messages = {
            "EXACT_DUPLICATE": f"Exact duplicate detected (similarity: {similarity:.1%})",
            "LIKELY_DUPLICATE": f"Likely duplicate - documents are very similar (similarity: {similarity:.1%})",
            "POSSIBLE_DUPLICATE": f"Possible duplicate - significant similarity detected (similarity: {similarity:.1%})"
        }
        return messages.get(duplicate_type, f"Similar documents (similarity: {similarity:.1%})")
    
    @staticmethod
    def _determine_change_type(value_a: Any, value_b: Any) -> str:
        """Determine type of change between values."""
        if value_a is None and value_b is not None:
            return "ADDED"
        elif value_a is not None and value_b is None:
            return "REMOVED"
        else:
            return "MODIFIED"
    
    @staticmethod
    def _text_similarity(text_a: str, text_b: str) -> float:
        """Calculate text similarity using SequenceMatcher."""
        return SequenceMatcher(None, text_a, text_b).ratio()
    
    @staticmethod
    def _generate_change_summary(changed_fields: List[Dict[str, Any]]) -> str:
        """Generate summary of changes."""
        if not changed_fields:
            return "No changes detected"
        
        added = len([f for f in changed_fields if f['change_type'] == 'ADDED'])
        removed = len([f for f in changed_fields if f['change_type'] == 'REMOVED'])
        modified = len([f for f in changed_fields if f['change_type'] == 'MODIFIED'])
        
        parts = []
        if added:
            parts.append(f"{added} field(s) added")
        if removed:
            parts.append(f"{removed} field(s) removed")
        if modified:
            parts.append(f"{modified} field(s) modified")
        
        return ", ".join(parts)
    
    def batch_detect_duplicates(
        self,
        document_groups: List[List[Dict[str, Any]]]
    ) -> List[List[Dict[str, Any]]]:
        """
        Detect duplicates across multiple document groups.
        
        Args:
            document_groups: List of document groups (e.g., by case)
            
        Returns:
            List of duplicate reports per group
        """
        results = []
        
        for group in document_groups:
            duplicates = self.detect_duplicates(group)
            results.append(duplicates)
        
        return results
