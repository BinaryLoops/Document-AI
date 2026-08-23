"""
Knowledge graph implementation for enhanced document relationship modeling.
"""

import logging
import uuid
import re
from typing import List, Dict, Any, Optional, Tuple, Set, Union
import networkx as nx
from dataclasses import dataclass, field

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Class representing an entity in the knowledge graph."""
    name: str
    type: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class Relation:
    """Class representing a relationship between entities."""
    source: str  # Entity ID
    target: str  # Entity ID
    type: str
    weight: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


class KnowledgeGraph:
    """Knowledge graph implementation using NetworkX."""
    
    def __init__(self):
        """Initialize a new knowledge graph."""
        self.graph = nx.DiGraph()
        self.entities: Dict[str, Entity] = {}
        self.relations: Dict[str, Relation] = {}
    
    def add_entity(self, entity: Entity) -> str:
        """
        Add an entity to the knowledge graph.
        
        Args:
            entity: Entity to add
            
        Returns:
            Entity ID
        """
        # Check if entity with same name and type already exists
        for existing_entity in self.entities.values():
            if existing_entity.name == entity.name and existing_entity.type == entity.type:
                return existing_entity.id
        
        # Add entity to graph
        self.graph.add_node(
            entity.id,
            name=entity.name,
            type=entity.type,
            metadata=entity.metadata
        )
        
        # Store entity
        self.entities[entity.id] = entity
        
        logger.debug(f"Added entity: {entity.name} ({entity.type})")
        return entity.id
    
    def add_relation(self, relation: Relation) -> str:
        """
        Add a relation between entities.

        Args:
            relation: Relation to add

        Returns:
            Relation ID
        """
        # Ensure source entity exists
        if relation.source not in self.entities:
            logger.warning(f"Source entity {relation.source} not found. Auto-creating entity.")
            # Auto-create entity (optional)
            self.entities[relation.source] = Entity(name=f"Unknown-{relation.source}", type="Unknown")
            self.graph.add_node(relation.source, name=f"Unknown-{relation.source}", type="Unknown")

        # Ensure target entity exists
        if relation.target not in self.entities:
            logger.warning(f"Target entity {relation.target} not found. Auto-creating entity.")
            # Auto-create entity (optional)
            self.entities[relation.target] = Entity(name=f"Unknown-{relation.target}", type="Unknown")
            self.graph.add_node(relation.target, name=f"Unknown-{relation.target}", type="Unknown")

        # Now safe to add relation
        logger.info(f"Adding relation: {self.entities[relation.source].name} --[{relation.type}]--> {self.entities[relation.target].name}")
        self.graph.add_edge(
            relation.source,
            relation.target,
            type=relation.type,
            weight=relation.weight,
            metadata=relation.metadata,
            id=relation.id
        )

        # Store relation
        self.relations[relation.id] = relation
        return relation.id

    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """
        Get an entity by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity if found, None otherwise
        """
        return self.entities.get(entity_id)
    
    def get_entity_by_name(self, name: str, entity_type: Optional[str] = None) -> List[Entity]:
        """
        Get entities by name and optionally type.
        
        Args:
            name: Entity name
            entity_type: Optional entity type
            
        Returns:
            List of matching entities
        """
        matches = []
        for entity in self.entities.values():
            if entity.name.lower() == name.lower():
                if entity_type is None or entity.type == entity_type:
                    matches.append(entity)
        return matches
    
    def get_relation(self, relation_id: str) -> Optional[Relation]:
        """
        Get a relation by ID.
        
        Args:
            relation_id: Relation ID
            
        Returns:
            Relation if found, None otherwise
        """
        return self.relations.get(relation_id)
    
    def get_neighbors(self, entity_id: str, relation_type: Optional[str] = None) -> List[Tuple[Entity, Relation]]:
        """
        Get neighbors of an entity, optionally filtered by relation type.
        
        Args:
            entity_id: Entity ID
            relation_type: Optional relation type to filter by
            
        Returns:
            List of (entity, relation) tuples
        """
        if entity_id not in self.entities:
            return []
        
        neighbors = []
        
        for target_id in self.graph.successors(entity_id):
            edge_data = self.graph.get_edge_data(entity_id, target_id)
            if relation_type is None or edge_data.get("type") == relation_type:
                target_entity = self.entities[target_id]
                relation = Relation(
                    source=entity_id,
                    target=target_id,
                    type=edge_data.get("type"),
                    weight=edge_data.get("weight", 1.0),
                    metadata=edge_data.get("metadata", {}),
                    id=edge_data.get("id")
                )
                neighbors.append((target_entity, relation))
        
        return neighbors
    
    def find_path(self, source_id: str, target_id: str, max_hops: int = 3) -> List[List[Tuple[Entity, Optional[Relation]]]]:
        """
        Find paths between two entities.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            max_hops: Maximum number of hops (path length)
            
        Returns:
            List of paths, where each path is a list of (entity, relation) tuples
        """
        if source_id not in self.entities or target_id not in self.entities:
            return []
        
        try:
            # Find paths with NetworkX
            paths = list(nx.all_simple_paths(self.graph, source_id, target_id, cutoff=max_hops))
            
            # Convert to entity and relation objects
            result_paths = []
            
            for path in paths:
                result_path = []
                
                # Add first entity with no incoming relation
                result_path.append((self.entities[path[0]], None))
                
                # Add remaining entities with their incoming relations
                for i in range(1, len(path)):
                    source = path[i-1]
                    target = path[i]
                    edge_data = self.graph.get_edge_data(source, target)
                    
                    relation = Relation(
                        source=source,
                        target=target,
                        type=edge_data.get("type"),
                        weight=edge_data.get("weight", 1.0),
                        metadata=edge_data.get("metadata", {}),
                        id=edge_data.get("id")
                    )
                    
                    result_path.append((self.entities[target], relation))
                
                result_paths.append(result_path)
            
            return result_paths
        except nx.NetworkXNoPath:
            return []
    
    def query(self, query_entity: str, relation_path: List[str]) -> List[Entity]:
        """
        Query the graph by following a path of relations.
        
        Args:
            query_entity: Starting entity name or ID
            relation_path: List of relation types to follow
            
        Returns:
            List of destination entities
        """
        # Find starting entity
        start_entities = []
        
        if query_entity in self.entities:
            # Direct ID match
            start_entities = [self.entities[query_entity]]
        else:
            # Name match
            start_entities = self.get_entity_by_name(query_entity)
        
        if not start_entities:
            return []
        
        # Start with all source entities
        current_entities = start_entities
        
        # Follow the relation path
        for relation_type in relation_path:
            next_entities = []
            
            for entity in current_entities:
                neighbors = self.get_neighbors(entity.id, relation_type)
                next_entities.extend([neighbor for neighbor, _ in neighbors])
            
            current_entities = next_entities
            
            if not current_entities:
                # No more entities found along this path
                break
        
        return current_entities
    
    def get_entity_connections(self, entity_id_or_name: str) -> Dict[str, List[Tuple[Entity, Relation]]]:
        """
        Get all connections for an entity grouped by relation type.
        
        Args:
            entity_id_or_name: Entity ID or name
            
        Returns:
            Dictionary mapping relation types to lists of (entity, relation) tuples
        """
        # Find entity
        entity_id = entity_id_or_name
        if entity_id_or_name not in self.entities:
            # Try to find by name
            matches = self.get_entity_by_name(entity_id_or_name)
            if matches:
                entity_id = matches[0].id
            else:
                return {}
        
        # Get all neighbors
        all_neighbors = self.get_neighbors(entity_id)
        
        # Group by relation type
        connections: Dict[str, List[Tuple[Entity, Relation]]] = {}
        
        for entity, relation in all_neighbors:
            if relation.type not in connections:
                connections[relation.type] = []
            connections[relation.type].append((entity, relation))
        
        return connections
    
    def search_entities(self, query: str, entity_type: Optional[str] = None) -> List[Entity]:
        """
        Search for entities by name or metadata.
        
        Args:
            query: Search query
            entity_type: Optional entity type to filter by
            
        Returns:
            List of matching entities
        """
        query = query.lower()
        matches = []
        
        for entity in self.entities.values():
            if entity_type is not None and entity.type != entity_type:
                continue
                
            # Check name
            if query in entity.name.lower():
                matches.append(entity)
                continue
                
            # Check metadata
            for key, value in entity.metadata.items():
                if isinstance(value, str) and query in value.lower():
                    matches.append(entity)
                    break
        
        return matches
    
    def clear(self) -> None:
        """
        Clear the knowledge graph.
        """
        self.graph = nx.DiGraph()
        self.entities = {}
        self.relations = {}
        logger.info("Knowledge graph cleared")
    
    def statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the knowledge graph.
        
        Returns:
            Dictionary of statistics
        """
        entity_types = {}
        for entity in self.entities.values():
            if entity.type not in entity_types:
                entity_types[entity.type] = 0
            entity_types[entity.type] += 1
        
        relation_types = {}
        for relation in self.relations.values():
            if relation.type not in relation_types:
                relation_types[relation.type] = 0
            relation_types[relation.type] += 1
        
        return {
            "num_entities": len(self.entities),
            "num_relations": len(self.relations),
            "entity_types": entity_types,
            "relation_types": relation_types,
            "is_connected": nx.is_weakly_connected(self.graph) if self.entities else True,
            "average_degree": sum(dict(self.graph.degree()).values()) / len(self.entities) if self.entities else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the knowledge graph to a dictionary.
        
        Returns:
            Dictionary representation of the knowledge graph
        """
        return {
            "entities": [vars(entity) for entity in self.entities.values()],
            "relations": [vars(relation) for relation in self.relations.values()]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeGraph':
        """
        Create a knowledge graph from a dictionary.
        
        Args:
            data: Dictionary representation of a knowledge graph
            
        Returns:
            KnowledgeGraph instance
        """
        kg = cls()
        
        # Add entities
        for entity_data in data.get("entities", []):
            entity = Entity(
                name=entity_data["name"],
                type=entity_data["type"],
                metadata=entity_data.get("metadata", {}),
                id=entity_data.get("id")
            )
            kg.entities[entity.id] = entity
            kg.graph.add_node(
                entity.id,
                name=entity.name,
                type=entity.type,
                metadata=entity.metadata
            )
        
        # Add relations
        for relation_data in data.get("relations", []):
            relation = Relation(
                source=relation_data["source"],
                target=relation_data["target"],
                type=relation_data["type"],
                weight=relation_data.get("weight", 1.0),
                metadata=relation_data.get("metadata", {}),
                id=relation_data.get("id")
            )
            kg.relations[relation.id] = relation
            kg.graph.add_edge(
                relation.source,
                relation.target,
                type=relation.type,
                weight=relation.weight,
                metadata=relation.metadata,
                id=relation.id
            )
        
        return kg
    
    def save(self, file_path: str) -> None:
        """
        Save the knowledge graph to a file.
        
        Args:
            file_path: Path to save to
        """
        import json
        with open(file_path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
        logger.info(f"Knowledge graph saved to {file_path}")
    
    @classmethod
    def load(cls, file_path: str) -> 'KnowledgeGraph':
        """
        Load a knowledge graph from a file.
        
        Args:
            file_path: Path to load from
            
        Returns:
            KnowledgeGraph instance
        """
        import json
        with open(file_path, 'r') as f:
            data = json.load(f)
        kg = cls.from_dict(data)
        logger.info(f"Knowledge graph loaded from {file_path}")
        return kg