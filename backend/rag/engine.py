"""
Main RAG (Retrieval-Augmented Generation) engine implementation.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


class RAGEngine:
    """Retrieval-Augmented Generation (RAG) engine for question answering."""
    
    def __init__(
        self,
        embedder,
        vector_db,
        llm=None,
        top_k: int = 5,
        search_type: str = "hybrid",
        prompt_template: Optional[str] = None
    ):
        """
        Initialize the RAG engine.
        
        Args:
            embedder: Embedding model
            vector_db: Vector database for document storage and retrieval
            llm: Language model for text generation (optional)
            top_k: Number of documents to retrieve
            search_type: Type of search ('semantic', 'keyword', 'hybrid')
            prompt_template: Optional custom prompt template
        """
        self.embedder = embedder
        self.vector_db = vector_db
        self.llm = llm
        self.top_k = top_k
        self.search_type = search_type
        
        # Set default prompt template if none provided
        if prompt_template is None:
            try:
                from config import DEFAULT_PROMPT_TEMPLATE
                self.prompt_template = DEFAULT_PROMPT_TEMPLATE
            except ImportError:
                # Fallback template if config not available
                self.prompt_template = """
                Answer the following question based ONLY on the provided context.
                If you cannot answer the question based on the context, say "I don't have enough information to answer this question."

                Context:
                {context}

                Question: {query}

                Answer:
                """
        else:
            self.prompt_template = prompt_template
    
    def add_documents(
        self,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None,
        batch_size: int = 32
    ) -> List[str]:
        """
        Add documents to the database.
        
        Args:
            texts: List of text chunks
            metadata: Optional list of metadata dictionaries for each text
            batch_size: Batch size for embedding generation
            
        Returns:
            List of document IDs
        """
        from storage.vector_db import Document
        
        # Handle metadata
        if metadata is None:
            metadata = [{} for _ in texts]
        elif len(metadata) != len(texts):
            raise ValueError(f"Length mismatch: got {len(texts)} texts but {len(metadata)} metadata entries")
        
        # Log what we're adding
        logger.info(f"Adding {len(texts)} documents to database")
        logger.info(f"First document sample: {texts[0][:100]}...")
        
        # Generate embeddings in batches
        doc_ids = []
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            batch_metadata = metadata[i:i+batch_size]
            
            # Generate embeddings
            logger.info(f"Generating embeddings for batch {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}")
            batch_embeddings = self.embedder.embed(batch_texts)
            
            # Create document objects
            documents = []
            for text, meta, embedding in zip(batch_texts, batch_metadata, batch_embeddings):
                doc = Document(text=text, metadata=meta, embedding=embedding)
                documents.append(doc)
            
            # Add to database
            batch_ids = self.vector_db.add_documents(documents)
            doc_ids.extend(batch_ids)
        
        logger.info(f"Added {len(doc_ids)} documents to database")
        return doc_ids
    
    def search(
        self,
        query: str,
        top_k: Optional[int] = None,
        search_type: Optional[str] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for relevant documents.
        
        Args:
            query: Query string
            top_k: Number of results to return (defaults to self.top_k)
            search_type: Type of search (defaults to self.search_type)
            filter_dict: Dictionary of metadata filters
            
        Returns:
            List of document dictionaries
        """
        if top_k is None:
            top_k = self.top_k
            
        if search_type is None:
            search_type = self.search_type
            
        # Print debugging info
        logger.info(f"Searching for: '{query}' with search_type={search_type}, top_k={top_k}")
        
        # Create filter function if filter_dict is provided
        filter_func = None
        if filter_dict:
            def filter_func(doc):
                for key, value in filter_dict.items():
                    # Handle nested keys (e.g., "metadata.source")
                    if "." in key:
                        parts = key.split(".")
                        current = doc.metadata
                        for part in parts[:-1]:
                            if part not in current:
                                return False
                            current = current[part]
                        if parts[-1] not in current or current[parts[-1]] != value:
                            return False
                    elif key not in doc.metadata or doc.metadata[key] != value:
                        return False
                return True
        
        try:
            # Generate query embedding
            query_embedding = self.embedder.embed(query)
            
            # Log embedding info
            logger.info(f"Query embedding created with shape: {query_embedding.shape}")
            
            # Perform search
            results = self.vector_db.search(query_embedding, top_k, filter_func)
            
            # Log what was found
            logger.info(f"Found {len(results)} results")
            for i, (doc, score) in enumerate(results[:3]):  # Log first 3 results
                logger.info(f"Result {i+1}: score={score:.4f}, id={doc.id}, text='{doc.text[:100]}...'")
            
            # Convert results to dictionaries
            return [
                {
                    "id": doc.id,
                    "text": doc.text,
                    "metadata": doc.metadata,
                    "score": float(score)
                }
                for doc, score in results
            ]
        except Exception as e:
            logger.error(f"Error during search: {e}", exc_info=True)
            return []
    
    def generate_response(
        self,
        query: str,
        top_k: Optional[int] = None,
        search_type: Optional[str] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        max_tokens: int = 512,
        use_reasoning: bool = False
    ) -> Dict[str, Any]:
        """
        Generate a response to a query using RAG.
        
        Args:
            query: Query string
            top_k: Number of documents to retrieve
            search_type: Type of search
            filter_dict: Optional filter for document retrieval
            max_tokens: Maximum number of tokens in the response
            use_reasoning: Whether to use chain-of-thought reasoning
            
        Returns:
            Dictionary with query, response, and retrieved documents
        """
        # Retrieve relevant documents
        retrieved_docs = self.search(query, top_k, search_type, filter_dict)
        
        # If no documents were found, return a default message
        if not retrieved_docs:
            logger.warning("No relevant documents found for query")
            return {
                "query": query,
                "response": "I couldn't find any relevant information to answer your question.",
                "retrieved_documents": [],
                "search_type": search_type or self.search_type
            }
        
        # Format context from retrieved documents
        context = self._format_context(retrieved_docs)
        logger.info(f"Formatted context with {len(retrieved_docs)} documents, length: {len(context)} chars")
        
        # Get metadata for template selection
        metadata = [doc.get("metadata", {}) for doc in retrieved_docs]
        
        # Check if the question is complex and might benefit from CoT
        is_complex_question = any(term in query.lower() for term in [
            'why', 'how', 'explain', 'reason', 'analyze', 'compare', 'relationship'
        ])
        
        # Select appropriate template based on query and context
        template = self.prompt_template
        template_name = "default"
        current_llm = self.llm
        
        try:
            from rag.template_selector import TemplateSelector
            template_selector = TemplateSelector()
            template = template_selector.select_template(query, context, metadata, use_reasoning)
            template_name = getattr(template_selector, "selected_template_name", "default")
            logger.info(f"Using template: {template_name}")
            
            # Apply CoT wrapper for complex questions or if reasoning is requested
            if (template_name in ["chain_of_thought", "technical", "compare"] and is_complex_question) or use_reasoning:
                from llm.model import ChainOfThoughtLLM
                current_llm = ChainOfThoughtLLM(self.llm)
                logger.info(f"Using Chain of Thought reasoning for complex question")
        except Exception as e:
            logger.warning(f"Could not use template selector: {e}, using default template")
        
        # Format prompt with context and query
        prompt = template.format(context=context, query=query)
        logger.info(f"Created prompt of length {len(prompt)} chars")
        
        # Log sample of the prompt for debugging
        logger.info(f"Prompt sample: {prompt[:500]}...")
        
        # Generate response using LLM
        if self.llm is None:
            # Create a simple local LLM if none is provided
            from llm.model import LocalLLM
            logger.info("No LLM provided, creating a simple local LLM")
            self.llm = LocalLLM()
            response = self._generate_llm_response(prompt, max_tokens, llm=current_llm)
        else:
            response = self._generate_llm_response(prompt, max_tokens, llm=current_llm)
        
        logger.info(f"Generated response of length {len(response)} chars")
        
        # Return the results
        result = {
            "query": query,
            "response": response,
            "retrieved_documents": retrieved_docs,
            "search_type": search_type or self.search_type,
            "template_used": template_name,
            "context_length": len(context)
        }
        
        # Add reasoning info if ChainOfThoughtLLM was used
        try:
            from llm.model import ChainOfThoughtLLM
            result["reasoning_used"] = isinstance(current_llm, ChainOfThoughtLLM)
        except ImportError:
            result["reasoning_used"] = False
            
        return result
    
    def _format_context(self, documents: List[Dict[str, Any]]) -> str:
        """
        Format retrieved documents into context for the prompt.
        
        Args:
            documents: List of retrieved documents
            
        Returns:
            Formatted context string
        """
        # Log how many documents we're formatting
        logger.info(f"Formatting context from {len(documents)} documents")
        
        if not documents:
            logger.warning("No documents provided for context formatting")
            return "No relevant context found."
            
        context_parts = []
        
        for i, doc in enumerate(documents):
            # Extract relevant fields
            text = doc["text"]
            metadata = doc["metadata"]
            source = metadata.get("source", "Unknown")
            
            # Skip empty documents
            if not text or not text.strip():
                logger.warning(f"Empty document at index {i}, skipping")
                continue
                
            # Format the document with clear separation
            doc_text = f"Document {i+1}: [Source: {source}]\n{text}\n\n"
            context_parts.append(doc_text)
        
        # Join all context parts with clear separation
        context = "\n".join(context_parts)
        
        # Log context length and preview for debugging
        logger.info(f"Created context of length {len(context)} characters")
        if context:
            logger.info(f"Context preview: {context[:200]}...")
        
        # Add fallback if context is empty
        if not context.strip():
            logger.warning("Empty context created after formatting, adding fallback")
            return "No relevant context found."
            
        return context
    
    def _generate_llm_response(self, prompt: str, max_tokens: int, llm=None) -> str:
        """
        Generate a response using the LLM.
        
        Args:
            prompt: The formatted prompt
            max_tokens: Maximum number of tokens in the response
            llm: Optional override LLM to use (defaults to self.llm)
            
        Returns:
            Generated response
        """
        # Use provided LLM or fall back to instance LLM
        current_llm = llm or self.llm
        
        try:
            # Make sure the prompt has a context section
            if "Context:" not in prompt:
                logger.warning("Prompt is missing Context section")
                return "I couldn't process your question due to a system error."
                
            # Make sure context is not empty
            context_section = prompt.split("Context:")[1].split("Question:")[0].strip()
            if not context_section:
                logger.warning("Context section is empty in prompt")
                return "I don't have enough information to answer this question."
            
            # Use appropriate method based on LLM type
            if hasattr(current_llm, "generate_openai_response"):
                # OpenAI-compatible LLM
                return current_llm.generate_openai_response(prompt, max_tokens)
            elif hasattr(current_llm, "generate_huggingface_response"):
                # HuggingFace-compatible LLM
                return current_llm.generate_huggingface_response(prompt, max_tokens)
            else:
                # Default implementation
                return current_llm.generate_response(prompt, max_tokens)
        except Exception as e:
            logger.error(f"Error generating response: {e}", exc_info=True)
            return f"I encountered an error while generating a response: {str(e)}"
    
    def update_prompt_template(self, new_template: str) -> None:
        """
        Update the prompt template.
        
        Args:
            new_template: New prompt template
        """
        self.prompt_template = new_template
        logger.info("Updated prompt template")
    
    def count_documents(self) -> int:
        """
        Get the number of documents in the database.
        
        Returns:
            Number of documents
        """
        return self.vector_db.count_documents()
    
    def clear_documents(self) -> None:
        """Clear all documents from the database."""
        self.vector_db.clear()
        logger.info("Cleared all documents from database")


