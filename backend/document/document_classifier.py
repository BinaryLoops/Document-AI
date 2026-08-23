"""
Document classification module.
P2 requirement: Classify documents into 8-10 types with confidence scoring.
Uses embedding-based similarity for explainable, fast classification.
"""

import logging
from typing import Tuple, List, Dict, Any
import numpy as np

from document.schemas.document_types import (
    get_all_document_types,
    get_document_type_descriptions
)

logger = logging.getLogger(__name__)


class DocumentClassifier:
    """
    Embedding-based document classifier.
    Fast, explainable, no fine-tuning needed - good for prototyping.
    """
    
    def __init__(self, embedding_model):
        """
        Initialize the document classifier.
        
        Args:
            embedding_model: Embedding model instance (from embedding.model)
        """
        self.embedding_model = embedding_model
        self.document_types = get_all_document_types()
        
        # Precompute embeddings for all document type descriptions
        logger.info("Precomputing document type embeddings...")
        self._precompute_type_embeddings()
        logger.info(f"Classifier ready with {len(self.type_embeddings)} document types")
    
    def _precompute_type_embeddings(self):
        """Precompute embeddings for all document type descriptions."""
        self.type_names = []
        self.type_descriptions = []
        
        for type_key, type_info in self.document_types.items():
            name = type_info["name"]
            description = type_info["description"]
            keywords = " ".join(type_info["keywords"])
            
            # Combine description and keywords for better matching
            full_description = f"{description}. Keywords: {keywords}"
            
            self.type_names.append(name)
            self.type_descriptions.append(full_description)
        
        # Generate embeddings for all types at once
        self.type_embeddings = self.embedding_model.embed(self.type_descriptions)
    
    def classify(self, text: str, top_k: int = 3) -> Tuple[str, float]:
        """
        Classify a document based on its text content.
        
        Args:
            text: Document text to classify
            top_k: Number of top candidates to consider
            
        Returns:
            Tuple of (document_type, confidence_score)
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for classification")
            return "Other", 0.0
        
        try:
            # Truncate very long texts to avoid embedding issues
            # Take first 2000 chars + last 500 chars for better representation
            if len(text) > 2500:
                text = text[:2000] + " " + text[-500:]
            
            # Generate embedding for the input text
            text_embedding = self.embedding_model.embed(text)
            
            # Calculate cosine similarity with all document types
            similarities = self._cosine_similarity(
                text_embedding, 
                self.type_embeddings
            )
            
            # Get the best match
            best_idx = np.argmax(similarities)
            best_type = self.type_names[best_idx]
            best_confidence = float(similarities[best_idx])
            
            # Apply confidence thresholding
            # If confidence is too low, classify as "Other"
            if best_confidence < 0.3:
                logger.info(f"Low confidence ({best_confidence:.3f}), classifying as 'Other'")
                return "Other", best_confidence
            
            logger.info(f"Classified as '{best_type}' with confidence {best_confidence:.3f}")
            
            return best_type, best_confidence
            
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return "Other", 0.0
    
    def classify_with_alternatives(
        self, 
        text: str, 
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Classify a document and return top-k candidates.
        
        Args:
            text: Document text to classify
            top_k: Number of top candidates to return
            
        Returns:
            List of dicts with {type, confidence, description}
        """
        if not text or not text.strip():
            return [{"type": "Other", "confidence": 0.0, "description": "Empty document"}]
        
        try:
            # Truncate long text
            if len(text) > 2500:
                text = text[:2000] + " " + text[-500:]
            
            # Generate embedding
            text_embedding = self.embedding_model.embed(text)
            
            # Calculate similarities
            similarities = self._cosine_similarity(
                text_embedding, 
                self.type_embeddings
            )
            
            # Get top-k indices
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            
            results = []
            for idx in top_indices:
                results.append({
                    "type": self.type_names[idx],
                    "confidence": float(similarities[idx]),
                    "description": self.document_types[
                        list(self.document_types.keys())[idx]
                    ]["description"]
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Classification error: {e}")
            return [{"type": "Other", "confidence": 0.0, "description": str(e)}]
    
    def classify_batch(
        self, 
        texts: List[str]
    ) -> List[Tuple[str, float]]:
        """
        Classify multiple documents in batch.
        
        Args:
            texts: List of document texts
            
        Returns:
            List of (document_type, confidence) tuples
        """
        if not texts:
            return []
        
        try:
            # Generate embeddings for all texts
            text_embeddings = self.embedding_model.embed(texts)
            
            # Calculate similarities for all texts at once
            # Shape: (num_texts, num_types)
            similarities = np.dot(text_embeddings, self.type_embeddings.T)
            
            # Get best match for each text
            best_indices = np.argmax(similarities, axis=1)
            best_confidences = np.max(similarities, axis=1)
            
            results = []
            for idx, conf in zip(best_indices, best_confidences):
                doc_type = self.type_names[idx]
                confidence = float(conf)
                
                # Apply threshold
                if confidence < 0.3:
                    doc_type = "Other"
                
                results.append((doc_type, confidence))
            
            return results
            
        except Exception as e:
            logger.error(f"Batch classification error: {e}")
            return [("Other", 0.0) for _ in texts]
    
    @staticmethod
    def _cosine_similarity(
        vec1: np.ndarray, 
        vec2: np.ndarray
    ) -> np.ndarray:
        """
        Calculate cosine similarity between vectors.
        
        Args:
            vec1: First vector or matrix (n_samples, n_features)
            vec2: Second vector or matrix (m_samples, n_features)
            
        Returns:
            Similarity scores
        """
        # Ensure 2D arrays
        if vec1.ndim == 1:
            vec1 = vec1.reshape(1, -1)
        if vec2.ndim == 1:
            vec2 = vec2.reshape(1, -1)
        
        # Calculate dot product
        similarity = np.dot(vec1, vec2.T)
        
        # Squeeze if single sample
        if similarity.shape[0] == 1:
            similarity = similarity.squeeze(0)
        
        return similarity
    
    def get_supported_types(self) -> List[str]:
        """Get list of all supported document types."""
        return self.type_names.copy()
    
    def get_type_description(self, doc_type: str) -> str:
        """Get description for a specific document type."""
        for type_info in self.document_types.values():
            if type_info["name"] == doc_type:
                return type_info["description"]
        return "Unknown document type"
