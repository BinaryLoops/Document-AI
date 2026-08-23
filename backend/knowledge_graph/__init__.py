"""
Knowledge graph module for enhanced document retrieval and querying.
"""

from .model import KnowledgeGraph, Entity, Relation
from .extractor import KnowledgeGraphExtractor
from .integration import KnowledgeGraphEnhancedRetrieval, RAGEnhancer
from .query import KnowledgeGraphQueryProcessor

# Import visualization functions if available
try:
    from .visualize import generate_html_visualization, get_graph_data, save_graph_data_json
except ImportError:
    # Visualization dependencies might not be available
    pass

# Import Government Knowledge Graph layer
try:
    from .gov_graph import GovernmentKnowledgeGraph, NodeType, RelType
except ImportError:
    pass

__all__ = [
    'KnowledgeGraph',
    'Entity',
    'Relation',
    'KnowledgeGraphExtractor',
    'KnowledgeGraphEnhancedRetrieval',
    'RAGEnhancer',
    'KnowledgeGraphQueryProcessor',
]

# Add visualization functions to __all__ if they were imported successfully
if 'generate_html_visualization' in locals():
    __all__.extend(['generate_html_visualization', 'get_graph_data', 'save_graph_data_json'])

# Add Government KG to __all__ if imported successfully
if 'GovernmentKnowledgeGraph' in locals():
    __all__.extend(['GovernmentKnowledgeGraph', 'NodeType', 'RelType'])