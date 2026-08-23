"""
Integration of knowledge graph functionality into the Streamlit RAG application.
"""

import streamlit as st
import os
import logging
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt

from knowledge_graph.model import KnowledgeGraph
from knowledge_graph.extractor import KnowledgeGraphExtractor
from knowledge_graph.integration import RAGEnhancer
from knowledge_graph.streamlit_ui import add_knowledge_graph_ui, add_knowledge_graph_query_ui

# Configure logging
logger = logging.getLogger(__name__)


def setup_knowledge_graph(rag_engine):
    """
    Initialize the knowledge graph and RAG enhancer.
    
    Args:
        rag_engine: Existing RAG engine
        
    Returns:
        Tuple of (KnowledgeGraph, RAGEnhancer)
    """
    # Check if knowledge graph already exists in session state
    if "knowledge_graph" not in st.session_state:
        # Initialize RAG enhancer
        enhancer = RAGEnhancer(rag_engine)
        
        # Build knowledge graph from existing documents
        with st.spinner("Building knowledge graph from documents..."):
            enhancer.build_knowledge_graph()
        
        # Store in session state
        st.session_state.rag_enhancer = enhancer
        logger.info("Knowledge graph initialized")
        st.session_state.knowledge_graph = enhancer.get_knowledge_graph()
        logger.info("Knowledge graph stored in session state")
        
        # Log statistics
        stats = st.session_state.knowledge_graph.statistics()
        logger.info(f"Knowledge graph built with {stats['num_entities']} entities and {stats['num_relations']} relations")
    
    return st.session_state.knowledge_graph, st.session_state.rag_enhancer


def integrate_knowledge_graph_to_sidebar(rag_engine):
    """
    Add knowledge graph information to the sidebar.
    
    Args:
        rag_engine: Existing RAG engine
    """
    st.sidebar.markdown("---")
    st.sidebar.header("Knowledge Graph")
    
    # Initialize or retrieve knowledge graph
    kg, enhancer = setup_knowledge_graph(rag_engine)
    
    # Display stats
    stats = kg.statistics()
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Entities", stats["num_entities"])
    col2.metric("Relations", stats["num_relations"])
    
    # Add rebuild button
    if st.sidebar.button("Rebuild Knowledge Graph"):
        with st.spinner("Rebuilding knowledge graph..."):
            enhancer.build_knowledge_graph(reset=True)
            st.session_state.knowledge_graph = enhancer.get_knowledge_graph()
            logger.info("Knowledge graph rebuilt")
            logger.info(f"Knowledge graph summary: {enhancer.get_knowledge_graph().generate_summary()}")
            # Store knowledge graph in session state
        
            st.sidebar.success("Knowledge graph rebuilt!")
            # Force rerun to update metrics
            st.rerun()
    
    # Top entities section
    if stats["num_entities"] > 0:
        # Calculate centrality
        import networkx as nx
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


