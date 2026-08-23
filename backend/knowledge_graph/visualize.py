"""
Visualization utilities for knowledge graphs.
"""

import os
import json
import logging
from typing import Dict, Any, Optional

from .model import KnowledgeGraph

# Configure logging
logger = logging.getLogger(__name__)


def generate_html_visualization(
    knowledge_graph: KnowledgeGraph,
    output_path: str,
    title: str = "Knowledge Graph Visualization",
    width: int = 900,
    height: int = 600
) -> None:
    """
    Generate an interactive HTML visualization of a knowledge graph.
    
    Args:
        knowledge_graph: Knowledge graph to visualize
        output_path: Path to save HTML file
        title: Title for the visualization
        width: Width of the visualization in pixels
        height: Height of the visualization in pixels
    """
    # Generate graph data
    graph_data = get_graph_data(knowledge_graph)
    
    # Create HTML with D3.js visualization
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <title>{title}</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 0;
                padding: 0;
            }}
            #container {{
                width: 100%;
                height: 100vh;
                overflow: hidden;
            }}
            #graph {{
                width: 100%;
                height: 100%;
            }}
            .node {{
                stroke: #fff;
                stroke-width: 1.5px;
            }}
            .link {{
                stroke: #999;
                stroke-opacity: 0.6;
            }}
            .node-label {{
                font-size: 10px;
                pointer-events: none;
            }}
            .info-panel {{
                position: absolute;
                top: 10px;
                right: 10px;
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                width: 300px;
                max-height: 80vh;
                overflow-y: auto;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .info-panel h3 {{
                margin-top: 0;
            }}
            .info-panel p {{
                margin: 5px 0;
            }}
            .legend {{
                position: absolute;
                bottom: 10px;
                left: 10px;
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .legend-item {{
                display: flex;
                align-items: center;
                margin-bottom: 5px;
            }}
            .legend-color {{
                width: 15px;
                height: 15px;
                margin-right: 5px;
                border-radius: 50%;
            }}
            .search-box {{
                position: absolute;
                top: 10px;
                left: 10px;
                background-color: rgba(255, 255, 255, 0.9);
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 10px;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
            }}
            .search-input {{
                width: 200px;
                padding: 5px;
                border: 1px solid #ccc;
                border-radius: 3px;
            }}
        </style>
    </head>
    <body>
        <div id="container">
            <div id="graph"></div>
            <div class="search-box">
                <input type="text" id="search" class="search-input" placeholder="Search entities...">
            </div>
            <div id="info-panel" class="info-panel" style="display: none;">
                <h3 id="entity-name">Entity Name</h3>
                <p><strong>Type:</strong> <span id="entity-type">Type</span></p>
                <div id="entity-connections">
                    <h4>Connections:</h4>
                    <div id="connections-list"></div>
                </div>
            </div>
            <div class="legend" id="legend"></div>
        </div>
        
        <script>
        // Graph data
        const graphData = {json.dumps(graph_data)};
        
        // Set up the SVG and force simulation
        const width = {width};
        const height = {height};
        
        const svg = d3.select("#graph")
            .append("svg")
            .attr("width", "100%")
            .attr("height", "100%")
            .attr("viewBox", [0, 0, width, height]);
        
        // Create legend
        const entityTypes = [...new Set(graphData.nodes.map(d => d.type))];
        const legendContainer = d3.select("#legend");
        
        entityTypes.forEach(type => {{
            const color = graphData.nodes.find(d => d.type === type).color;
            const item = legendContainer.append("div")
                .attr("class", "legend-item");
            
            item.append("div")
                .attr("class", "legend-color")
                .style("background-color", color);
            
            item.append("span")
                .text(type);
        }});
        
        // Add zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 10])
            .on("zoom", (event) => {{
                g.attr("transform", event.transform);
            }});
        
        svg.call(zoom);
        
        const g = svg.append("g");
        
        // Add links
        const link = g.append("g")
            .selectAll("line")
            .data(graphData.links)
            .enter()
            .append("line")
            .attr("class", "link")
            .attr("stroke-width", d => Math.sqrt(d.value) * 1.5);
        
        // Add nodes
        const node = g.append("g")
            .selectAll("circle")
            .data(graphData.nodes)
            .enter()
            .append("circle")
            .attr("class", "node")
            .attr("r", d => d.size || 5)
            .attr("fill", d => d.color || "#999")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended));
        
        // Add node labels
        const label = g.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .enter()
            .append("text")
            .attr("class", "node-label")
            .attr("dx", 12)
            .attr("dy", ".35em")
            .text(d => d.name);
        
        // Set up force simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collide", d3.forceCollide().radius(30))
            .on("tick", ticked);
        
        // Node click event to show info panel
        node.on("click", function(event, d) {{
            showEntityInfo(d);
            event.stopPropagation();
        }});
        
        // Click on background to hide info panel
        svg.on("click", function() {{
            d3.select("#info-panel").style("display", "none");
        }});
        
        // Search functionality
        d3.select("#search").on("input", function() {{
            const searchTerm = this.value.toLowerCase();
            
            if (searchTerm === "") {{
                // Reset all nodes and links
                node.attr("opacity", 1);
                link.attr("opacity", 0.6);
                label.attr("opacity", 1);
                return;
            }}
            
            // Find matching nodes
            const matchingNodes = graphData.nodes.filter(n => 
                n.name.toLowerCase().includes(searchTerm)
            );
            
            const matchingNodeIds = new Set(matchingNodes.map(n => n.id));
            
            // Highlight matching nodes and connections
            node.attr("opacity", d => matchingNodeIds.has(d.id) ? 1 : 0.1);
            
            link.attr("opacity", d => 
                matchingNodeIds.has(d.source.id) || matchingNodeIds.has(d.target.id) ? 0.8 : 0.1
            );
            
            label.attr("opacity", d => matchingNodeIds.has(d.id) ? 1 : 0.1);
            
            // If exactly one match, show its info
            if (matchingNodes.length === 1) {{
                showEntityInfo(matchingNodes[0]);
            }}
        }});
        
        function ticked() {{
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
                
            label
                .attr("x", d => d.x)
                .attr("y", d => d.y);
        }}
        
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }}
        
        function dragged(event, d) {{
            d.fx = event.x;
            d.fy = event.y;
        }}
        
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }}
        
        function showEntityInfo(entity) {{
            // Get connections for this entity
            const connections = {{}};
            
            graphData.links.forEach(link => {{
                if (link.source.id === entity.id) {{
                    const targetNode = graphData.nodes.find(n => n.id === link.target.id);
                    if (!connections[link.type]) {{
                        connections[link.type] = [];
                    }}
                    connections[link.type].push(targetNode);
                }} else if (link.target.id === entity.id) {{
                    const sourceNode = graphData.nodes.find(n => n.id === link.source.id);
                    const reverseType = `incoming` + link.type;
                    if (!connections[reverseType]) {{
                        connections[reverseType] = [];
                    }}
                    connections[reverseType].push(sourceNode);
                }}
            }});
            
            // Update info panel
            d3.select("#entity-name").text(entity.name);
            d3.select("#entity-type").text(entity.type);
            
            const connectionsList = d3.select("#connections-list");
            connectionsList.html("");
            
            Object.keys(connections).forEach(type => {{
                const connectionSection = connectionsList.append("div");
                connectionSection.append("h5").text(type);
                
                const ul = connectionSection.append("ul");
                connections[type].forEach(connectedEntity => {{
                    ul.append("li")
                        .text(connectedEntity.name)
                        .style("cursor", "pointer")
                        .on("click", function() {{
                            showEntityInfo(connectedEntity);
                            event.stopPropagation();
                        }});
                }});
            }});
            
            d3.select("#info-panel").style("display", "block");
        }}
        </script>
    </body>
    </html>
    """
    
    # Write HTML to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    logger.info(f"Generated interactive visualization at {output_path}")


def get_graph_data(knowledge_graph: KnowledgeGraph) -> Dict[str, Any]:
    """
    Generate graph data for visualization.
    
    Args:
        knowledge_graph: Knowledge graph to visualize
        
    Returns:
        Dictionary with nodes and links for visualization
    """
    # Define colors for entity types
    node_colors = {
        "Person": "#4285F4",  # Blue
        "Organization": "#EA4335",  # Red
        "Location": "#FBBC05",  # Yellow
        "Concept": "#34A853",  # Green
        "Product": "#8F00FF",  # Purple
        "Event": "#FF6D01",  # Orange
        "WorkOfArt": "#00BCD4",  # Cyan
        "Other": "#9E9E9E"  # Gray
    }
    
    # Generate nodes
    nodes = []
    for entity_id, entity in knowledge_graph.entities.items():
        # Get node size based on connections
        size = 5
        try:
            neighbors = len(list(knowledge_graph.graph.neighbors(entity_id)))
            size = max(5, min(15, 5 + neighbors))
        except:
            pass
        
        color = node_colors.get(entity.type, node_colors["Other"])
        
        nodes.append({
            "id": entity_id,
            "name": entity.name,
            "type": entity.type,
            "color": color,
            "size": size
        })
    
    # Generate links
    links = []
    for relation_id, relation in knowledge_graph.relations.items():
        links.append({
            "source": relation.source,
            "target": relation.target,
            "type": relation.type,
            "value": relation.weight
        })
    
    return {
        "nodes": nodes,
        "links": links
    }


def generate_graph_statistics(knowledge_graph: KnowledgeGraph) -> Dict[str, Any]:
    """
    Generate statistics about the knowledge graph.
    
    Args:
        knowledge_graph: Knowledge graph to analyze
        
    Returns:
        Dictionary of statistics
    """
    import networkx as nx
    
    stats = knowledge_graph.statistics()
    
    # Add additional network metrics
    if knowledge_graph.entities:
        # Centrality measures
        try:
            # Degree centrality
            degree_centrality = nx.degree_centrality(knowledge_graph.graph)
            stats["avg_degree_centrality"] = sum(degree_centrality.values()) / len(degree_centrality)
            
            # Top entities by degree centrality
            top_central_entities = sorted(
                degree_centrality.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            stats["top_central_entities"] = [
                {
                    "id": entity_id,
                    "name": knowledge_graph.entities[entity_id].name if entity_id in knowledge_graph.entities else "Unknown",
                    "type": knowledge_graph.entities[entity_id].type if entity_id in knowledge_graph.entities else "Unknown",
                    "centrality": centrality
                }
                for entity_id, centrality in top_central_entities
            ]
            
            # Clustering coefficient
            if len(knowledge_graph.entities) > 1:
                stats["clustering_coefficient"] = nx.average_clustering(knowledge_graph.graph.to_undirected())
                
        except Exception as e:
            logger.warning(f"Error calculating network metrics: {e}")
    
    return stats


def save_graph_data_json(
    knowledge_graph: KnowledgeGraph,
    output_path: str
) -> None:
    """
    Save graph data to a JSON file for use in external visualization tools.
    
    Args:
        knowledge_graph: Knowledge graph to visualize
        output_path: Path to save JSON file
    """
    graph_data = get_graph_data(knowledge_graph)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)
    
    logger.info(f"Saved graph data to {output_path}")