"""
Hybrid search implementation combining semantic, keyword, and metadata filtering.
P5 requirement: FAISS semantic + BM25 keyword + metadata filters with score combination.
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)


class HybridSearch:
    """
    Hybrid search engine combining semantic and keyword search with metadata filtering.
    """
    
    def __init__(
        self,
        semantic_weight: float = 0.7,
        keyword_weight: float = 0.3
    ):
        """
        Initialize hybrid search.
        
        Args:
            semantic_weight: Weight for semantic search scores (0.0 to 1.0)
            keyword_weight: Weight for keyword search scores (0.0 to 1.0)
        """
        self.semantic_weight = semantic_weight
        self.keyword_weight = keyword_weight
        
        # BM25 index for keyword search
        self.bm25 = None
        self.corpus_texts = []
        self.corpus_metadata = []
        
        logger.info(
            f"HybridSearch initialized with weights: "
            f"semantic={semantic_weight}, keyword={keyword_weight}"
        )
    
    def index_documents(
        self, 
        texts: List[str], 
        metadata: List[Dict[str, Any]]
    ):
        """
        Index documents for keyword search.
        
        Args:
            texts: List of document texts
            metadata: List of metadata dictionaries
        """
        if not texts:
            logger.warning("No texts provided for indexing")
            return
        
        self.corpus_texts = texts
        self.corpus_metadata = metadata
        
        # Tokenize documents for BM25
        tokenized_corpus = [text.lower().split() for text in texts]
        self.bm25 = BM25Okapi(tokenized_corpus)
        
        logger.info(f"Indexed {len(texts)} documents for keyword search")
    
    def search(
        self,
        query: str,
        semantic_results: List[Dict[str, Any]],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search combining semantic and keyword results.
        
        Args:
            query: Search query
            semantic_results: Results from semantic search (FAISS)
            top_k: Number of top results to return
            filter_dict: Metadata filters (e.g., {"doc_type": "Application"})
            
        Returns:
            List of search results with combined scores
        """
        if not semantic_results:
            logger.warning("No semantic results provided")
            return []
        
        # Perform keyword search
        keyword_results = self._keyword_search(query, top_k * 2)
        
        # Combine scores
        combined_results = self._combine_results(
            semantic_results,
            keyword_results,
            self.semantic_weight,
            self.keyword_weight
        )
        
        # Apply metadata filters
        if filter_dict:
            combined_results = self._apply_filters(combined_results, filter_dict)
        
        # Sort by combined score and return top-k
        combined_results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        return combined_results[:top_k]
    
    def _keyword_search(
        self, 
        query: str, 
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Perform BM25 keyword search.
        
        Args:
            query: Search query
            top_k: Number of top results
            
        Returns:
            List of keyword search results
        """
        if self.bm25 is None or not self.corpus_texts:
            logger.warning("BM25 index not initialized")
            return []
        
        # Tokenize query
        tokenized_query = query.lower().split()
        
        # Get BM25 scores
        scores = self.bm25.get_scores(tokenized_query)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[-top_k:][::-1]
        
        results = []
        for idx in top_indices:
            if idx < len(self.corpus_texts):
                score = float(scores[idx])
                if score > 0:  # Only include non-zero scores
                    results.append({
                        "text": self.corpus_texts[idx],
                        "metadata": self.corpus_metadata[idx],
                        "score": score,
                        "index": int(idx)
                    })
        
        return results
    
    def _combine_results(
        self,
        semantic_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        semantic_weight: float,
        keyword_weight: float
    ) -> List[Dict[str, Any]]:
        """
        Combine semantic and keyword search results.
        
        Args:
            semantic_results: Results from semantic search
            keyword_results: Results from keyword search
            semantic_weight: Weight for semantic scores
            keyword_weight: Weight for keyword scores
            
        Returns:
            Combined results with normalized scores
        """
        # Normalize semantic scores
        semantic_scores_map = {}
        semantic_max = max(
            [r.get("score", 0) for r in semantic_results], 
            default=1.0
        )
        for result in semantic_results:
            text = result.get("text", "")
            score = result.get("score", 0) / semantic_max if semantic_max > 0 else 0
            semantic_scores_map[text] = score
        
        # Normalize keyword scores
        keyword_scores_map = {}
        keyword_max = max(
            [r.get("score", 0) for r in keyword_results], 
            default=1.0
        )
        for result in keyword_results:
            text = result.get("text", "")
            score = result.get("score", 0) / keyword_max if keyword_max > 0 else 0
            keyword_scores_map[text] = score
        
        # Combine scores
        combined = {}
        all_texts = set(semantic_scores_map.keys()) | set(keyword_scores_map.keys())
        
        for text in all_texts:
            semantic_score = semantic_scores_map.get(text, 0)
            keyword_score = keyword_scores_map.get(text, 0)
            
            combined_score = (
                semantic_weight * semantic_score + 
                keyword_weight * keyword_score
            )
            
            combined[text] = combined_score
        
        # Build result list
        results = []
        semantic_map = {r.get("text", ""): r for r in semantic_results}
        keyword_map = {r.get("text", ""): r for r in keyword_results}
        
        for text, score in combined.items():
            # Get metadata from either source
            result = semantic_map.get(text) or keyword_map.get(text, {})
            results.append({
                "text": text,
                "metadata": result.get("metadata", {}),
                "score": score,
                "semantic_score": semantic_scores_map.get(text, 0),
                "keyword_score": keyword_scores_map.get(text, 0)
            })
        
        return results
    
    @staticmethod
    def _apply_filters(
        results: List[Dict[str, Any]], 
        filter_dict: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply metadata filters to search results.
        
        Args:
            results: Search results
            filter_dict: Filters to apply (e.g., {"doc_type": "Application", "status": "COMPLETED"})
            
        Returns:
            Filtered results
        """
        filtered = []
        
        for result in results:
            metadata = result.get("metadata", {})
            matches = True
            
            for key, value in filter_dict.items():
                # Handle different filter types
                if key == "date_range" and isinstance(value, dict):
                    # Date range filter
                    doc_date = metadata.get("date")
                    if doc_date:
                        start = value.get("start")
                        end = value.get("end")
                        if start and doc_date < start:
                            matches = False
                            break
                        if end and doc_date > end:
                            matches = False
                            break
                elif key == "document_types" and isinstance(value, list):
                    # Multiple document types filter
                    if metadata.get("document_type") not in value:
                        matches = False
                        break
                else:
                    # Exact match filter
                    if metadata.get(key) != value:
                        matches = False
                        break
            
            if matches:
                filtered.append(result)
        
        return filtered
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get search index statistics."""
        return {
            "indexed_documents": len(self.corpus_texts),
            "semantic_weight": self.semantic_weight,
            "keyword_weight": self.keyword_weight,
            "bm25_initialized": self.bm25 is not None
        }


class MetadataFilter:
    """
    Helper class for building metadata filters.
    """
    
    @staticmethod
    def by_document_type(doc_types: List[str]) -> Dict[str, Any]:
        """Filter by document type(s)."""
        if len(doc_types) == 1:
            return {"document_type": doc_types[0]}
        return {"document_types": doc_types}
    
    @staticmethod
    def by_date_range(start_date: str, end_date: str) -> Dict[str, Any]:
        """Filter by date range."""
        return {
            "date_range": {
                "start": start_date,
                "end": end_date
            }
        }
    
    @staticmethod
    def by_case(case_id: str) -> Dict[str, Any]:
        """Filter by case ID."""
        return {"case_id": case_id}
    
    @staticmethod
    def by_person(person_name: str) -> Dict[str, Any]:
        """Filter by person name."""
        return {"person_name": person_name}
    
    @staticmethod
    def by_organization(org_name: str) -> Dict[str, Any]:
        """Filter by organization name."""
        return {"organization": org_name}
    
    @staticmethod
    def by_status(status: str) -> Dict[str, Any]:
        """Filter by document status."""
        return {"status": status}
    
    @staticmethod
    def combine_filters(*filters: Dict[str, Any]) -> Dict[str, Any]:
        """Combine multiple filters."""
        combined = {}
        for f in filters:
            combined.update(f)
        return combined