# Factory function to create the RAG engine
def create_rag_engine(
    embedder=None,
    vector_db=None,
    llm=None,
    config=None
) -> RAGEngine:
    """
    Factory function to create a RAG engine.
    
    Args:
        embedder: Embedding model (if None, created based on config)
        vector_db: Vector database (if None, created based on config)
        llm: Language model (if None, created based on config)
        config: Configuration module or dictionary
        
    Returns:
        Configured RAGEngine instance
    """
    # Load configuration if provided
    if config is None:
        try:
            # Use absolute imports to avoid issues
            from config import (
                TOP_K,
                SEARCH_TYPE,
                DEFAULT_PROMPT_TEMPLATE
            )
        except ImportError:
            # Default values if config not available
            TOP_K = 5
            SEARCH_TYPE = "hybrid"
            DEFAULT_PROMPT_TEMPLATE = """
            Answer the following question based ONLY on the provided context.
            
            Context:
            {context}
            
            Question: {query}
            
            Answer:
            """
    else:
        TOP_K = config.get("TOP_K", 5)
        SEARCH_TYPE = config.get("SEARCH_TYPE", "hybrid")
        DEFAULT_PROMPT_TEMPLATE = config.get(
            "DEFAULT_PROMPT_TEMPLATE",
            """
            Answer the following question based ONLY on the provided context.
            
            Context:
            {context}
            
            Question: {query}
            
            Answer:
            """
        )
    
    # Create embedding model if not provided
    if embedder is None:
        try:
            from embedding.model import create_embedding_model
            embedder = create_embedding_model()
        except Exception as e:
            logger.error(f"Error creating embedding model: {e}", exc_info=True)
            raise
    
    # Create vector database if not provided
    if vector_db is None:
        try:
            from storage.vector_db import create_vector_database
            vector_db = create_vector_database(dimension=embedder.dimension)
        except Exception as e:
            logger.error(f"Error creating vector database: {e}", exc_info=True)
            raise
    
    # Create language model if not provided
    if llm is None:
        try:
            from llm.model import create_llm
            llm = create_llm()
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"LLM module not found, proceeding without an LLM: {e}")
    
    # Create and return the RAG engine
    return RAGEngine(
        embedder=embedder,
        vector_db=vector_db,
        llm=llm,
        top_k=TOP_K,
        search_type=SEARCH_TYPE,
        prompt_template=DEFAULT_PROMPT_TEMPLATE
    )