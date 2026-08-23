"""
Streamlit UI integration for knowledge graph visualization.
"""

import streamlit as st
import os
import tempfile
import networkx as nx
import matplotlib.pyplot as plt
import base64
from io import BytesIO
import json
from typing import Dict, Any, Optional, List

from .model import KnowledgeGraph
from .visualize import get_graph_data, generate_html_visualization


def add_knowledge_graph_ui(kg: KnowledgeGraph, container=None):
    """
    Add knowledge graph visualization and exploration UI to a Streamlit app.
    
    Args:
        kg: Knowledge graph to visualize
        container: Optional container to render in (uses st directly if None)
    """
    # Use provided container or st directly
    ui = container or st
    
    # Get statistics
    stats = kg.statistics()
    
    ui.subheader("Knowledge Graph Explorer")
    
    # Show statistics
    ui.markdown("#### Graph Statistics")
    col1, col2, col3 = ui.columns(3)
    col1.metric("Entities", stats["num_entities"])
    col2.metric("Relations", stats["num_relations"])
    col3.metric("Entity Types", len(stats["entity_types"]))
    
    # Entity type breakdown
    if stats["entity_types"]:
        ui.markdown("#### Entity Types")
        
        # Create bar chart data
        types = list(stats["entity_types"].keys())
        counts = list(stats["entity_types"].values())
        
        # Plot using matplotlib
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(types, counts)
        ax.set_ylabel("Count")
        ax.set_title("Entity Types")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        
        ui.pyplot(fig)
    
    # Relation type breakdown
    if stats["relation_types"]:
        ui.markdown("#### Relation Types")
        
        # Create bar chart data
        types = list(stats["relation_types"].keys())
        counts = list(stats["relation_types"].values())
        
        # Plot using matplotlib
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(types, counts)
        ax.set_ylabel("Count")
        ax.set_title("Relation Types")
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        
        ui.pyplot(fig)
    
    # Interactive visualization
    ui.markdown("#### Interactive Visualization")
    
    # Create visualization
    if "knowledge_graph_html" not in st.session_state:
        # Generate visualization in a temporary file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
            generate_html_visualization(kg, temp_file.name)
            temp_path = temp_file.name
            
            # Read the HTML content
            with open(temp_path, "r", encoding="utf-8") as f:
                st.session_state.knowledge_graph_html = f.read()
            
            # Clean up
            os.unlink(temp_path)
    
    # Display the HTML visualization using an iframe
    ui.components.v1.html(st.session_state.knowledge_graph_html, height=600)
    
    # Entity search
    ui.markdown("#### Search Entities")
    
    search_term = ui.text_input("Search for entities:", key="kg_entity_search")
    
    if search_term:
        # Search for entities
        matching_entities = kg.search_entities(search_term)
        
        if matching_entities:
            ui.write(f"Found {len(matching_entities)} matching entities:")
            
            # Display entities in an expander
            for entity in matching_entities:
                with ui.expander(f"{entity.name} ({entity.type})"):
                    # Show entity details
                    ui.markdown(f"**ID:** {entity.id}")
                    ui.markdown(f"**Type:** {entity.type}")
                    
                    # Show metadata
                    if entity.metadata:
                        ui.markdown("**Metadata:**")
                        for key, value in entity.metadata.items():
                            if key not in ["source_text", "start_char", "end_char"]:
                                ui.markdown(f"- **{key}:** {value}")
                    
                    # Show connections
                    connections = kg.get_entity_connections(entity.id)
                    if connections:
                        ui.markdown("**Connections:**")
                        for relation_type, neighbors in connections.items():
                            ui.markdown(f"- **{relation_type}:** {', '.join([n.name for n, _ in neighbors])}")
        else:
            ui.info("No matching entities found.")
    
    # Path finding
    ui.markdown("#### Find Paths Between Entities")
    
    col1, col2 = ui.columns(2)
    
    # Get all entity names for dropdowns
    entity_names = [(entity.id, f"{entity.name} ({entity.type})") for entity in kg.entities.values()]
    entity_names.sort(key=lambda x: x[1])
    
    source_options = [""] + [name for _, name in entity_names]
    target_options = [""] + [name for _, name in entity_names]
    
    source_idx = col1.selectbox("Source Entity:", source_options, key="kg_source_entity")
    target_idx = col2.selectbox("Target Entity:", target_options, key="kg_target_entity")
    
    if source_idx and target_idx and source_idx != target_idx:
        # Get entity IDs
        source_id = entity_names[source_options.index(source_idx) - 1][0]
        target_id = entity_names[target_options.index(target_idx) - 1][0]
        
        # Find paths
        paths = kg.find_path(source_id, target_id, max_hops=3)
        
        if paths:
            ui.success(f"Found {len(paths)} paths between entities!")
            
            for i, path in enumerate(paths):
                with ui.expander(f"Path {i+1} ({len(path)} steps)"):
                    for j, (entity, relation) in enumerate(path):
                        if j > 0:
                            ui.markdown(f"↓ **{relation.type}** ↓")
                        
                        ui.markdown(f"**{entity.name}** ({entity.type})")
        else:
            ui.error("No paths found between these entities")
    
    # Create export options
    ui.markdown("#### Export Knowledge Graph")
    
    col1, col2 = ui.columns(2)
    
    # Export as JSON
    if col1.button("Export as JSON"):
        # Convert to JSON
        graph_data = get_graph_data(kg)
        
        # Create download link
        json_str = json.dumps(graph_data, indent=2)
        b64 = base64.b64encode(json_str.encode()).decode()
        href = f'<a href="data:application/json;base64,{b64}" download="knowledge_graph.json">Download JSON</a>'
        ui.markdown(href, unsafe_allow_html=True)
    
    # Export as HTML visualization
    if col2.button("Export Interactive Visualization"):
        # Create an HTML file
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as temp_file:
            generate_html_visualization(kg, temp_file.name)
            
            # Read file content
            with open(temp_file.name, "rb") as f:
                html_content = f.read()
            
            # Clean up
            os.unlink(temp_file.name)
            
            # Create download link
            b64 = base64.b64encode(html_content).decode()
            href = f'<a href="data:text/html;base64,{b64}" download="knowledge_graph_visualization.html">Download HTML Visualization</a>'
            ui.markdown(href, unsafe_allow_html=True)


