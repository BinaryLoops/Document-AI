"""
Configuration settings for the knowledge graph module.
"""

import os
from typing import Dict, Any
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Neo4j configuration
NEO4J_ENABLED = os.getenv("NEO4J_ENABLED", "false").lower() in ("true", "1", "t", "yes")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Knowledge graph extraction settings
SPACY_MODEL = os.getenv("SPACY_MODEL", "en_core_web_sm")
MIN_ENTITY_CONFIDENCE = float(os.getenv("MIN_ENTITY_CONFIDENCE", "0.5"))
USE_NER = os.getenv("USE_NER", "true").lower() in ("true", "1", "t", "yes")
USE_NOUN_PHRASES = os.getenv("USE_NOUN_PHRASES", "true").lower() in ("true", "1", "t", "yes")
USE_CUSTOM_RULES = os.getenv("USE_CUSTOM_RULES", "true").lower() in ("true", "1", "t", "yes")

# Retrieval enhancement settings
QUERY_EXPANSION_ENABLED = os.getenv("QUERY_EXPANSION_ENABLED", "true").lower() in ("true", "1", "t", "yes")
RESULTS_RANKING_ENABLED = os.getenv("RESULTS_RANKING_ENABLED", "true").lower() in ("true", "1", "t", "yes")
MAX_EXPANSION_TERMS = int(os.getenv("MAX_EXPANSION_TERMS", "5"))
SEMANTIC_EXPANSION_WEIGHT = float(os.getenv("SEMANTIC_EXPANSION_WEIGHT", "0.3"))
GRAPH_RANKING_WEIGHT = float(os.getenv("GRAPH_RANKING_WEIGHT", "0.3"))

# Graph visualization settings
MAX_NODES_VISUALIZATION = int(os.getenv("MAX_NODES_VISUALIZATION", "100"))
MAX_EDGES_VISUALIZATION = int(os.getenv("MAX_EDGES_VISUALIZATION", "200"))

# Entity types and colors for visualization
ENTITY_COLORS = {
    "Person": "#4285F4",  # Blue
    "Organization": "#EA4335",  # Red
    "Location": "#FBBC05",  # Yellow
    "Concept": "#34A853",  # Green
    "Product": "#8F00FF",  # Purple
    "Event": "#FF6D01",  # Orange
    "WorkOfArt": "#00BCD4",  # Cyan
    "Other": "#9E9E9E"  # Gray
}


def get_neo4j_config() -> Dict[str, Any]:
    """
    Get Neo4j configuration.
    
    Returns:
        Dictionary with Neo4j configuration
    """
    return {
        "enabled": NEO4J_ENABLED,
        "uri": NEO4J_URI,
        "username": NEO4J_USERNAME,
        "password": NEO4J_PASSWORD,
        "database": NEO4J_DATABASE
    }


def get_extraction_config() -> Dict[str, Any]:
    """
    Get knowledge graph extraction configuration.
    
    Returns:
        Dictionary with extraction configuration
    """
    return {
        "spacy_model": SPACY_MODEL,
        "min_entity_confidence": MIN_ENTITY_CONFIDENCE,
        "use_ner": USE_NER,
        "use_noun_phrases": USE_NOUN_PHRASES,
        "use_custom_rules": USE_CUSTOM_RULES
    }


def get_retrieval_config() -> Dict[str, Any]:
    """
    Get retrieval enhancement configuration.
    
    Returns:
        Dictionary with retrieval enhancement configuration
    """
    return {
        "query_expansion_enabled": QUERY_EXPANSION_ENABLED,
        "results_ranking_enabled": RESULTS_RANKING_ENABLED,
        "max_expansion_terms": MAX_EXPANSION_TERMS,
        "semantic_expansion_weight": SEMANTIC_EXPANSION_WEIGHT,
        "graph_ranking_weight": GRAPH_RANKING_WEIGHT
    }


def get_visualization_config() -> Dict[str, Any]:
    """
    Get graph visualization configuration.
    
    Returns:
        Dictionary with visualization configuration
    """
    return {
        "max_nodes": MAX_NODES_VISUALIZATION,
        "max_edges": MAX_EDGES_VISUALIZATION,
        "entity_colors": ENTITY_COLORS
    }