"""
Grounded RAG implementation with source citation and hallucination guardrails.
P6 requirement: Refuse to answer from general knowledge, mandatory source citation.
"""

import logging
from typing import List, Dict, Any, Optional
import re

from document.evidence_tracker import create_rag_response, RAGResponse

logger = logging.getLogger(__name__)


class GroundedRAG:
    """
    Grounded RAG system that only answers based on provided context.
    Includes guardrails against hallucination and mandatory source citation.
    """
    
    # Prompt template with anti-hallucination guardrail
    GROUNDED_PROMPT_TEMPLATE = """You are a precise document analysis assistant. You MUST follow these rules strictly:

1. Answer ONLY using information from the provided context below
2. If the context does not contain enough information to answer the question, you MUST respond with: "I don't have enough information in the provided documents to answer this question."
3. NEVER use your general knowledge or training data to answer
4. Be specific and cite which parts of the context support your answer
5. If you're uncertain, say so explicitly

Context from documents:
{context}

Question: {query}

Instructions:
- Read the context carefully
- Only answer if the information is explicitly in the context
- If not found in context, respond with the exact phrase: "I don't have enough information in the provided documents to answer this question."
- Be concise and accurate

Answer:"""

    SUMMARY_TEMPLATE = """You are a document summarization assistant. Your task is to summarize the provided documents accurately.

Context from documents:
{context}

Instructions:
1. Summarize ONLY the information present in the documents above
2. Organize the summary by main topics or themes
3. Be comprehensive but concise
4. Do NOT add information not present in the documents
5. If the documents are incomplete or unclear, state that explicitly

Summary:"""

    COMPARISON_TEMPLATE = """You are a document comparison assistant. Compare the information in the provided documents.

Context from documents:
{context}

Question: {query}

Instructions:
1. Compare ONLY information present in the provided documents
2. Highlight similarities and differences
3. Note any contradictions or inconsistencies
4. Be objective and precise
5. Do NOT add external information

Comparison:"""

    def __init__(self, llm_generator):
        """
        Initialize grounded RAG system.
        
        Args:
            llm_generator: LLM generator function (takes prompt, returns response)
        """
        self.llm_generator = llm_generator
        logger.info("GroundedRAG initialized with anti-hallucination guardrails")
    
    def generate_response(
        self,
        query: str,
        retrieved_documents: List[Dict[str, Any]],
        template: Optional[str] = None,
        max_tokens: int = 512
    ) -> RAGResponse:
        """
        Generate a grounded response with mandatory source citation.
        
        Args:
            query: User query
            retrieved_documents: Documents retrieved from hybrid search
            template: Optional custom prompt template
            max_tokens: Maximum tokens in response
            
        Returns:
            RAGResponse with answer and evidence
        """
        if not retrieved_documents:
            logger.warning("No documents provided for RAG generation")
            return self._create_no_documents_response(query)
        
        # Build context from retrieved documents
        context = self._build_context(retrieved_documents)
        
        # Select appropriate template
        if template is None:
            template = self._select_template(query)
        
        # Build prompt
        prompt = template.format(context=context, query=query)
        
        # Generate response
        try:
            response_text = self.llm_generator(prompt, max_tokens=max_tokens)
            
            # Check if response indicates lack of information
            if self._is_no_info_response(response_text):
                logger.info("LLM indicated insufficient information in documents")
            
            # Create RAG response with evidence
            rag_response = create_rag_response(
                query=query,
                response=response_text,
                retrieved_documents=retrieved_documents,
                search_type="grounded"
            )
            
            return rag_response
            
        except Exception as e:
            logger.error(f"Error generating grounded response: {e}")
            return self._create_error_response(query, str(e))
    
    def _build_context(
        self, 
        retrieved_documents: List[Dict[str, Any]],
        max_context_length: int = 3000
    ) -> str:
        """
        Build context string from retrieved documents with source attribution.
        
        Args:
            retrieved_documents: Retrieved document chunks
            max_context_length: Maximum context length in characters
            
        Returns:
            Formatted context string
        """
        context_parts = []
        current_length = 0
        
        for idx, doc in enumerate(retrieved_documents, 1):
            text = doc.get("text", "")
            metadata = doc.get("metadata", {})
            
            # Format with source attribution
            source = metadata.get("filename", metadata.get("source", "Unknown"))
            page = metadata.get("page", "unknown")
            
            doc_context = f"[Document {idx} - Source: {source}, Page: {page}]\n{text}\n"
            
            # Check length limit
            if current_length + len(doc_context) > max_context_length:
                break
            
            context_parts.append(doc_context)
            current_length += len(doc_context)
        
        return "\n---\n".join(context_parts)
    
    def _select_template(self, query: str) -> str:
        """
        Select appropriate prompt template based on query type.
        
        Args:
            query: User query
            
        Returns:
            Selected prompt template
        """
        query_lower = query.lower()
        
        # Check for summary queries
        if any(word in query_lower for word in ["summarize", "summary", "overview", "what is this document about"]):
            return self.SUMMARY_TEMPLATE
        
        # Check for comparison queries
        if any(word in query_lower for word in ["compare", "difference", "similar", "contrast", "versus", "vs"]):
            return self.COMPARISON_TEMPLATE
        
        # Default to grounded QA template
        return self.GROUNDED_PROMPT_TEMPLATE
    
    @staticmethod
    def _is_no_info_response(response: str) -> bool:
        """
        Check if response indicates lack of information.
        
        Args:
            response: LLM response
            
        Returns:
            True if response indicates insufficient information
        """
        no_info_patterns = [
            "don't have enough information",
            "cannot answer",
            "not found in the documents",
            "insufficient information",
            "not provided in the context",
            "no information about"
        ]
        
        response_lower = response.lower()
        return any(pattern in response_lower for pattern in no_info_patterns)
    
    @staticmethod
    def _create_no_documents_response(query: str) -> RAGResponse:
        """Create response when no documents are provided."""
        from document.evidence_tracker import Evidence
        
        return RAGResponse(
            query=query,
            response="I don't have any documents to answer this question. Please upload relevant documents first.",
            evidence=[],
            search_type="grounded",
            confidence=0.0
        )
    
    @staticmethod
    def _create_error_response(query: str, error: str) -> RAGResponse:
        """Create response when an error occurs."""
        from document.evidence_tracker import Evidence
        
        return RAGResponse(
            query=query,
            response=f"An error occurred while processing your question: {error}",
            evidence=[],
            search_type="grounded",
            confidence=0.0
        )
    
    def validate_response(self, response: RAGResponse) -> Dict[str, Any]:
        """
        Validate that a response meets grounding requirements.
        
        Args:
            response: RAG response to validate
            
        Returns:
            Validation result with warnings
        """
        warnings = []
        
        # Check if evidence is provided
        if not response.evidence:
            warnings.append("No evidence/sources provided for the response")
        
        # Check if confidence is too low
        if response.confidence < 0.3:
            warnings.append(f"Low confidence score: {response.confidence:.2f}")
        
        # Check for potential hallucination indicators
        response_text = response.response.lower()
        hallucination_indicators = [
            "i think", "probably", "maybe", "it's possible",
            "in general", "typically", "usually"
        ]
        
        found_indicators = [
            ind for ind in hallucination_indicators 
            if ind in response_text
        ]
        
        if found_indicators:
            warnings.append(
                f"Response contains uncertainty indicators: {', '.join(found_indicators)}"
            )
        
        is_valid = len(warnings) == 0
        
        return {
            "is_valid": is_valid,
            "confidence": response.confidence,
            "evidence_count": len(response.evidence),
            "warnings": warnings
        }


