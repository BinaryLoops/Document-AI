"""
Enhanced query processing using knowledge graphs.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Set

from .model import KnowledgeGraph, Entity, Relation

# Configure logging
logger = logging.getLogger(__name__)


class KnowledgeGraphQueryProcessor:
    """
    Processes and enhances queries using knowledge graph.
    """
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        """
        Initialize the query processor.
        
        Args:
            knowledge_graph: Knowledge graph to use for query processing
        """
        self.knowledge_graph = knowledge_graph
    
    def expand_query(self, query: str, expansion_factor: float = 0.5, max_terms: int = 5) -> str:
        """
        Expand a query with related terms from the knowledge graph.
        
        Args:
            query: Original query
            expansion_factor: Strength of expansion (0.0-1.0)
            max_terms: Maximum number of expansion terms to add
            
        Returns:
            Expanded query
        """
        logger.info(f"Expanding query: '{query}'")
        
        # Extract entities from query
        query_entities = []
        
        # Try to match phrases in query with entities in knowledge graph
        for entity in self.knowledge_graph.entities.values():
            if entity.name.lower() in query.lower():
                query_entities.append(entity)
        
        if not query_entities:
            logger.info("No entities found in query for expansion")
            return query
        
        logger.info(f"Found {len(query_entities)} entities in query")
        
        # Get related entities for expansion
        expansion_terms = []
        
        for entity in query_entities:
            # Get neighbors
            neighbors = self.knowledge_graph.get_neighbors(entity.id)
            
            # Add neighbor names as expansion terms
            for neighbor, relation in neighbors:
                # Skip if the name is too short or already in the query
                if len(neighbor.name) < 3 or neighbor.name.lower() in query.lower():
                    continue
                    
                expansion_terms.append((neighbor.name, relation.weight))
        
        # Sort by relation weight and limit number of terms
        expansion_terms.sort(key=lambda x: x[1], reverse=True)
        expansion_terms = expansion_terms[:max_terms]
        
        # Create expanded query
        if expansion_terms:
            expanded_query = query
            
            # Calculate expansion strength based on factor
            if expansion_factor > 0:
                added_terms = [term for term, _ in expansion_terms]
                expanded_query = f"{query} {' '.join(added_terms)}"
                
            logger.info(f"Expanded query: '{expanded_query}'")
            return expanded_query
        else:
            return query
    
    def extract_query_intent(self, query: str) -> Dict[str, Any]:
        """
        Extract intent and focus entities from a query.
        
        Args:
            query: User query
            
        Returns:
            Dictionary with query intent information
        """
        intent_info = {
            "type": "general",
            "entities": [],
            "relations": [],
            "focus": None
        }
        
        # Detect query type
        query_lower = query.lower()
        
        if re.search(r'(compare|comparison|difference|similarities? between)', query_lower):
            intent_info["type"] = "comparison"
        elif re.search(r'(list|what are|what is|examples of)', query_lower):
            intent_info["type"] = "list"
        elif re.search(r'(explain|why|how does|how do)', query_lower):
            intent_info["type"] = "explanation"
        elif re.search(r'(relationship|connection|related|link|associate)', query_lower):
            intent_info["type"] = "relationship"
        
        # Find entities mentioned in query
        for entity in self.knowledge_graph.entities.values():
            if entity.name.lower() in query_lower:
                # Add to found entities
                intent_info["entities"].append({
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type
                })
                
                # If we have no focus entity yet, set this as focus
                if intent_info["focus"] is None:
                    intent_info["focus"] = entity.id
        
        # If we have multiple entities, look for relations between them
        if len(intent_info["entities"]) > 1:
            entity_ids = [entity["id"] for entity in intent_info["entities"]]
            
            for i in range(len(entity_ids)):
                for j in range(i + 1, len(entity_ids)):
                    # Find paths between these entities
                    paths = self.knowledge_graph.find_path(entity_ids[i], entity_ids[j], max_hops=2)
                    
                    if paths:
                        for path in paths:
                            for idx, (entity, relation) in enumerate(path):
                                if relation is not None:  # Skip first entity which has no incoming relation
                                    intent_info["relations"].append({
                                        "type": relation.type,
                                        "source": relation.source,
                                        "target": relation.target
                                    })
        
        return intent_info
    
    def formulate_graph_query(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Convert a natural language query to a graph query if possible.
        
        Args:
            query: Natural language query
            
        Returns:
            Graph query specification or None if not applicable
        """
        # Check if query can be interpreted as a graph query
        query_lower = query.lower()
        
        # Detect relation-focused queries
        relation_patterns = [
            r'(?:what|which|who) (?:is|are) (?:the|a) (.+?) (?:of|for|related to) (.+?)\?',
            r'(?:how|why) (?:is|are) (.+?) (?:related to|connected to|associated with) (.+?)\?',
            r'(?:what|which) (.+?) (?:has|have|contains) (.+?)\?'
        ]
        
        for pattern in relation_patterns:
            match = re.search(pattern, query_lower)
            if match:
                relation_type = match.group(1).strip()
                entity_name = match.group(2).strip()
                
                # Find matching entities
                entities = self.knowledge_graph.get_entity_by_name(entity_name)
                
                if entities:
                    return {
                        "type": "relation_query",
                        "entity": entities[0].id,
                        "entity_name": entities[0].name,
                        "relation": relation_type
                    }
        
        # Detect entity property queries
        property_patterns = [
            r'(?:what|which|who) (?:is|are) (.+?)\?',
            r'(?:tell me about|describe) (.+?)(?:\.|$)'
        ]
        
        for pattern in property_patterns:
            match = re.search(pattern, query_lower)
            if match:
                entity_name = match.group(1).strip()
                
                # Find matching entities
                entities = self.knowledge_graph.get_entity_by_name(entity_name)
                
                if entities:
                    return {
                        "type": "entity_query",
                        "entity": entities[0].id,
                        "entity_name": entities[0].name
                    }
        
        # Detect path queries
        path_patterns = [
            r'(?:how is|what is the relationship between) (.+?) and (.+?)\?',
            r'(?:how are) (.+?) and (.+?) (?:related|connected)\?'
        ]
        
        for pattern in path_patterns:
            match = re.search(pattern, query_lower)
            if match:
                entity1_name = match.group(1).strip()
                entity2_name = match.group(2).strip()
                
                # Find matching entities
                entities1 = self.knowledge_graph.get_entity_by_name(entity1_name)
                entities2 = self.knowledge_graph.get_entity_by_name(entity2_name)
                
                if entities1 and entities2:
                    return {
                        "type": "path_query",
                        "source": entities1[0].id,
                        "source_name": entities1[0].name,
                        "target": entities2[0].id,
                        "target_name": entities2[0].name
                    }
        
        return None
    
    def execute_graph_query(self, graph_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a graph query and return results.
        
        Args:
            graph_query: Graph query specification
            
        Returns:
            Query results
        """
        if graph_query["type"] == "relation_query":
            # Query for entities related to a given entity by a specific relation
            entity_id = graph_query["entity"]
            relation_type = graph_query["relation"]
            
            # Get connections
            neighbors = self.knowledge_graph.get_neighbors(entity_id)
            
            # Filter by relation type if specified
            if relation_type != "*":
                filtered_neighbors = []
                for neighbor, relation in neighbors:
                    if relation_type.lower() in relation.type.lower():
                        filtered_neighbors.append((neighbor, relation))
                neighbors = filtered_neighbors
            
            return {
                "type": "relation_results",
                "query": graph_query,
                "count": len(neighbors),
                "results": [
                    {
                        "id": neighbor.id,
                        "name": neighbor.name,
                        "type": neighbor.type,
                        "relation": relation.type
                    }
                    for neighbor, relation in neighbors
                ]
            }
            
        elif graph_query["type"] == "entity_query":
            # Query for information about a specific entity
            entity_id = graph_query["entity"]
            
            # Get entity
            entity = self.knowledge_graph.get_entity(entity_id)
            
            if not entity:
                return {
                    "type": "entity_results",
                    "query": graph_query,
                    "error": "Entity not found"
                }
            
            # Get connections grouped by relation type
            connections = self.knowledge_graph.get_entity_connections(entity_id)
            
            formatted_connections = {}
            for relation_type, neighbors in connections.items():
                formatted_connections[relation_type] = [
                    {
                        "id": neighbor.id,
                        "name": neighbor.name,
                        "type": neighbor.type
                    }
                    for neighbor, _ in neighbors
                ]
            
            return {
                "type": "entity_results",
                "query": graph_query,
                "entity": {
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "metadata": entity.metadata
                },
                "connections": formatted_connections
            }
            
        elif graph_query["type"] == "path_query":
            # Query for paths between two entities
            source_id = graph_query["source"]
            target_id = graph_query["target"]
            
            # Find paths
            paths = self.knowledge_graph.find_path(source_id, target_id, max_hops=3)
            
            formatted_paths = []
            for path in paths:
                formatted_path = []
                for entity, relation in path:
                    step = {
                        "entity": {
                            "id": entity.id,
                            "name": entity.name,
                            "type": entity.type
                        }
                    }
                    
                    if relation:
                        step["relation"] = {
                            "type": relation.type,
                            "source": relation.source,
                            "target": relation.target
                        }
                    
                    formatted_path.append(step)
                formatted_paths.append(formatted_path)
            
            return {
                "type": "path_results",
                "query": graph_query,
                "count": len(paths),
                "paths": formatted_paths
            }
        
        return {
            "type": "error",
            "message": "Unsupported query type"
        }
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query using the knowledge graph.
        
        Args:
            query: Natural language query
            
        Returns:
            Query results
        """
        # Extract query intent
        intent = self.extract_query_intent(query)
        
        # Try to formulate as a graph query
        graph_query = self.formulate_graph_query(query)
        
        if graph_query:
            # Execute graph query
            results = self.execute_graph_query(graph_query)
            
            # Add intent information
            results["intent"] = intent
            
            return results
        else:
            # Return intent information for regular RAG processing
            return {
                "type": "intent_only",
                "intent": intent,
                "expanded_query": self.expand_query(query)
            }
    
    def format_graph_results(self, results: Dict[str, Any]) -> str:
        """
        Format graph query results as a human-readable string.
        
        Args:
            results: Graph query results
            
        Returns:
            Formatted results string
        """
        if results["type"] == "relation_results":
            query = results["query"]
            count = results["count"]
            
            output = f"Found {count} {query['relation']} for {query['entity_name']}:\n\n"
            
            for item in results["results"]:
                output += f"- {item['name']} ({item['type']}): {item['relation']}\n"
            
            return output
            
        elif results["type"] == "entity_results":
            entity = results["entity"]
            
            output = f"Information about {entity['name']} ({entity['type']}):\n\n"
            
            # Add metadata if available
            if entity['metadata']:
                output += "Properties:\n"
                for key, value in entity['metadata'].items():
                    if key not in ["source_text", "start_char", "end_char"]:
                        output += f"- {key}: {value}\n"
                output += "\n"
            
            # Add connections
            if results["connections"]:
                output += "Connections:\n"
                for relation_type, neighbors in results["connections"].items():
                    output += f"- {relation_type}: {', '.join([n['name'] for n in neighbors])}\n"
            
            return output
            
        elif results["type"] == "path_results":
            query = results["query"]
            count = results["count"]
            
            output = f"Found {count} connection paths between {query['source_name']} and {query['target_name']}:\n\n"
            
            for i, path in enumerate(results["paths"]):
                output += f"Path {i+1}:\n"
                
                for j, step in enumerate(path):
                    if j > 0:
                        prev_step = path[j-1]
                        relation = step.get("relation")
                        if relation:
                            output += f"  → {relation['type']} → "
                    
                    output += f"{step['entity']['name']}"
                    
                    if j < len(path) - 1:
                        output += " "
                    else:
                        output += "\n"
                
                output += "\n"
            
            return output
            
        elif results["type"] == "intent_only":
            intent = results["intent"]
            
            output = f"Query intent: {intent['type']}\n"
            
            if intent['entities']:
                output += f"Entities mentioned: {', '.join([e['name'] for e in intent['entities']])}\n"
            
            if results.get("expanded_query"):
                output += f"Expanded query: {results['expanded_query']}\n"
            
            return output
        
        return "No formatted results available."