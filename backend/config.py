"""
Centralized configuration for the RAG system.
"""

import os
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Embedding model settings
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "384"))
USE_GPU = os.getenv("USE_GPU", "True").lower() in ("true", "1", "t")

# Document processing settings
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
MAX_LENGTH = int(os.getenv("MAX_LENGTH", "512"))
MIN_CHUNK_SIZE = int(os.getenv("MIN_CHUNK_SIZE", "200"))
MAX_SINGLE_CHUNK_SIZE = int(os.getenv("MAX_SINGLE_CHUNK_SIZE", "10000"))

# Vector database settings
VECTOR_DB_TYPE = os.getenv("VECTOR_DB_TYPE", "faiss")  # Options: "faiss", "milvus", etc.
FAISS_INDEX_TYPE = os.getenv("FAISS_INDEX_TYPE", "Flat")  # Options: "Flat", "IVF", "HNSW"
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
DB_NAME = os.getenv("DB_NAME", "rag_db")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "documents")

# Retrieval settings
TOP_K = int(os.getenv("TOP_K", "5"))
SEARCH_TYPE = os.getenv("SEARCH_TYPE", "hybrid")  # Options: "semantic", "keyword", "hybrid"
SEMANTIC_SEARCH_WEIGHT = float(os.getenv("SEMANTIC_SEARCH_WEIGHT", "0.7"))
KEYWORD_SEARCH_WEIGHT = float(os.getenv("KEYWORD_SEARCH_WEIGHT", "0.3"))

# LLM settings
LLM_MODEL_NAME = os.getenv("LLM_MODEL", "gpt-3.5-turbo")
LLM_API_KEY = os.getenv("OPENAI_API_KEY")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))

# HuggingFace API settings
HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
HUGGINGFACE_MODEL = os.getenv("HUGGINGFACE_MODEL", "mistralai/Mistral-7B-Instruct-v0.2")

# Local LLM settings (optional)
LOCAL_LLM_MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "google/flan-t5-base")
USE_LOCAL_LLM = os.getenv("USE_LOCAL_LLM", "False").lower() in ("true", "1", "t")

# API settings
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# Logging settings
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FORMAT = os.getenv("LOG_FORMAT", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Default prompt template
DEFAULT_PROMPT_TEMPLATE = """
Answer the following question based ONLY on the provided context. 
If you cannot answer the question based on the context, say "I don't have enough information to answer this question."

Context:
{context}

Question: {query}

Answer:
"""

# Enhanced prompt templates for different query types
ENHANCED_PROMPT_TEMPLATE = """
You are a precise and knowledgeable assistant specialized in document analysis. 
Answer the following question based ONLY on the provided context.

If the context doesn't contain enough information, respond with "I don't have enough information to answer this question completely." and suggest what additional information might be helpful.

If the question asks about the document as a whole, synthesize the information from all provided context chunks to give an overview.

Context:
{context}

Question: {query}

Instructions:
1. Be concise and direct in your answer
2. If the context contains specific numbers, dates, or technical terms, include them in your answer
3. If the answer requires steps or a list, format it appropriately
4. Cite specific parts of the context that support your answer
5. Only use information from the provided context

Answer:
"""

# Specialized template for document summarization
DOCUMENT_SUMMARY_TEMPLATE = """
You are an expert document analyst. Based ONLY on the provided context chunks from the document, provide a comprehensive summary.

Context:
{context}

Instructions:
1. Identify the main topic or purpose of the document
2. Summarize the key points, findings, or arguments
3. Note any significant data, statistics, or evidence mentioned
4. Highlight the organizational structure if apparent
5. Mention any limitations or gaps that are evident in these excerpts
6. Do not introduce information not present in the context

Summary:
"""

# Template for comparing/contrasting document sections
DOCUMENT_COMPARE_TEMPLATE = """
Analyze the following context chunks from the document and compare/contrast the information they contain.

Context chunks:
{context}

Instructions:
1. Identify common themes or topics across the chunks
2. Highlight any contradictions or inconsistencies
3. Note progression of ideas or arguments
4. Identify any relationships between different sections
5. Only use information present in the provided context

Analysis:
"""

# Template for technical document analysis
TECHNICAL_DOCUMENT_TEMPLATE = """
You are a technical documentation specialist. Analyze the following code or technical content from the document.

Technical content:
{context}

Question: {query}

Instructions:
1. If code is present, explain its purpose and functionality
2. Identify any APIs, functions, or important components
3. Note any technical requirements or dependencies mentioned
4. Highlight best practices or implementation details
5. Only use information from the provided context

Analysis:
"""

# Chain of Thought template for complex reasoning
CHAIN_OF_THOUGHT_TEMPLATE = """
Answer the following question based ONLY on the provided context.
Think step-by-step to solve this problem:

1. First, identify the key information in the context that's relevant to the question.
2. Consider what facts from the context are needed to answer accurately.
3. Break down any complex reasoning into clear logical steps.
4. Reason carefully about how these pieces of information connect.
5. Finally, formulate your answer based on this reasoning.

Context:
{context}

Question: {query}

Step-by-step reasoning:
"""


def get_logging_config() -> Dict[str, Any]:
    """Get logging configuration dictionary."""
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": LOG_FORMAT
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": LOG_LEVEL,
                "formatter": "standard",
                "stream": "ext://sys.stdout"
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": LOG_LEVEL,
                "propagate": True
            }
        }
    }


def get_model_config(model_name: Optional[str] = None) -> Dict[str, Any]:
    """Get model-specific configuration."""
    # Default to the configured model if none specified
    if model_name is None:
        model_name = EMBEDDING_MODEL_NAME
        
    # Common configurations for popular models
    config_map = {
        "sentence-transformers/all-MiniLM-L6-v2": {
            "dimension": 384,
            "max_length": 512,
            "normalize": True,
        },
        "sentence-transformers/all-mpnet-base-v2": {
            "dimension": 768,
            "max_length": 512,
            "normalize": True,
        },
        # Add more models as needed
    }
    
    # Return specific config if available, otherwise return default values
    return config_map.get(model_name, {
        "dimension": EMBEDDING_DIMENSION,
        "max_length": MAX_LENGTH,
        "normalize": True,
    })