"""
Main application entry point.
"""

import logging
import os
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
from config import get_logging_config
import logging.config
logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="RAG API System",
    description="API for RAG-based question answering",
    version="1.0.0"
)


# Initialize components
def initialize_components():
    """Initialize all system components."""
    logger.info("Initializing system components")
    
    # Create embedding model
    from embedding.model import create_embedding_model
    embedding_model = create_embedding_model()
    logger.info(f"Embedding model initialized with dimension {embedding_model.dimension}")
    
    # Create vector database
    from storage.vector_db import create_vector_database
    vector_db = create_vector_database(dimension=embedding_model.dimension)
    logger.info("Vector database initialized")
    
    # Create RAG engine
    from rag.engine import create_rag_engine
    rag_engine = create_rag_engine(
        embedder=embedding_model,
        vector_db=vector_db
    )
    logger.info("RAG engine initialized")
    
    return rag_engine

# Register API routes
def register_api_routes(app, rag_engine):
    """Register API routes."""
    from api.routes import RAGAPIRouter
    router = RAGAPIRouter(app, rag_engine)
    logger.info("API routes registered")

# Add health check route
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint returning basic system information."""
    return {
        "name": "RAG API System",
        "version": "1.0.0",
        "status": "running"
    }

# Main entry point
def main():
    """Main application entry point."""
    logger.info("Starting RAG API system")
    
    # Initialize components
    rag_engine = initialize_components()
    
    # Register API routes
    register_api_routes(app, rag_engine)
    
    # Run server if executed directly
    if __name__ == "__main__":
        host = os.getenv("API_HOST", "0.0.0.0")
        port = int(os.getenv("API_PORT", "8000"))
        
        logger.info(f"Starting server on http://{host}:{port}")
        uvicorn.run(app, host=host, port=port)
    
    return app

# Create and run application
app = main()
