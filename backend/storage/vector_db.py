"""
Vector database implementation for document storage and retrieval.
"""

from typing import List, Dict, Any, Optional, Union, Tuple, Callable
import logging
import os
import json
import uuid
import numpy as np
from dataclasses import dataclass, field, asdict

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Document:
    """Class to represent a document or text chunk with metadata and embeddings."""
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = asdict(self)
        # Convert numpy array to list for JSON serialization
        if self.embedding is not None:
            result['embedding'] = self.embedding.tolist()
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Document':
        """Create Document from dictionary."""
        if 'embedding' in data and data['embedding'] is not None:
            data['embedding'] = np.array(data['embedding'], dtype=np.float32)
        return cls(**data)


class VectorDatabase:
    """Base class for vector databases."""
    
    def __init__(self, dimension: int = 384):
        """
        Initialize the vector database.
        
        Args:
            dimension: Dimension of the embedding vectors
        """
        self.dimension = dimension
    
    def add_document(self, document: Document) -> str:
        """
        Add a document to the database.
        
        Args:
            document: Document to add
            
        Returns:
            Document ID
        """
        raise NotImplementedError("Subclasses must implement add_document")
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        Add multiple documents to the database.
        
        Args:
            documents: List of documents to add
            
        Returns:
            List of document IDs
        """
        return [self.add_document(doc) for doc in documents]
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_func: Optional[Callable[[Document], bool]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_func: Optional function to filter results
            
        Returns:
            List of (document, score) tuples
        """
        raise NotImplementedError("Subclasses must implement search")
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the database.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            True if document was deleted, False otherwise
        """
        raise NotImplementedError("Subclasses must implement delete_document")
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID to get
            
        Returns:
            Document if found, None otherwise
        """
        raise NotImplementedError("Subclasses must implement get_document")
    
    def count_documents(self) -> int:
        """
        Get the number of documents in the database.
        
        Returns:
            Number of documents
        """
        raise NotImplementedError("Subclasses must implement count_documents")
    
    def clear(self) -> None:
        """Clear all documents from the database."""
        raise NotImplementedError("Subclasses must implement clear")
    
    def save(self, directory: str) -> None:
        """
        Save the database to disk.
        
        Args:
            directory: Directory to save to
        """
        raise NotImplementedError("Subclasses must implement save")
    
    @classmethod
    def load(cls, directory: str) -> 'VectorDatabase':
        """
        Load a database from disk.
        
        Args:
            directory: Directory to load from
            
        Returns:
            Loaded database
        """
        raise NotImplementedError("Subclasses must implement load")