class CitationEnforcer:
    """
    Utility to ensure all RAG responses include proper citations.
    """
    
    @staticmethod
    def add_citations_to_response(
        response_text: str, 
        evidence_list: List[Dict[str, Any]]
    ) -> str:
        """
        Add source citations to response text.
        
        Args:
            response_text: Generated response
            evidence_list: List of evidence items
            
        Returns:
            Response with citations appended
        """
        if not evidence_list:
            return response_text
        
        citations = ["\n\n**Sources:**"]
        
        for idx, evidence in enumerate(evidence_list, 1):
            source = evidence.get("source_document", "Unknown")
            page = evidence.get("page", "?")
            confidence = evidence.get("confidence", 0.0)
            
            citations.append(
                f"{idx}. {source} (Page {page}) - Confidence: {confidence:.2f}"
            )
        
        return response_text + "\n".join(citations)
    
    @staticmethod
    def extract_cited_sources(response_text: str) -> List[str]:
        """
        Extract source citations from response text.
        
        Args:
            response_text: Response with citations
            
        Returns:
            List of cited source names
        """
        # Look for citation patterns like [1], [Source: ...], etc.
        citation_patterns = [
            r'\[(\d+)\]',
            r'\[Source: ([^\]]+)\]',
            r'\(([^)]+), Page \d+\)'
        ]
        
        sources = []
        for pattern in citation_patterns:
            matches = re.findall(pattern, response_text)
            sources.extend(matches)
        
        return list(set(sources))
