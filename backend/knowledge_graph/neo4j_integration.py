"""
Integration between KnowledgeGraph and Neo4j database.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
import os

from .model import KnowledgeGraph, Entity, Relation
from .neo4j_store import Neo4jKnowledgeGraphStore
from .config import get_neo4j_config

# Configure logging
logger = logging.getLogger(__name__)


class Neo4jIntegration:
    """
    Integrates the in-memory knowledge graph with Neo4j database.
    """
    
    def __init__(self, kg: Optional[KnowledgeGraph] = None):
        """
        Initialize Neo4j integration.
        
        Args:
            kg: Optional knowledge graph to integrate with
        """
        self.knowledge_graph = kg or KnowledgeGraph()
        self.config = get_neo4j_config()
        self.store = Neo4jKnowledgeGraphStore(
            uri=self.config["uri"],
            username=self.config["username"],
            password=self.config["password"],
            database=self.config["database"]
        )
        self.connected = False
    
    def connect(self) -> bool:
        """
        Connect to Neo4j database.
        
        Returns:
            Whether connection was successful
        """
        if not self.config["enabled"]:
            logger.info("Neo4j integration is disabled")
            return False
        
        if self.connected:
            return True
        
        self.connected = self.store.connect()
        return self.connected
    
    def disconnect(self) -> None:
        """
        Disconnect from Neo4j database.
        """
        if self.connected:
            self.store.close()
            self.connected = False
    
    def sync_to_neo4j(self) -> bool:
        """
        Sync the in-memory knowledge graph to Neo4j.
        
        Returns:
            Whether sync was successful
        """
        if not self.config["enabled"]:
            logger.info("Neo4j integration is disabled")
            return False
        
        if not self.connected and not self.connect():
            logger.error("Failed to connect to Neo4j")
            return False
        
        try:
            logger.info("Syncing knowledge graph to Neo4j...")
            return self.store.save_knowledge_graph(self.knowledge_graph)
        except Exception as e:
            logger.error(f"Error syncing to Neo4j: {e}")
            return False
    
    def sync_from_neo4j(self) -> bool:
        """
        Sync from Neo4j to the in-memory knowledge graph.
        
        Returns:
            Whether sync was successful
        """
        if not self.config["enabled"]:
            logger.info("Neo4j integration is disabled")
            return False
        
        if not self.connected and not self.connect():
            logger.error("Failed to connect to Neo4j")
            return False
        
        try:
            logger.info("Syncing knowledge graph from Neo4j...")
            loaded_kg = self.store.load_knowledge_graph()
            
            if loaded_kg:
                self.knowledge_graph = loaded_kg
                return True
            else:
                logger.error("Failed to load knowledge graph from Neo4j")
                return False
        except Exception as e:
            logger.error(f"Error syncing from Neo4j: {e}")
            return False
    
    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """
        Get an entity by ID from Neo4j.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity if found, None otherwise
        """
        if not self.config["enabled"]:
            # Use in-memory knowledge graph
            return self.knowledge_graph.get_entity(entity_id)
        
        if not self.connected and not self.connect():
            # Fall back to in-memory knowledge graph
            return self.knowledge_graph.get_entity(entity_id)
        
        try:
            entity = self.store.get_entity_by_id(entity_id)
            if entity:
                return entity
            
            # Fall back to in-memory knowledge graph
            return self.knowledge_graph.get_entity(entity_id)
        except Exception as e:
            logger.error(f"Error getting entity from Neo4j: {e}")
            return self.knowledge_graph.get_entity(entity_id)
    
    def search_entities(self, query: str, entity_type: Optional[str] = None, limit: int = 10) -> List[Entity]:
        """
        Search for entities in Neo4j.
        
        Args:
            query: Search query
            entity_type: Optional entity type to filter by
            limit: Maximum number of results to return
            
        Returns:
            List of matching entities
        """
        if not self.config["enabled"]:
            # Use in-memory knowledge graph
            return self.knowledge_graph.search_entities(query, entity_type)[:limit]
        
        if not self.connected and not self.connect():
            # Fall back to in-memory knowledge graph
            return self.knowledge_graph.search_entities(query, entity_type)[:limit]
        
        try:
            entities = self.store.search_entities(query, entity_type, limit)
            if entities:
                return entities
            
            # Fall back to in-memory knowledge graph
            return self.knowledge_graph.search_entities(query, entity_type)[:limit]
        except Exception as e:
            logger.error(f"Error searching entities in Neo4j: {e}")
            return self.knowledge_graph.search_entities(query, entity_type)[:limit]
    
    def get_neighbors(self, entity_id: str, relation_type: Optional[str] = None) -> List[Tuple[Entity, Relation]]:
        """
        Get neighbors of an entity from Neo4j.
        
        Args:
            entity_id: Entity ID
            relation_type: Optional relation type to filter by
            
        Returns:
            List of (entity, relation) tuples
        """
        if not self.config["enabled"]:
            # Use in-memory knowledge graph
            return self.knowledge_graph.get_neighbors(entity_id, relation_type)
        
        if not self.connected and not self.connect():
            # Fall back to in-memory knowledge graph
            return self.knowledge_graph.get_neighbors(entity_id, relation_type)
        
        try:
            neighbors = self.store.get_neighbors(entity_id, relation_type)
            if neighbors:
                return neighbors
            
            # Fall back to in-memory knowledge graph
            return self.knowledge_graph.get_neighbors(entity_id, relation_type)
        except Exception as e:
            logger.error(f"Error getting neighbors from Neo4j: {e}")
            return self.knowledge_graph.get_neighbors(entity_id, relation_type)
    
    def find_paths(self, source_id: str, target_id: str, max_hops: int = 3) -> List[List[Dict[str, Any]]]:
        """
        Find paths between entities in Neo4j.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            max_hops: Maximum number of hops
            
        Returns:
            List of paths
        """
        if not self.config["enabled"]:
            # Use in-memory knowledge graph
            paths = self.knowledge_graph.find_path(source_id, target_id, max_hops)
            
            # Convert to dict format
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
                            "id": relation.id,
                            "type": relation.type,
                            "source": relation.source,
                            "target": relation.target,
                            "weight": relation.weight
                        }
                    
                    formatted_path.append(step)
                
                formatted_paths.append(formatted_path)
            
            return formatted_paths
        
        if not self.connected and not self.connect():
            # Fall back to in-memory knowledge graph
            paths = self.knowledge_graph.find_path(source_id, target_id, max_hops)
            
            # Convert to dict format (same as above)
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
                            "id": relation.id,
                            "type": relation.type,
                            "source": relation.source,
                            "target": relation.target,
                            "weight": relation.weight
                        }
                    
                    formatted_path.append(step)
                
                formatted_paths.append(formatted_path)
            
            return formatted_paths
        
        try:
            paths = self.store.find_paths(source_id, target_id, max_hops)
            if paths:
                return paths
            
            # Fall back to in-memory knowledge graph
            paths = self.knowledge_graph.find_path(source_id, target_id, max_hops)
            
            # Convert to dict format (same as above)
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
                            "id": relation.id,
                            "type": relation.type,
                            "source": relation.source,
                            "target": relation.target,
                            "weight": relation.weight
                        }
                    
                    formatted_path.append(step)
                
                formatted_paths.append(formatted_path)
            
            return formatted_paths
        except Exception as e:
            logger.error(f"Error finding paths in Neo4j: {e}")
            paths = self.knowledge_graph.find_path(source_id, target_id, max_hops)
            
            # Convert to dict format (same as above)
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
                            "id": relation.id,
                            "type": relation.type,
                            "source": relation.source,
                            "target": relation.target,
                            "weight": relation.weight
                        }
                    
                    formatted_path.append(step)
                
                formatted_paths.append(formatted_path)
            
            return formatted_paths
    
    def clear_database(self) -> bool:
        """
        Clear the Neo4j database.
        
        Returns:
            Whether clear was successful
        """
        if not self.config["enabled"]:
            logger.info("Neo4j integration is disabled")
            return False
        
        if not self.connected and not self.connect():
            logger.error("Failed to connect to Neo4j")
            return False
        
        try:
            return self.store.clear_database()
        except Exception as e:
            logger.error(f"Error clearing Neo4j database: {e}")
            return False