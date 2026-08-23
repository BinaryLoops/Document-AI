"""
Integration of Knowledge Graph functionality with the main Streamlit application.
"""

import os
import sys
import streamlit as st
import logging
from typing import List, Dict, Any, Optional
import tempfile

# Configure logging
logger = logging.getLogger(__name__)

# Check if running in Streamlit Cloud
import os
import sys
import streamlit as st

# Flag for cloud environment
is_cloud_environment = "STREAMLIT_SHARING_MODE" in os.environ or "STREAMLIT_SERVER_BASE_URL_IS_SET" in os.environ

def is_neo4j_configured():
    """Check if Neo4j is configured in the environment."""
    if hasattr(st, "secrets") and "NEO4J_URI" in st.secrets:
        return True
    return "NEO4J_URI" in os.environ and os.environ.get("NEO4J_ENABLED", "false").lower() in ("true", "1", "t", "yes")

def register_knowledge_graph_pages():
    """Register Knowledge Graph pages with the main Streamlit application."""
    # Check if knowledge graph module is available
    try:
        from knowledge_graph.model import KnowledgeGraph
        from knowledge_graph.integration import RAGEnhancer
        return True
    except ImportError:
        logger.warning("Knowledge Graph module not available")
        return False

def get_or_create_knowledge_graph(rag_engine):
    """
    Get or create a knowledge graph for the current session.
    
    Args:
        rag_engine: RAG engine instance
        
    Returns:
        Tuple of (knowledge_graph, rag_enhancer)
    """
    # Initialize RAG enhancer if not already in session state
    if "rag_enhancer" not in st.session_state:
        from knowledge_graph.integration import RAGEnhancer
        
        enhancer = RAGEnhancer(rag_engine)
        
        # Check if there are documents to process
        if rag_engine.count_documents() > 0:
            with st.spinner("Building knowledge graph from documents..."):
                enhancer.build_knowledge_graph()
        
        st.session_state.rag_enhancer = enhancer
    
    # Get knowledge graph from enhancer
    enhancer = st.session_state.rag_enhancer
    knowledge_graph = enhancer.get_knowledge_graph()
    
    return knowledge_graph, enhancer

def add_knowledge_graph_to_sidebar(rag_engine):
    """
    Add Knowledge Graph information to the sidebar.
    
    Args:
        rag_engine: RAG engine instance
    """
    st.sidebar.markdown("---")
    st.sidebar.header("Knowledge Graph")
    
    kg, enhancer = get_or_create_knowledge_graph(rag_engine)
    
    # Check if Neo4j integration is enabled
    try:
        from knowledge_graph.config import get_neo4j_config
        neo4j_config = get_neo4j_config()

        # Add connection test button
        if "neo4j_integration" in st.session_state:
            if st.button("Test Neo4j Connection"):
                integration = st.session_state.neo4j_integration
                if integration.connect():
                    st.success("Connected to Neo4j successfully! ✅")
                else:
                    st.error("Failed to connect to Neo4j. Please check your connection settings. ❌")
        
        if neo4j_config["enabled"]:
            from knowledge_graph.neo4j_integration import Neo4jIntegration
            
            if "neo4j_integration" not in st.session_state:
                integration = Neo4jIntegration(kg)
                st.session_state.neo4j_integration = integration
            else:
                integration = st.session_state.neo4j_integration
            
            # Display Neo4j connection status
            connected = integration.connect()
            
            if connected:
                st.sidebar.success("Neo4j Connected ✓")
                
                # Add sync buttons
                col1, col2 = st.sidebar.columns(2)
                if col1.button("Sync to Neo4j"):
                    with st.spinner("Syncing to Neo4j..."):
                        success = integration.sync_to_neo4j()
                        if success:
                            st.sidebar.success("Sync successful!")
                        else:
                            st.sidebar.error("Sync failed!")
                
                if col2.button("Sync from Neo4j"):
                    with st.spinner("Syncing from Neo4j..."):
                        success = integration.sync_from_neo4j()
                        if success:
                            # Update the knowledge graph in session state
                            st.session_state.rag_enhancer.knowledge_graph = integration.knowledge_graph
                            st.sidebar.success("Sync successful!")
                            # Force rerun to update UI
                            st.rerun()
                        else:
                            st.sidebar.error("Sync failed!")
            else:
                st.sidebar.error("Neo4j Not Connected ✗")
                st.sidebar.markdown("Check connection settings in the Knowledge Graph settings tab.")
                
    except ImportError:
        # Neo4j integration not available
        pass
    
    # Display KG stats
    stats = kg.statistics()
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Entities", stats["num_entities"])
    col2.metric("Relations", stats["num_relations"])
    
    # Add rebuild button
    if st.sidebar.button("Rebuild Knowledge Graph"):
        with st.spinner("Rebuilding knowledge graph..."):
            enhancer.build_knowledge_graph(reset=True)
            st.sidebar.success("Knowledge graph rebuilt!")
            # Force rerun to update metrics
            st.rerun()
    
    # Top entities section
    if stats["num_entities"] > 0:
        # Calculate centrality
        import networkx as nx
        try:
            centrality = nx.degree_centrality(kg.graph)
            
            # Find top entities
            top_entities = sorted(
                [(entity_id, entity.name, centrality.get(entity_id, 0)) 
                 for entity_id, entity in kg.entities.items()],
                key=lambda x: x[2],
                reverse=True
            )[:5]
            
            if top_entities:
                st.sidebar.markdown("#### Key Concepts")
                for _, name, cent in top_entities:
                    st.sidebar.markdown(f"- {name}")
        except Exception as e:
            logger.error(f"Error calculating centrality: {e}")