def add_knowledge_graph_page(rag_engine):
    """
    Add a knowledge graph visualization page to the Streamlit app.
    
    Args:
        rag_engine: Existing RAG engine
    """
    st.title("📊 Knowledge Graph Explorer")
    
    # Initialize or retrieve knowledge graph
    kg, enhancer = setup_knowledge_graph(rag_engine)
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Visualization", "Query", "Statistics"])
    
    with tab1:
        # Add knowledge graph visualization
        add_knowledge_graph_ui(kg)
    
    with tab2:
        # Add knowledge graph query interface
        add_knowledge_graph_query_ui(kg)
    
    with tab3:
        # Display detailed statistics
        st.header("Knowledge Graph Statistics")
        
        stats = kg.statistics()
        
        # Overall statistics
        st.subheader("Overview")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Entities", stats["num_entities"])
        col2.metric("Relations", stats["num_relations"])
        col3.metric("Entity Types", len(stats["entity_types"]))
        col4.metric("Relation Types", len(stats["relation_types"]))
        
        # Entity type breakdown
        if stats["entity_types"]:
            st.subheader("Entity Types")
            
            # Create a pie chart
            fig, ax = plt.subplots(figsize=(8, 6))
            labels = list(stats["entity_types"].keys())
            sizes = list(stats["entity_types"].values())
            
            # Sort by size
            sorted_data = sorted(zip(labels, sizes), key=lambda x: x[1], reverse=True)
            labels = [x[0] for x in sorted_data]
            sizes = [x[1] for x in sorted_data]
            
            # Use a threshold to group small slices as "Other"
            threshold = 0.03  # 3% threshold
            total = sum(sizes)
            
            if total > 0:
                small_indices = [i for i, size in enumerate(sizes) if size/total < threshold]
                
                if small_indices:
                    # Collect small slices
                    other_size = sum(sizes[i] for i in small_indices)
                    large_labels = [label for i, label in enumerate(labels) if i not in small_indices]
                    large_sizes = [size for i, size in enumerate(sizes) if i not in small_indices]
                    
                    # Add "Other" category
                    large_labels.append("Other")
                    large_sizes.append(other_size)
                    
                    ax.pie(large_sizes, labels=large_labels, autopct='%1.1f%%')
                else:
                    ax.pie(sizes, labels=labels, autopct='%1.1f%%')
                
                ax.axis('equal')
                st.pyplot(fig)
            
        # Relation type breakdown
        if stats["relation_types"]:
            st.subheader("Relation Types")
            
            # Create a horizontal bar chart
            fig, ax = plt.subplots(figsize=(10, len(stats["relation_types"]) * 0.4 + 2))
            
            # Sort by count
            sorted_items = sorted(stats["relation_types"].items(), key=lambda x: x[1], reverse=True)
            labels = [x[0] for x in sorted_items]
            values = [x[1] for x in sorted_items]
            
            y_pos = range(len(labels))
            ax.barh(y_pos, values)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels)
            ax.invert_yaxis()
            ax.set_xlabel('Count')
            plt.tight_layout()
            
            st.pyplot(fig)
        
        # Network metrics
        st.subheader("Network Metrics")
        
        col1, col2 = st.columns(2)
        
        import networkx as nx
        graph = kg.graph
        
        # Basic metrics
        col1.metric("Average Degree", f"{stats.get('average_degree', 0):.2f}")
        col1.metric("Connected", "Yes" if stats.get("is_connected", False) else "No")
        
        # Advanced metrics
        try:
            # Degree centrality
            centrality = nx.degree_centrality(graph)
            col2.metric("Avg. Centrality", f"{sum(centrality.values()) / max(1, len(centrality)):.4f}")
            
            # Clustering coefficient (only for undirected graphs)
            if len(kg.entities) > 1:
                clustering = nx.average_clustering(graph.to_undirected())
                col2.metric("Clustering Coefficient", f"{clustering:.4f}")
        except Exception as e:
            st.warning(f"Could not calculate some network metrics: {e}")
        
        # Top central entities
        st.subheader("Most Central Entities")
        
        try:
            # Calculate centrality
            centrality = nx.degree_centrality(graph)
            
            # Get top 10 entities
            top_entities = sorted(
                [(entity_id, kg.entities[entity_id].name, kg.entities[entity_id].type, centrality[entity_id]) 
                 for entity_id in centrality if entity_id in kg.entities],
                key=lambda x: x[3],
                reverse=True
            )[:10]
            
            # Create a table
            table_data = {
                "Entity": [name for _, name, _, _ in top_entities],
                "Type": [type for _, _, type, _ in top_entities],
                "Centrality": [f"{cent:.4f}" for _, _, _, cent in top_entities],
                "Connections": [len(list(graph.neighbors(entity_id))) for entity_id, _, _, _ in top_entities]
            }
            
            st.dataframe(table_data)
            
        except Exception as e:
            st.warning(f"Could not calculate entity centrality: {e}")