class FaissVectorDatabase(VectorDatabase):
    """Vector database implementation using FAISS."""
    
    def __init__(self, dimension: int = 384, index_type: str = "Flat"):
        """
        Initialize the FAISS vector database.
        
        Args:
            dimension: Dimension of the embedding vectors
            index_type: FAISS index type (e.g., "Flat", "IVF", "HNSW")
        """
        super().__init__(dimension)
        self.index_type = index_type
        self.documents: Dict[str, Document] = {}
        self.id_to_index: Dict[str, int] = {}
        self.index_to_id: Dict[int, str] = {}
        
        # Initialize FAISS index
        self._initialize_index()
    
    def _initialize_index(self):
        """Initialize FAISS index based on the specified type."""
        try:
            import faiss
        except ImportError:
            raise ImportError(
                "faiss-cpu is not installed. "
                "Please install it with `pip install faiss-cpu` or `pip install faiss-gpu`."
            )
        
        if self.index_type == "Flat":
            self.index = faiss.IndexFlatL2(self.dimension)
        elif self.index_type == "IVF":
            # IVF requires training, so we'll use a placeholder
            # This would need to be trained on actual data
            quantizer = faiss.IndexFlatL2(self.dimension)
            n_cells = 100  # Number of centroids
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, n_cells)
            self.index.nprobe = 10  # Number of cells to probe at search time
        elif self.index_type == "HNSW":
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)  # 32 neighbors per node
        else:
            logger.warning(f"Unknown index type {self.index_type}, falling back to Flat")
            self.index = faiss.IndexFlatL2(self.dimension)
        
        # Mark if index needs training
        self.needs_training = self.index_type in ["IVF"]
    
    def add_document(self, document: Document) -> str:
        """
        Add a document to the database.
        
        Args:
            document: Document to add
            
        Returns:
            Document ID
        """
        # If no embedding is provided, log warning
        if document.embedding is None:
            logger.warning(f"Document {document.id} has no embedding - skipping indexing")
            self.documents[document.id] = document
            return document.id
        
        # Ensure embedding is in the right format
        embedding = np.array([document.embedding], dtype=np.float32)
        
        # Train index if needed and we have enough data
        if self.needs_training and len(self.documents) >= 100 and not self.index.is_trained:
            logger.info("Training FAISS index")
            # Collect 1000 embeddings for training
            train_data = np.vstack([doc.embedding for doc in list(self.documents.values())[:1000]])
            self.index.train(train_data)
        
        # Add to FAISS index if it's trained or doesn't need training
        if not self.needs_training or self.index.is_trained:
            idx = len(self.id_to_index)
            self.index.add(embedding)
            
            # Update mapping dictionaries
            self.id_to_index[document.id] = idx
            self.index_to_id[idx] = document.id
        
        # Store document
        self.documents[document.id] = document
        
        return document.id
    
    def add_documents(self, documents: List[Document]) -> List[str]:
        """
        Add multiple documents to the database.
        
        Args:
            documents: List of Document objects
            
        Returns:
            List of document IDs
        """
        doc_ids = []
        
        # First, collect all valid documents with embeddings
        valid_docs = []
        valid_embeddings = []
        
        for doc in documents:
            if doc.embedding is not None:
                valid_docs.append(doc)
                valid_embeddings.append(doc.embedding)
        
        if not valid_docs:
            logger.warning("No valid documents with embeddings to add")
            return []
        
        # Train index if needed and we have enough data
        if self.needs_training and not self.index.is_trained:
            if len(valid_embeddings) >= 100 or (len(self.documents) + len(valid_docs)) >= 100:
                logger.info("Training FAISS index")
                # Use available embeddings for training
                train_data = np.vstack([
                    *[doc.embedding for doc in list(self.documents.values()) if doc.embedding is not None],
                    *valid_embeddings
                ])
                train_data = train_data[:min(1000, len(train_data))]  # Limit to 1000 samples
                self.index.train(train_data)
        
        # Add embeddings to FAISS index if it's trained or doesn't need training
        if not self.needs_training or self.index.is_trained:
            embeddings_array = np.array(valid_embeddings, dtype=np.float32)
            start_idx = len(self.id_to_index)
            self.index.add(embeddings_array)
            
            # Update mappings
            for i, doc in enumerate(valid_docs):
                idx = start_idx + i
                self.id_to_index[doc.id] = idx
                self.index_to_id[idx] = doc.id
        
        # Store all documents (with or without embeddings)
        for doc in documents:
            self.documents[doc.id] = doc
            doc_ids.append(doc.id)
        
        return doc_ids
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_func: Optional[Callable[[Document], bool]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_func: Optional function to filter results
            
        Returns:
            List of (document, score) tuples
        """
        if not self.documents or not self.id_to_index:
            logger.warning("Cannot search: database is empty")
            return []
        
        # Ensure index is trained if needed
        if self.needs_training and not self.index.is_trained:
            logger.warning("Cannot search: index not trained")
            return []
        
        # Convert to correct format if needed
        if len(query_embedding.shape) == 1:
            query_embedding = np.array([query_embedding], dtype=np.float32)
        
        # Check if we need to rebuild the index
        if len(self.id_to_index) != self.index.ntotal:
            logger.info("Rebuilding index before search")
            self._rebuild_index()
        
        # Adjust top_k based on available items
        effective_top_k = min(top_k, self.index.ntotal)
        if effective_top_k < top_k:
            logger.warning(f"Requested top_k={top_k} but only {effective_top_k} items in index")
        
        # Perform search
        distances, indices = self.index.search(query_embedding, effective_top_k)
        
        # Retrieve documents
        results = []
        for i, idx in enumerate(indices[0]):
            if idx != -1:  # FAISS uses -1 for padding when there aren't enough results
                doc_id = self.index_to_id.get(idx)
                if doc_id and doc_id in self.documents:
                    doc = self.documents[doc_id]
                    
                    # Apply filter if provided
                    if filter_func is None or filter_func(doc):
                        # Convert L2 distance to similarity score (1 / (1 + distance))
                        score = 1.0 / (1.0 + distances[0][i])
                        results.append((doc, score))
        
        # Sort by score in descending order
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the database.
        
        Note: FAISS doesn't support direct deletion, so we handle this
        by rebuilding the index when needed.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            True if document was found and deleted
        """
        if doc_id not in self.documents:
            return False
        
        # Remove from documents dictionary
        del self.documents[doc_id]
        
        # If document was in index, mark for rebuild
        if doc_id in self.id_to_index:
            # Remove from mappings
            del self.id_to_index[doc_id]
            # We'll rebuild the index on the next query
            
        return True
    
    def _rebuild_index(self):
        """Rebuild the FAISS index from scratch."""
        # Re-initialize the index
        self._initialize_index()
        self.id_to_index = {}
        self.index_to_id = {}
        
        # Collect all documents with embeddings
        docs_with_embeddings = [doc for doc in self.documents.values() if doc.embedding is not None]
        
        if not docs_with_embeddings:
            logger.warning("No documents with embeddings to rebuild index")
            return
        
        # Extract embeddings
        embeddings = np.array([doc.embedding for doc in docs_with_embeddings], dtype=np.float32)
        
        # Train if needed
        if self.needs_training and len(docs_with_embeddings) >= 100:
            logger.info("Training FAISS index during rebuild")
            train_data = embeddings[:min(1000, len(embeddings))]
            self.index.train(train_data)
        
        # Add to index if trained or doesn't need training
        if not self.needs_training or self.index.is_trained:
            self.index.add(embeddings)
            
            # Update mappings
            for i, doc in enumerate(docs_with_embeddings):
                self.id_to_index[doc.id] = i
                self.index_to_id[i] = doc.id
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID to get
            
        Returns:
            Document if found, None otherwise
        """
        return self.documents.get(doc_id)
    
    def count_documents(self) -> int:
        """
        Get the number of documents in the database.
        
        Returns:
            Number of documents
        """
        return len(self.documents)
    
    def clear(self) -> None:
        """Clear all documents from the database."""
        self.documents = {}
        self.id_to_index = {}
        self.index_to_id = {}
        self._initialize_index()
    
    def save(self, directory: str) -> None:
        """
        Save the database to disk.
        
        Args:
            directory: Directory to save to
        """
        import faiss
        
        os.makedirs(directory, exist_ok=True)
        
        # Save documents
        documents_data = {doc_id: doc.to_dict() for doc_id, doc in self.documents.items()}
        with open(os.path.join(directory, "documents.json"), "w") as f:
            json.dump(documents_data, f)
        
        # Save mappings
        mappings = {
            "id_to_index": self.id_to_index,
            "index_to_id": {str(k): v for k, v in self.index_to_id.items()}  # Convert int keys to strings for JSON
        }
        with open(os.path.join(directory, "mappings.json"), "w") as f:
            json.dump(mappings, f)
        
        # Save index
        faiss.write_index(self.index, os.path.join(directory, "faiss_index.bin"))
        
        # Save metadata
        metadata = {
            "dimension": self.dimension,
            "index_type": self.index_type,
            "document_count": len(self.documents)
        }
        with open(os.path.join(directory, "metadata.json"), "w") as f:
            json.dump(metadata, f)
    
    @classmethod
    def load(cls, directory: str) -> 'FaissVectorDatabase':
        """
        Load a database from disk.
        
        Args:
            directory: Directory to load from
            
        Returns:
            Loaded FaissVectorDatabase
        """
        import faiss
        
        # Load metadata
        with open(os.path.join(directory, "metadata.json"), "r") as f:
            metadata = json.load(f)
        
        # Create instance
        db = cls(dimension=metadata["dimension"], index_type=metadata["index_type"])
        
        # Load documents
        with open(os.path.join(directory, "documents.json"), "r") as f:
            documents_data = json.load(f)
        
        db.documents = {doc_id: Document.from_dict(doc_data) for doc_id, doc_data in documents_data.items()}
        
        # Load mappings
        with open(os.path.join(directory, "mappings.json"), "r") as f:
            mappings = json.load(f)
        
        db.id_to_index = mappings["id_to_index"]
        db.index_to_id = {int(k): v for k, v in mappings["index_to_id"].items()}  # Convert string keys back to int
        
        # Load index
        db.index = faiss.read_index(os.path.join(directory, "faiss_index.bin"))
        
        return db


class KeywordVectorDatabase(VectorDatabase):
    """Simple vector database with keyword search capabilities."""
    
    def __init__(self, dimension: int = 384):
        """
        Initialize the keyword vector database.
        
        Args:
            dimension: Dimension of the embedding vectors
        """
        super().__init__(dimension)
        self.documents: Dict[str, Document] = {}
    
    def add_document(self, document: Document) -> str:
        """
        Add a document to the database.
        
        Args:
            document: Document to add
            
        Returns:
            Document ID
        """
        self.documents[document.id] = document
        return document.id
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
        filter_func: Optional[Callable[[Document], bool]] = None
    ) -> List[Tuple[Document, float]]:
        """
        Search for similar documents using cosine similarity.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_func: Optional function to filter results
            
        Returns:
            List of (document, score) tuples
        """
        if not self.documents:
            logger.warning("Cannot search: database is empty")
            return []
        
        # Filter documents if needed
        docs_to_search = self.documents.values()
        if filter_func is not None:
            docs_to_search = [doc for doc in docs_to_search if filter_func(doc)]
        
        # Filter documents with embeddings
        docs_with_embeddings = [doc for doc in docs_to_search if doc.embedding is not None]
        
        if not docs_with_embeddings:
            logger.warning("No documents with embeddings to search")
            return []
        
        # Calculate cosine similarity for all documents
        results = []
        for doc in docs_with_embeddings:
            # Calculate cosine similarity
            dot_product = np.dot(query_embedding, doc.embedding)
            query_norm = np.linalg.norm(query_embedding)
            doc_norm = np.linalg.norm(doc.embedding)
            
            # Avoid division by zero
            if query_norm == 0 or doc_norm == 0:
                similarity = 0
            else:
                similarity = dot_product / (query_norm * doc_norm)
            
            results.append((doc, float(similarity)))
        
        # Sort by similarity in descending order
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Return top k results
        return results[:top_k]
    
    def delete_document(self, doc_id: str) -> bool:
        """
        Delete a document from the database.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            True if document was deleted, False otherwise
        """
        if doc_id in self.documents:
            del self.documents[doc_id]
            return True
        return False
    
    def get_document(self, doc_id: str) -> Optional[Document]:
        """
        Get a document by ID.
        
        Args:
            doc_id: Document ID to get
            
        Returns:
            Document if found, None otherwise
        """
        return self.documents.get(doc_id)
    
    def count_documents(self) -> int:
        """
        Get the number of documents in the database.
        
        Returns:
            Number of documents
        """
        return len(self.documents)
    
    def clear(self) -> None:
        """Clear all documents from the database."""
        self.documents = {}
    
    def save(self, directory: str) -> None:
        """
        Save the database to disk.
        
        Args:
            directory: Directory to save to
        """
        os.makedirs(directory, exist_ok=True)
        
        # Save documents
        documents_data = {doc_id: doc.to_dict() for doc_id, doc in self.documents.items()}
        with open(os.path.join(directory, "documents.json"), "w") as f:
            json.dump(documents_data, f)
        
        # Save metadata
        metadata = {
            "dimension": self.dimension,
            "document_count": len(self.documents)
        }
        with open(os.path.join(directory, "metadata.json"), "w") as f:
            json.dump(metadata, f)
    
    @classmethod
    def load(cls, directory: str) -> 'KeywordVectorDatabase':
        """
        Load a database from disk.
        
        Args:
            directory: Directory to load from
            
        Returns:
            Loaded KeywordVectorDatabase
        """
        # Load metadata
        with open(os.path.join(directory, "metadata.json"), "r") as f:
            metadata = json.load(f)
        
        # Create instance
        db = cls(dimension=metadata["dimension"])
        
        # Load documents
        with open(os.path.join(directory, "documents.json"), "r") as f:
            documents_data = json.load(f)
        
        db.documents = {doc_id: Document.from_dict(doc_data) for doc_id, doc_data in documents_data.items()}
        
        return db


# Factory function to create vector databases
def create_vector_database(
    db_type: str = "faiss",
    dimension: int = 384,
    **kwargs
) -> VectorDatabase:
    """
    Factory function to create a vector database.
    
    Args:
        db_type: Database type ('faiss', 'keyword')
        dimension: Dimension of the embedding vectors
        **kwargs: Additional arguments for the database
        
    Returns:
        A VectorDatabase instance
    """
    if db_type.lower() == "faiss":
        return FaissVectorDatabase(dimension=dimension, **kwargs)
    elif db_type.lower() == "keyword":
        return KeywordVectorDatabase(dimension=dimension)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")