def create_knowledge_graph_tab(rag_engine, tab):
    """
    Create the Knowledge Graph visualization tab.
    
    Args:
        rag_engine: RAG engine instance
        tab: Streamlit tab to render in
    """
    tab.title("📊 Knowledge Graph Explorer")
    
    kg, enhancer = get_or_create_knowledge_graph(rag_engine)
    
    # Add visualization
    from knowledge_graph.streamlit_ui import add_knowledge_graph_ui
    add_knowledge_graph_ui(kg, tab)
    
    # Neo4j settings section
    tab.markdown("---")
    tab.header("Neo4j Database Settings")
    
    try:
        from knowledge_graph.config import get_neo4j_config
        
        # Get current config
        neo4j_config = get_neo4j_config()
        
        # Create settings form
        with tab.form("neo4j_settings"):
            enable_neo4j = st.checkbox("Enable Neo4j Integration", value=neo4j_config["enabled"])
            neo4j_uri = st.text_input("Neo4j URI", value=neo4j_config["uri"])
            neo4j_username = st.text_input("Neo4j Username", value=neo4j_config["username"])
            neo4j_password = st.text_input("Neo4j Password", value=neo4j_config["password"], type="password")
            neo4j_database = st.text_input("Neo4j Database", value=neo4j_config["database"])
            
            if st.form_submit_button("Save Settings"):
                # Save settings to environment variables
                os.environ["NEO4J_ENABLED"] = str(enable_neo4j).lower()
                os.environ["NEO4J_URI"] = neo4j_uri
                os.environ["NEO4J_USERNAME"] = neo4j_username
                os.environ["NEO4J_PASSWORD"] = neo4j_password
                os.environ["NEO4J_DATABASE"] = neo4j_database
                
                # Force refresh of Neo4j integration
                if "neo4j_integration" in st.session_state:
                    del st.session_state.neo4j_integration
                
                st.success("Settings saved!")
                
    except ImportError:
        tab.warning("Neo4j integration not available. Please install the neo4j Python package.")

def create_knowledge_graph_query_tab(rag_engine, tab):
    """
    Create the Knowledge Graph query tab.
    
    Args:
        rag_engine: RAG engine instance
        tab: Streamlit tab to render in
    """
    tab.title("🔍 Knowledge Graph Query")
    
    kg, enhancer = get_or_create_knowledge_graph(rag_engine)
    
    # Add query UI
    from knowledge_graph.streamlit_ui import add_knowledge_graph_query_ui
    add_knowledge_graph_query_ui(kg, tab)

def enhance_search_with_knowledge_graph(query, rag_engine, search_params=None):
    """
    Enhance search results using the knowledge graph.
    
    Args:
        query: User query
        rag_engine: RAG engine instance
        search_params: Optional search parameters
        
    Returns:
        Enhanced search results
    """
    # Get or create knowledge graph and enhancer
    _, enhancer = get_or_create_knowledge_graph(rag_engine)
    
    # Use search parameters if provided
    if search_params is None:
        search_params = {}
    
    # Generate response with knowledge graph enhancement
    return enhancer.generate_response(query, **search_params)

