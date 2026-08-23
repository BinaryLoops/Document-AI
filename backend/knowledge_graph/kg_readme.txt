# Knowledge Graph Integration with Neo4j

This document explains how to use the Knowledge Graph feature with Neo4j integration in the RAG Document QA System.

## Overview

The Knowledge Graph component enhances the RAG system by:

1. Automatically extracting entities and relationships from documents
2. Building a graph representation of document relationships
3. Enhancing query expansion and document retrieval
4. Visualizing relationships between document concepts
5. Persisting the graph structure in a Neo4j database

## Features

- **Entity and Relationship Extraction**: Identifies key entities and their relationships in documents
- **Graph-Based Query Enhancement**: Expands queries with related concepts from the graph
- **Graph Visualization**: Interactive graph visualization of document concepts
- **Neo4j Integration**: Persistent storage of graph in Neo4j database
- **Graph Querying**: Query the knowledge graph directly for insights

## Installation

### Prerequisites

- Neo4j Database (optional, for persistent storage)
- Python 3.8+

### Installation Steps

1. Run the installation script:

```bash
python install_neo4j_integration.py
```

For more options:

```bash
python install_neo4j_integration.py --help
```

2. To configure Neo4j connection:

```bash
python install_neo4j_integration.py --uri bolt://localhost:7687 --username neo4j --password your_password --enable --test-connection
```

### Manual Installation

If you prefer to install manually, add the following to your requirements.txt:

```
neo4j>=5.0.0
networkx>=2.5
matplotlib>=3.4.0
spacy>=3.0.0
```

And run:

```bash
pip install -r requirements.txt
python -m spacy download en_core_web_sm
```

## Usage

### Building the Knowledge Graph

The knowledge graph is built automatically when you upload documents. You can also rebuild it manually from the Knowledge Graph tab or sidebar.

### Viewing the Knowledge Graph

1. Navigate to the "Knowledge Graph" tab in the application
2. Explore the interactive graph visualization
3. Search for entities or concepts
4. Find paths between entities

### Knowledge Graph-Enhanced Search

1. In the Search tab, select "Knowledge Graph Enhanced" search mode
2. Enter your query
3. The system will use the knowledge graph to expand your query and improve results

### Neo4j Integration

To enable Neo4j integration:

1. Go to the Knowledge Graph tab
2. Scroll down to the Neo4j Database Settings section
3. Enable Neo4j Integration
4. Enter your Neo4j connection details
5. Click "Save Settings"

Once configured, you can:
- Sync the knowledge graph to Neo4j
- Sync from Neo4j to the application
- Persist your knowledge graph between sessions

### Neo4j Cypher Queries

When using Neo4j, you can run Cypher queries directly against your knowledge graph database:

```cypher
// Get all entities
MATCH (e:Entity) RETURN e LIMIT 10

// Find entities by type
MATCH (e:Entity) WHERE e.type = "Concept" RETURN e

// Find relationships between entities
MATCH (e1:Entity)-[r]->(e2:Entity) RETURN e1.name, type(r), e2.name LIMIT 20

// Find paths between two entities
MATCH p = shortestPath((e1:Entity {name: "RAG"})-[*]-(e2:Entity {name: "Document"}))
RETURN p
```

## Architecture

The Knowledge Graph component consists of:

1. **Entity Extractor**: Uses NLP techniques to identify entities and relationships
2. **Graph Model**: Represents entities and relationships in a graph structure
3. **Query Enhancer**: Uses the graph to improve search queries
4. **Neo4j Integration**: Persists the graph to a Neo4j database
5. **Graph Visualization**: Provides interactive visualization of the graph

## Troubleshooting

### Neo4j Connection Issues

If you encounter issues connecting to Neo4j:

1. Ensure Neo4j is running
2. Check that the connection credentials are correct
3. Verify your Neo4j database accepts connections from the application
4. Check if APOC extensions are installed (recommended but not required)

### Missing Entities/Relationships

If you notice expected entities or relationships are missing:

1. Rebuild the knowledge graph from the sidebar
2. Check that your documents were properly processed
3. Consider using a more sophisticated spaCy model (e.g., en_core_web_lg)

### Performance Issues

For large document collections:

1. Use smaller chunk sizes
2. Enable Neo4j integration for better performance with large graphs
3. Use more specific queries when exploring the graph

## Example Knowledge Graph Queries

### Finding related concepts

To find concepts related to "Embedding":

1. Go to the Knowledge Graph Query tab
2. Enter "What is related to Embedding?"
3. The system will identify relationships to the "Embedding" entity

### Finding connections between concepts

To understand how "RAG" and "LLM" are related:

1. Go to the Knowledge Graph tab
2. In the "Find Paths Between Entities" section, select the source and target entities
3. View the discovered paths between them

## Further Reading

- [Neo4j Documentation](https://neo4j.com/docs/)
- [NetworkX Documentation](https://networkx.org/documentation/stable/)
- [Knowledge Graphs in RAG Systems](https://en.wikipedia.org/wiki/Knowledge_graph)