def enhanced_rag_generate_response(rag_enhancer, query, **kwargs):
    """
    Generate a response using the enhanced RAG system with knowledge graph.
    
    Args:
        rag_enhancer: RAG enhancer instance
        query: User query
        **kwargs: Additional parameters
        
    Returns:
        Response dictionary
    """
    return rag_enhancer.generate_response(query, **kwargs)


def enhance_search_ui(rag_engine):
    """
    Enhance the search UI with knowledge graph features.
    
    Args:
        rag_engine: Existing RAG engine
    """
    # Set up tabs
    mode_tabs = st.radio(
        "Search Mode:",
        ["Standard Search", "Knowledge Graph Enhanced"],
        horizontal=True,
        key="search_mode"
    )
    
    query = st.text_input("Enter your question:", key="query_input")
    
    if query:
        if mode_tabs == "Knowledge Graph Enhanced":
            # Use knowledge graph enhanced search
            kg, enhancer = setup_knowledge_graph(rag_engine)
            
            with st.spinner('Searching with knowledge graph enhancement...'):
                # Get query processor
                from knowledge_graph.query import KnowledgeGraphQueryProcessor
                processor = KnowledgeGraphQueryProcessor(kg)
                
                # Process query to see if it's a graph query
                graph_results = processor.process_query(query)
                
                if graph_results["type"] not in ["intent_only"]:
                    # Display graph query results
                    st.markdown("### Knowledge Graph Results")
                    
                    # Format results based on type
                    formatted_results = processor.format_graph_results(graph_results)
                    st.markdown(formatted_results)
                else:
                    # Use enhanced RAG
                    results = enhanced_rag_generate_response(enhancer, query)
                    
                    # Display response
                    st.markdown("### Answer")
                    st.write(results["response"])
                    
                    # Display sources
                    st.markdown("### Sources")
                    for i, doc in enumerate(results["retrieved_documents"]):
                        with st.expander(f"Source {i+1}"):
                            st.text_area("Content", doc["text"], height=150, key=f"text_area_{i}")

                            st.text(f"Relevance: {doc.get('score', 0):.2f}")
                            if "graph_score" in doc:
                                st.text(f"Graph Relevance: {doc.get('graph_score', 0):.2f}")
        else:
            # Use standard search
            with st.spinner('Searching for answer...'):
                # Call the regular RAG engine
                results = rag_engine.generate_response(query)
                
                # Display response
                st.markdown("### Answer")
                st.write(results["response"])
                
                # Display sources
                st.markdown("### Sources")
                for i, doc in enumerate(results["retrieved_documents"]):
                    with st.expander(f"Source {i+1}"):
                        st.text_area("Content", doc["text"], height=150, key=f"text_area_{i}")

                        st.text(f"Relevance: {doc.get('score', 0):.2f}")


def process_uploaded_document_with_kg(file, rag_enhancer, task_type=None, **kwargs):
    """
    Process an uploaded document with knowledge graph enhancement.
    
    Args:
        file: Uploaded file
        rag_enhancer: RAG enhancer instance
        **kwargs: Additional parameters
        
    Returns:
        Status message
    """
    import tempfile
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.name)[1]) as tmp_file:
        tmp_file.write(file.getvalue())
        tmp_file_path = tmp_file.name
    
    try:
        # Process document
        from document.processor import DocumentProcessor
        
        processor = DocumentProcessor(**kwargs)
        chunks, chunk_metadata = processor.process_file(
            tmp_file_path,
            metadata={"filename": file.name, "source": "UI upload"},
            task_type=task_type

        )
        
        if not chunks:
            return "No text could be extracted from the document."
        
        # Add to RAG enhancer (which adds to both RAG and knowledge graph)
        doc_ids = rag_enhancer.add_documents(chunks, chunk_metadata)
        
        return f"Added {len(chunks)} document chunks with knowledge graph enhancement!"
    except Exception as e:
        return f"Error processing document: {str(e)}"
    finally:
        # Clean up temporary file
        os.unlink(tmp_file_path)