def process_document_with_knowledge_graph(file, rag_engine, params=None):
    """
    Process a document with knowledge graph enhancement.
    
    Args:
        file: Uploaded file
        rag_engine: RAG engine instance
        params: Optional processing parameters
        
    Returns:
        Processing result message
    """
    # Get or create knowledge graph and enhancer
    _, enhancer = get_or_create_knowledge_graph(rag_engine)
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_file_path = tmp_file.name
    
    try:
        # Process document
        from document.processor import DocumentProcessor
        
        # Use parameters if provided
        processor_params = params or {}
        
        processor = DocumentProcessor(**processor_params)
        chunks, chunk_metadata = processor.process_file(
            tmp_file_path,
            metadata={"filename": file.name, "source": "UI upload"},
            task_type=processor_params.get("task_type")
        )
        
        if not chunks:
            return "No text could be extracted from the document."
        
        # Add to RAG enhancer (which adds to both RAG and knowledge graph)
        doc_ids = enhancer.add_documents(chunks, chunk_metadata)
        
        return f"Added {len(chunks)} document chunks with knowledge graph enhancement!"
    except Exception as e:
        return f"Error processing document: {str(e)}"
    finally:
        # Clean up temporary file
        os.unlink(tmp_file_path)

def integrate_with_streamlit_app():
    """
    Main function to integrate knowledge graph functionality with the Streamlit app.
    
    This is called from the main Streamlit app to add knowledge graph functionality.
    """
    # Register pages
    if not register_knowledge_graph_pages():
        return False
    
    return True

def modify_streamlit_app(app_file_path):
    """
    Modify the main Streamlit app to include knowledge graph functionality.
    
    Args:
        app_file_path: Path to the main Streamlit app file
        
    Returns:
        Whether modification was successful
    """
    # Read the app file
    try:
        with open(app_file_path, 'r') as f:
            app_code = f.read()
        
        # Check if already modified
        if "knowledge_graph_integration" in app_code:
            logger.info("App already modified for knowledge graph")
            return True
        
        # Modify imports
        import_section = "import streamlit as st\n"
        new_import = import_section + "import knowledge_graph_integration\n"
        app_code = app_code.replace(import_section, new_import)
        
        # Add knowledge graph tab
        tabs_line = "tabs = st.tabs([\"Search\", \"Upload\"])"
        new_tabs_line = "tabs = st.tabs([\"Search\", \"Upload\", \"Knowledge Graph\", \"KG Query\"])"
        app_code = app_code.replace(tabs_line, new_tabs_line)
        
        # Add knowledge graph tab content
        upload_tab_section = "with tabs[1]:"
        kg_tab_section = """
    # Knowledge Graph tab
    with tabs[2]:
        knowledge_graph_integration.create_knowledge_graph_tab(rag_engine, st)
    
    # Knowledge Graph Query tab
    with tabs[3]:
        knowledge_graph_integration.create_knowledge_graph_query_tab(rag_engine, st)
    """
        # Find the end of the upload tab section
        end_upload_section_idx = app_code.find("with tabs[2]:")
        if end_upload_section_idx == -1:
            # If not found, add after the last tab
            end_upload_section_idx = app_code.find(upload_tab_section)
            end_upload_section_idx = app_code.find("\n\n", end_upload_section_idx)
        
        # Insert knowledge graph tabs
        if end_upload_section_idx != -1:
            app_code = app_code[:end_upload_section_idx] + kg_tab_section + app_code[end_upload_section_idx:]
        
        # Add sidebar integration
        sidebar_section = "st.sidebar.metric(\"Documents Stored\", rag_engine.count_documents())"
        new_sidebar_section = sidebar_section + "\n    # Add knowledge graph to sidebar\n    knowledge_graph_integration.add_knowledge_graph_to_sidebar(rag_engine)"
        app_code = app_code.replace(sidebar_section, new_sidebar_section)
        
        # Enhance search
        search_section = "result = rag_engine.generate_response("
        new_search_section = "# Use knowledge graph enhanced search if enabled\n            result = knowledge_graph_integration.enhance_search_with_knowledge_graph("
        app_code = app_code.replace(search_section, new_search_section)
        
        # Save modified app
        with open(app_file_path, 'w') as f:
            f.write(app_code)
        
        logger.info(f"Successfully modified {app_file_path} to include knowledge graph functionality")
        return True
        
    except Exception as e:
        logger.error(f"Error modifying Streamlit app: {e}")
        return False

if __name__ == "__main__":
    # This allows running as a standalone script to modify the main app
    if len(sys.argv) > 1:
        app_path = sys.argv[1]
        if os.path.exists(app_path):
            modify_streamlit_app(app_path)
        else:
            print(f"App file not found: {app_path}")
    else:
        print("Usage: python knowledge_graph_integration.py path/to/streamlit-app.py")