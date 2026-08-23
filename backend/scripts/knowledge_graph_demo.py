"""
Knowledge Graph enhanced RAG system demo.
"""

import os
import sys
import streamlit as st
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main application."""
    # Set page config
    st.set_page_config(
        page_title="Knowledge Graph RAG System",
        page_icon="📚",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Create tabs for different functionality
    st.title("📚 Knowledge Graph Enhanced RAG System")
    tabs = st.tabs(["Search", "Upload", "Knowledge Graph", "Settings"])
    
    # Initialize RAG engine and knowledge graph
    rag_engine = initialize_rag_components()
    
    # Import knowledge graph integration
    from streamlit_kg_integration import (
        setup_knowledge_graph,
        integrate_knowledge_graph_to_sidebar,
        enhance_search_ui,
        add_knowledge_graph_page,
        process_uploaded_document_with_kg
    )
    
    # Add knowledge graph info to sidebar
    integrate_knowledge_graph_to_sidebar(rag_engine)
    
    # Initialize or retrieve knowledge graph components
    kg, enhancer = setup_knowledge_graph(rag_engine)
    
    # Add document count to sidebar
    document_count = rag_engine.count_documents()
    st.sidebar.metric("Documents Stored", document_count)
    
    # Search tab
    with tabs[0]:
        st.header("Ask a Question")
        enhance_search_ui(rag_engine)
    
    # Upload tab
    with tabs[1]:
        st.header("Upload Documents")
        
        # Upload settings
        col1, col2 = st.columns(2)
        
        with col1:
            chunking_mode = st.selectbox(
                "Chunking Method",
                options=["auto", "paragraph", "sentence", "character"],
                index=0
            )
            
        with col2:
            chunk_size = st.slider(
                "Chunk Size",
                min_value=500,
                max_value=5000,
                value=2000,
                step=500
            )
        
        chunk_overlap = st.slider(
            "Chunk Overlap",
            min_value=0,
            max_value=500,
            value=200,
            step=50
        )
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a document file (PDF, TXT, DOCX)",
            type=["pdf", "txt", "md", "docx"]
        )
        
        # Process uploaded file
        if uploaded_file is not None:
            with st.spinner('Processing document with knowledge graph enhancement...'):
                # Process with knowledge graph enhancement
                result = process_uploaded_document_with_kg(
                    uploaded_file, 
                    enhancer,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap,
                    chunking_mode=chunking_mode,
                    task_type="summary"
                )
                
                # Show result
                st.success(result)
                
                # Update document count
                st.session_state.document_count = rag_engine.count_documents()
                
                # Show knowledge graph stats update
                kg_stats = kg.statistics()
                st.info(f"Knowledge graph now has {kg_stats['num_entities']} entities and {kg_stats['num_relations']} relations")
    
    # Knowledge Graph tab
    with tabs[2]:
        add_knowledge_graph_page(rag_engine)
    
    # Settings tab
    with tabs[3]:
        st.header("System Settings")
        
        # Knowledge graph settings
        st.subheader("Knowledge Graph Settings")
        
        # Toggle settings
        use_query_expansion = st.checkbox("Use Knowledge Graph for Query Expansion", value=True)
        use_results_ranking = st.checkbox("Use Knowledge Graph for Results Ranking", value=True)
        
        # NLP model settings
        st.subheader("NLP Model Settings")
        
        spacy_model = st.selectbox(
            "spaCy Model",
            options=["en_core_web_sm", "en_core_web_md", "en_core_web_lg"],
            index=0
        )
        
        # Save settings
        if st.button("Save Settings"):
            # Update enhancer settings
            if hasattr(enhancer, "retrieval_enhancer") and enhancer.retrieval_enhancer:
                enhancer.retrieval_enhancer.use_for_query_expansion = use_query_expansion
                enhancer.retrieval_enhancer.use_for_results_ranking = use_results_ranking
                
                st.success("Settings saved!")
        
        # Reset knowledge graph
        st.subheader("Reset Knowledge Graph")
        
        if st.button("Reset Knowledge Graph", type="primary"):
            # Confirm
            if st.checkbox("Confirm reset (this will delete all knowledge graph data)"):
                # Reset knowledge graph
                enhancer.knowledge_graph.clear()
                
                # Rebuild with current documents
                with st.spinner("Rebuilding knowledge graph..."):
                    enhancer.build_knowledge_graph(reset=True)
                
                st.success("Knowledge graph reset and rebuilt!")
                
                # Force rerun to update stats
                st.rerun()


def initialize_rag_components():
    """
    Initialize RAG components.
    
    Returns:
        RAG engine instance
    """
    # Check if we have already initialized the components
    if "rag_engine" in st.session_state:
        return st.session_state.rag_engine
    
    # Initialize components
    try:
        from embedding.model import create_embedding_model
        from storage.vector_db import create_vector_database
        from rag.engine import create_rag_engine
        
        # Create embedding model
        embedding_model = create_embedding_model()
        
        # Create vector database 
        vector_db = create_vector_database(dimension=embedding_model.dimension)
        
        # Create RAG engine
        rag_engine = create_rag_engine(
            embedder=embedding_model,
            vector_db=vector_db
        )
        
        # Store in session state
        st.session_state.rag_engine = rag_engine
        
        return rag_engine
        
    except Exception as e:
        st.error(f"Error initializing RAG components: {e}")
        # Add debugging info
        st.exception(e)
        return None


if __name__ == "__main__":
    main()