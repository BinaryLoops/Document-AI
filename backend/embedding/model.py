"""
Unified embedding model implementation supporting multiple backends.
"""

from typing import List, Union, Optional, Dict, Any
import logging
import numpy as np
import torch
from abc import ABC, abstractmethod

# Configure logging
logger = logging.getLogger(__name__)


class EmbeddingModel(ABC):
    """Abstract base class for embedding models."""
    
    @abstractmethod
    def embed(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Convert text(s) to embedding vector(s).
        
        Args:
            texts: Input text(s) to embed
            batch_size: Batch size for processing
            
        Returns:
            Embedding vector(s) as numpy array
        """
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        pass


class SentenceTransformerEmbedding(EmbeddingModel):
    """Embedding model using sentence-transformers library."""
    
    def __init__(
        self, 
        model_name: str = "all-MiniLM-L6-v2",
        device: Optional[str] = None,
        normalize: bool = True,
        **kwargs
    ):
        """
        Initialize the sentence transformer embedding model.
        
        Args:
            model_name: Sentence transformer model name or path
            device: Device to run model on ('cpu', 'cuda', 'cuda:0', etc.)
            normalize: Whether to L2-normalize embeddings
            **kwargs: Additional arguments for the model
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers is not installed. "
                "Please install it with `pip install sentence-transformers`."
            )
        
        self.model_name = model_name
        self.normalize = normalize
        
        # Determine device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Loading SentenceTransformer model: {model_name} on {self.device}")
        try:
            self.model = SentenceTransformer(model_name, device=self.device)
            self._dimension = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Embedding dimension: {self._dimension}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def embed(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Convert text(s) to embedding vector(s).
        
        Args:
            texts: Input text(s) to embed
            batch_size: Batch size for processing
            
        Returns:
            Embedding vector(s) as numpy array
        """
        # Handle single text input
        if isinstance(texts, str):
            texts = [texts]
            
        # Validate input
        if not texts:
            logger.warning("Empty texts provided for embedding")
            return np.array([])
            
        try:
            # Generate embeddings
            embeddings = self.model.encode(
                texts, 
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Normalize if requested
            if self.normalize:
                embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)
                
            return embeddings
        except Exception as e:
            logger.error(f"Error during embedding generation: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self._dimension


class HuggingFaceEmbedding(EmbeddingModel):
    """Embedding model using HuggingFace transformers directly."""
    
    def __init__(
        self, 
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: Optional[str] = None,
        normalize: bool = True,
        max_length: int = 512,
        **kwargs
    ):
        """
        Initialize the HuggingFace embedding model.
        
        Args:
            model_name: HuggingFace model name or path
            device: Device to run model on ('cpu', 'cuda', 'cuda:0', etc.)
            normalize: Whether to L2-normalize embeddings
            max_length: Maximum token length for inputs
            **kwargs: Additional arguments for the model
        """
        try:
            from transformers import AutoTokenizer, AutoModel
        except ImportError:
            raise ImportError(
                "transformers is not installed. "
                "Please install it with `pip install transformers`."
            )
        
        self.model_name = model_name
        self.normalize = normalize
        self.max_length = max_length
        
        # Determine device
        if device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = device
            
        logger.info(f"Loading HuggingFace model: {model_name} on {self.device}")
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            
            # Get embedding dimension from model config
            self._dimension = self.model.config.hidden_size
            logger.info(f"Model loaded successfully. Embedding dimension: {self._dimension}")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def _mean_pooling(self, model_output, attention_mask):
        """Perform mean pooling on token embeddings."""
        token_embeddings = model_output.last_hidden_state
        input_mask_expanded = attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(input_mask_expanded.sum(1), min=1e-9)
    
    def embed(self, texts: Union[str, List[str]], batch_size: int = 32) -> np.ndarray:
        """
        Convert text(s) to embedding vector(s).
        
        Args:
            texts: Input text(s) to embed
            batch_size: Batch size for processing
            
        Returns:
            Embedding vector(s) as numpy array
        """
        # Handle single text input
        if isinstance(texts, str):
            texts = [texts]
            
        # Validate input
        if not texts:
            logger.warning("Empty texts provided for embedding")
            return np.array([])
            
        try:
            all_embeddings = []
            
            # Process in batches
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                
                # Tokenize and move to device
                inputs = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=self.max_length,
                    return_tensors="pt"
                )
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                # Generate embeddings
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    embeddings = self._mean_pooling(outputs, inputs["attention_mask"])
                    
                    # Normalize if requested
                    if self.normalize:
                        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                        
                    # Move to CPU and convert to numpy
                    embeddings = embeddings.cpu().numpy()
                    all_embeddings.append(embeddings)
            
            # Concatenate all batches
            return np.vstack(all_embeddings) if all_embeddings else np.array([])
            
        except Exception as e:
            logger.error(f"Error during embedding generation: {e}")
            raise
    
    @property
    def dimension(self) -> int:
        """Get the dimension of the embedding vectors."""
        return self._dimension


# Factory function to create embedding models
def create_embedding_model(
    backend: str = "sentence-transformers",
    model_name: Optional[str] = None,
    **kwargs
) -> EmbeddingModel:
    """
    Factory function to create an embedding model.
    
    Args:
        backend: Backend to use ('sentence-transformers' or 'huggingface')
        model_name: Model name or path
        **kwargs: Additional arguments for the model
        
    Returns:
        An EmbeddingModel instance
    """
    from config import EMBEDDING_MODEL_NAME, get_model_config
    
    # Use config model if not specified
    if model_name is None:
        model_name = EMBEDDING_MODEL_NAME
    
    # Get model-specific config
    model_config = get_model_config(model_name)
    
    # Override with provided kwargs
    for k, v in kwargs.items():
        model_config[k] = v
    
    # Create the model
    if backend.lower() == "sentence-transformers":
        return SentenceTransformerEmbedding(model_name=model_name, **model_config)
    elif backend.lower() in ["huggingface", "hf", "transformers"]:
        return HuggingFaceEmbedding(model_name=model_name, **model_config)
    else:
        raise ValueError(f"Unsupported backend: {backend}")