def create_knowledge_graph_tab(kg: KnowledgeGraph):
    """
    Create a complete knowledge graph tab for a Streamlit application.
    
    Args:
        kg: Knowledge graph to display
        
    Returns:
        Tab content function
    """
    def _tab_content():
        add_knowledge_graph_ui(kg)
    
    return _tab_content


def add_knowledge_graph_query_ui(kg: KnowledgeGraph, container=None):
    """
    Add knowledge graph query UI to a Streamlit app.
    
    Args:
        kg: Knowledge graph to query
        container: Optional container to render in (uses st directly if None)
    """
    from .query import KnowledgeGraphQueryProcessor
    
    # Use provided container or st directly
    ui = container or st
    
    ui.subheader("Knowledge Graph Query")
    
    # Create query processor
    processor = KnowledgeGraphQueryProcessor(kg)
    
    # Query input
    query = ui.text_input("Enter your question:", placeholder="e.g., What is RAG?", key="kg_query_input")
    
    if query:
        ui.markdown("### Results")
        
        # Process query
        with ui.spinner("Processing query..."):
            results = processor.process_query(query)
            
            # Display results
            if results["type"] == "entity_results":
                entity = results["entity"]
                ui.markdown(f"#### Information about {entity['name']} ({entity['type']})")
                
                # Show metadata
                if entity['metadata']:
                    ui.markdown("**Properties:**")
                    for key, value in entity['metadata'].items():
                        if key not in ["source_text", "start_char", "end_char"]:
                            ui.markdown(f"- **{key}:** {value}")
                
                # Show connections
                if results["connections"]:
                    ui.markdown("**Connections:**")
                    for relation_type, neighbors in results["connections"].items():
                        ui.markdown(f"- **{relation_type}:** {', '.join([n['name'] for n in neighbors])}")
                        
            elif results["type"] == "relation_results":
                query_info = results["query"]
                count = results["count"]
                
                ui.markdown(f"#### Found {count} {query_info['relation']} for {query_info['entity_name']}")
                
                # Show results
                for item in results["results"]:
                    ui.markdown(f"- **{item['name']}** ({item['type']}): {item['relation']}")
                    
            elif results["type"] == "path_results":
                query_info = results["query"]
                count = results["count"]
                
                ui.markdown(f"#### Found {count} connection paths between {query_info['source_name']} and {query_info['target_name']}")
                
                # Show paths
                for i, path in enumerate(results["paths"]):
                    with ui.expander(f"Path {i+1}"):
                        for j, step in enumerate(path):
                            entity = step["entity"]
                            relation = step.get("relation")
                            
                            if j > 0 and relation:
                                ui.markdown(f"↓ **{relation['type']}** ↓")
                                
                            ui.markdown(f"**{entity['name']}** ({entity['type']})")
                            
            else:  # Intent only
                intent = results["intent"]
                expanded_query = results.get("expanded_query", query)
                
                ui.write("No direct knowledge graph answer found. Using RAG system instead.")
                
                # Show intent information
                ui.markdown("**Query Intent Analysis:**")
                ui.markdown(f"- **Type:** {intent['type']}")
                
                if intent['entities']:
                    ui.markdown(f"- **Entities mentioned:** {', '.join([e['name'] for e in intent['entities']])}")
                
                if expanded_query != query:
                    ui.markdown(f"- **Expanded query:** {expanded_query}")