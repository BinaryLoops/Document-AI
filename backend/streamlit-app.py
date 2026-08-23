"""
Streamlit UI for the RAG system with Knowledge Graph integration.
"""

import os
import sys
import streamlit as st
import tempfile
import logging
from dotenv import load_dotenv


# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

# Configure logging
from config import HUGGINGFACE_MODEL, get_logging_config
import logging.config
logging.config.dictConfig(get_logging_config())
logger = logging.getLogger(__name__)

# Import RAG and Knowledge Graph Integrations
from streamlit_kg_integration import (
    setup_knowledge_graph,
    integrate_knowledge_graph_to_sidebar,
    enhance_search_ui,
    process_uploaded_document_with_kg,
    add_knowledge_graph_page
)
from rag.engine import create_rag_engine
from embedding.model import create_embedding_model
from storage.vector_db import create_vector_database
from llm.model import create_llm

# Set page config
st.set_page_config(
    page_title="RAG + Knowledge Graph System",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded"
)


# Add spaCy model download for cloud deployment
@st.cache_resource
def load_spacy_model():
    try:
        import spacy
        return spacy.load("en_core_web_sm")
    except OSError:
        import spacy.cli
        spacy.cli.download("en_core_web_sm")
        return spacy.load("en_core_web_sm")

# Load spaCy model to ensure it's available
_ = load_spacy_model()
# Initialize session state
if "document_count" not in st.session_state:
    st.session_state.document_count = 0
if "initialized" not in st.session_state:
    st.session_state.initialized = False
if "last_question" not in st.session_state:
    st.session_state.last_question = ""

# Initialize RAG engine and Knowledge Graph
@st.cache_resource
def initialize_rag_kg_engine():
    embedding_model = create_embedding_model()
    vector_db = create_vector_database(dimension=embedding_model.dimension)
    llm = create_llm(model_type="local")
    rag_engine = create_rag_engine(embedder=embedding_model, vector_db=vector_db, llm=llm)
    
    # Initialize Knowledge Graph
    kg, enhancer = setup_knowledge_graph(rag_engine)
    
    st.session_state.initialized = True
    return rag_engine, kg, enhancer

# Main application
def main():
    """Main Streamlit application."""
    rag_engine, knowledge_graph, enhancer = initialize_rag_kg_engine()
    
    # Update document count
    st.session_state.document_count = rag_engine.count_documents()
    
    # Sidebar
    st.sidebar.title("📚 RAG + Knowledge Graph")
    integrate_knowledge_graph_to_sidebar(rag_engine)
    
    # Main tabs
    tabs = st.tabs(["Search", "Upload", "Knowledge Graph", "Documents", "Settings"])
    
    # Search tab
    with tabs[0]:
        st.header("Ask a Question")
        enhance_search_ui(rag_engine)
    
    # Upload tab
    with tabs[1]:
        st.header("Upload Documents")
        col1, col2 = st.columns(2)
        with col1:
            chunking_mode = st.selectbox("Chunking Method", options=["auto", "paragraph", "sentence", "character"], index=0)
        with col2:
            chunk_size = st.slider("Chunk Size", min_value=500, max_value=5000, value=2000, step=500)
        chunk_overlap = st.slider("Chunk Overlap", min_value=0, max_value=500, value=200, step=50)
        
        uploaded_file = st.file_uploader("Choose a document file", type=["pdf", "txt", "docx", "md"])
        
        if uploaded_file is not None:
            with st.spinner('Processing document with knowledge graph enhancement...'):
                result = process_uploaded_document_with_kg(uploaded_file, enhancer, chunk_size=chunk_size, chunk_overlap=chunk_overlap, chunking_mode=chunking_mode, task_type="summary")
                st.success(result)
                st.session_state.document_count = rag_engine.count_documents()
                kg_stats = knowledge_graph.statistics()
                st.info(f"Knowledge graph now has {kg_stats['num_entities']} entities and {kg_stats['num_relations']} relations")
    
    # Knowledge Graph Explorer tab
    with tabs[2]:
        add_knowledge_graph_page(rag_engine)
    
    # Documents tab (Restored functionality)
    with tabs[3]:
        st.header("📂 Document Management")
        doc_list = getattr(rag_engine, 'list_documents', lambda: None)()
        if doc_list is None:
            st.warning("Document listing is not supported in this version of RAGEngine.")
            doc_list = []
        if doc_list:
            for doc in doc_list:
                st.markdown(f"**{doc['name']}** ({doc['size']} KB)")
                if st.button(f"Delete {doc['name']}", key=f"del_{doc['id']}"):
                    rag_engine.delete_document(doc['id'])
                    st.rerun()
        else:
            st.info("No documents uploaded yet.")
    
    # Settings tab
    with tabs[4]:
        st.header("System Settings")
        use_query_expansion = st.checkbox("Use Knowledge Graph for Query Expansion", value=True)
        use_results_ranking = st.checkbox("Use Knowledge Graph for Results Ranking", value=True)
        spacy_model = st.selectbox("spaCy Model", options=["en_core_web_sm", "en_core_web_md", "en_core_web_lg"], index=0)
        
        if st.button("Save Settings"):
            enhancer.retrieval_enhancer.use_for_query_expansion = use_query_expansion
            enhancer.retrieval_enhancer.use_for_results_ranking = use_results_ranking
            st.success("Settings saved!")
        
        # Reset Knowledge Graph
        st.subheader("Reset Knowledge Graph")
        if st.button("Reset Knowledge Graph", type="primary"):
            if st.checkbox("Confirm reset (this will delete all knowledge graph data)"):
                enhancer.knowledge_graph.clear()
                with st.spinner("Rebuilding knowledge graph..."):
                    enhancer.build_knowledge_graph(reset=True)
                st.success("Knowledge graph reset and rebuilt!")
                st.rerun()
    
if __name__ == "__main__":
    main()
