"""
Neo4j integration for knowledge graph storage and retrieval.
"""

import logging
import os
import json
from typing import Dict, List, Any, Optional, Tuple, Set, Union
import uuid

from .model import KnowledgeGraph, Entity, Relation

# Configure logging
logger = logging.getLogger(__name__)


class Neo4jKnowledgeGraphStore:
    """
    Neo4j-based storage for knowledge graphs.
    """
    
    def __init__(
        self,
        uri: str = None,
        username: str = None,
        password: str = None,
        database: str = "neo4j"
    ):
        """
        Initialize the Neo4j knowledge graph store.
        
        Args:
            uri: Neo4j database URI (default: environment variable NEO4J_URI)
            username: Neo4j username (default: environment variable NEO4J_USERNAME)
            password: Neo4j password (default: environment variable NEO4J_PASSWORD)
            database: Neo4j database name
        """
        self.uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        self.username = username or os.environ.get("NEO4J_USERNAME", "neo4j")
        self.password = password or os.environ.get("NEO4J_PASSWORD", "password")
        self.database = database
        self._driver = None
    
    def connect(self) -> bool:
        """
        Connect to the Neo4j database.
        
        Returns:
            Whether connection was successful
        """
        try:
            from neo4j import GraphDatabase
        except ImportError:
            logger.error("Neo4j Python driver not installed. Please install it with 'pip install neo4j'")
            return False
        
        try:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.username, self.password)
            )
            # Test connection
            with self._driver.session(database=self.database) as session:
                result = session.run("RETURN 1 AS num")
                record = result.single()
                if record and record["num"] == 1:
                    logger.info(f"Connected to Neo4j database at {self.uri}")
                    return True
                else:
                    logger.error("Failed to validate Neo4j connection")
                    return False
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self._driver = None
            return False
    
    def close(self) -> None:
        """
        Close the connection to the Neo4j database.
        """
        if self._driver:
            self._driver.close()
            self._driver = None
            logger.info("Closed Neo4j connection")
    
    def save_knowledge_graph(self, kg: KnowledgeGraph, batch_size: int = 1000) -> bool:
        """
        Save a knowledge graph to Neo4j.
        
        Args:
            kg: Knowledge graph to save
            batch_size: Number of entities/relations to save in each transaction
            
        Returns:
            Whether save was successful
        """
        if not self._driver:
            if not self.connect():
                return False
        
        try:
            # Create constraints for uniqueness if they don't exist
            self._create_constraints()
            
            # Save entities in batches
            entity_count = 0
            entity_batches = [list(kg.entities.values())[i:i+batch_size] 
                             for i in range(0, len(kg.entities), batch_size)]
            
            for batch in entity_batches:
                entity_count += self._save_entities_batch(batch)
            
            # Save relations in batches
            relation_count = 0
            relation_batches = [list(kg.relations.values())[i:i+batch_size] 
                               for i in range(0, len(kg.relations), batch_size)]
            
            for batch in relation_batches:
                relation_count += self._save_relations_batch(batch)
            
            logger.info(f"Saved knowledge graph to Neo4j: {entity_count} entities, {relation_count} relations")
            return True
        except Exception as e:
            logger.error(f"Error saving knowledge graph to Neo4j: {e}")
            return False
    
    def load_knowledge_graph(self) -> Optional[KnowledgeGraph]:
        """
        Load a knowledge graph from Neo4j.
        
        Returns:
            Loaded knowledge graph or None if loading failed
        """
        if not self._driver:
            if not self.connect():
                return None
        
        try:
            kg = KnowledgeGraph()
            
            # Load entities
            entity_count = self._load_entities(kg)
            
            # Load relations
            relation_count = self._load_relations(kg)
            
            logger.info(f"Loaded knowledge graph from Neo4j: {entity_count} entities, {relation_count} relations")
            return kg
        except Exception as e:
            logger.error(f"Error loading knowledge graph from Neo4j: {e}")
            return None
    
    def clear_database(self) -> bool:
        """
        Clear all data from the Neo4j database.
        
        Returns:
            Whether clear was successful
        """
        if not self._driver:
            if not self.connect():
                return False
        
        try:
            with self._driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
                logger.info("Cleared all data from Neo4j database")
            return True
        except Exception as e:
            logger.error(f"Error clearing Neo4j database: {e}")
            return False
    
    def get_entity_by_id(self, entity_id: str) -> Optional[Entity]:
        """
        Get an entity from Neo4j by ID.
        
        Args:
            entity_id: Entity ID
            
        Returns:
            Entity if found, None otherwise
        """
        if not self._driver:
            if not self.connect():
                return None
        
        try:
            with self._driver.session(database=self.database) as session:
                result = session.run(
                    """
                    MATCH (e:Entity {id: $id})
                    RETURN e
                    """,
                    id=entity_id
                )
                
                record = result.single()
                if record:
                    node = record["e"]
                    
                    # Convert node properties to entity
                    entity = Entity(
                        id=node["id"],
                        name=node["name"],
                        type=node["type"],
                        metadata=self._parse_json_property(node.get("metadata", "{}"))
                    )
                    
                    return entity
                
                return None
        except Exception as e:
            logger.error(f"Error getting entity from Neo4j: {e}")
            return None
    
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
        if not self._driver:
            if not self.connect():
                return []
        
        try:
            with self._driver.session(database=self.database) as session:
                # Build query based on parameters
                cypher_query = """
                    MATCH (e:Entity)
                    WHERE toLower(e.name) CONTAINS toLower($query)
                    """
                
                if entity_type:
                    cypher_query += " AND e.type = $entity_type"
                
                cypher_query += """
                    RETURN e
                    ORDER BY e.name
                    LIMIT $limit
                    """
                
                params = {
                    "query": query,
                    "limit": limit
                }
                
                if entity_type:
                    params["entity_type"] = entity_type
                
                result = session.run(cypher_query, params)
                
                entities = []
                for record in result:
                    node = record["e"]
                    
                    # Convert node properties to entity
                    entity = Entity(
                        id=node["id"],
                        name=node["name"],
                        type=node["type"],
                        metadata=self._parse_json_property(node.get("metadata", "{}"))
                    )
                    
                    entities.append(entity)
                
                return entities
        except Exception as e:
            logger.error(f"Error searching entities in Neo4j: {e}")
            return []
    
    def get_neighbors(self, entity_id: str, relationship_type: Optional[str] = None) -> List[Tuple[Entity, Relation]]:
        """
        Get neighboring entities and relationships of an entity from Neo4j.
        
        Args:
            entity_id: Entity ID
            relationship_type: Optional relationship type to filter by
            
        Returns:
            List of (entity, relation) tuples
        """
        if not self._driver:
            if not self.connect():
                return []
        
        try:
            with self._driver.session(database=self.database) as session:
                # Build query based on parameters
                cypher_query = """
                    MATCH (e:Entity {id: $entity_id})-[r]->(n:Entity)
                    """
                
                if relationship_type:
                    cypher_query += " WHERE type(r) = $relationship_type"
                
                cypher_query += """
                    RETURN n, r
                    """
                
                params = {
                    "entity_id": entity_id
                }
                
                if relationship_type:
                    params["relationship_type"] = relationship_type
                
                result = session.run(cypher_query, params)
                
                neighbors = []
                for record in result:
                    node = record["n"]
                    rel = record["r"]
                    
                    # Convert node properties to entity
                    entity = Entity(
                        id=node["id"],
                        name=node["name"],
                        type=node["type"],
                        metadata=self._parse_json_property(node.get("metadata", "{}"))
                    )
                    
                    # Convert relationship properties to relation
                    relation = Relation(
                        source=entity_id,
                        target=entity.id,
                        type=rel.type,
                        weight=rel.get("weight", 1.0),
                        metadata=self._parse_json_property(rel.get("metadata", "{}")),
                        id=rel.get("id", str(uuid.uuid4()))
                    )
                    
                    neighbors.append((entity, relation))
                
                return neighbors
        except Exception as e:
            logger.error(f"Error getting neighbors from Neo4j: {e}")
            return []
    
    def find_paths(self, source_id: str, target_id: str, max_hops: int = 3) -> List[List[Dict[str, Any]]]:
        """
        Find paths between two entities in Neo4j.
        
        Args:
            source_id: Source entity ID
            target_id: Target entity ID
            max_hops: Maximum number of hops
            
        Returns:
            List of paths, where each path is a list of dictionaries with entity and relation information
        """
        if not self._driver:
            if not self.connect():
                return []
        
        try:
            with self._driver.session(database=self.database) as session:
                # Use the shortestPath algorithm
                cypher_query = f"""
                    MATCH (source:Entity {{id: $source_id}}), (target:Entity {{id: $target_id}}),
                          p = allShortestPaths((source)-[*1..{max_hops}]->(target))
                    RETURN p
                    LIMIT 10
                    """
                
                result = session.run(
                    cypher_query,
                    source_id=source_id,
                    target_id=target_id
                )
                
                paths = []
                for record in result:
                    path = record["p"]
                    
                    formatted_path = []
                    nodes = path.nodes
                    relationships = path.relationships
                    
                    # Add first node
                    first_node = nodes[0]
                    formatted_path.append({
                        "entity": {
                            "id": first_node["id"],
                            "name": first_node["name"],
                            "type": first_node["type"]
                        },
                        "relation": None
                    })
                    
                    # Add remaining nodes with their incoming relationships
                    for i in range(1, len(nodes)):
                        node = nodes[i]
                        rel = relationships[i-1]
                        
                        formatted_path.append({
                            "entity": {
                                "id": node["id"],
                                "name": node["name"],
                                "type": node["type"]
                            },
                            "relation": {
                                "id": rel.get("id", str(uuid.uuid4())),
                                "type": rel.type,
                                "weight": rel.get("weight", 1.0)
                            }
                        })
                    
                    paths.append(formatted_path)
                
                return paths
        except Exception as e:
            logger.error(f"Error finding paths in Neo4j: {e}")
            return []
    
    def _create_constraints(self) -> None:
        """
        Create constraints in Neo4j for uniqueness.
        """
        if not self._driver:
            return
        
        with self._driver.session(database=self.database) as session:
            # Create constraint for Entity ID uniqueness
            try:
                session.run(
                    """
                    CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
                    FOR (e:Entity)
                    REQUIRE e.id IS UNIQUE
                    """
                )
            except Exception:
                # Older Neo4j versions have a different syntax
                try:
                    session.run(
                        """
                        CREATE CONSTRAINT ON (e:Entity)
                        ASSERT e.id IS UNIQUE
                        """
                    )
                except Exception as e:
                    logger.warning(f"Could not create constraint for Entity ID: {e}")
    
    def _save_entities_batch(self, entities: List[Entity]) -> int:
        """
        Save a batch of entities to Neo4j.
        
        Args:
            entities: List of entities to save
            
        Returns:
            Number of entities saved
        """
        if not self._driver or not entities:
            return 0
        
        with self._driver.session(database=self.database) as session:
            # Use UNWIND for batch operations
            result = session.run(
                """
                UNWIND $entities AS entity
                MERGE (e:Entity {id: entity.id})
                ON CREATE SET
                    e.name = entity.name,
                    e.type = entity.type,
                    e.metadata = entity.metadata
                ON MATCH SET
                    e.name = entity.name,
                    e.type = entity.type,
                    e.metadata = entity.metadata
                RETURN count(e) AS count
                """,
                entities=[{
                    "id": entity.id,
                    "name": entity.name,
                    "type": entity.type,
                    "metadata": self._serialize_json_property(entity.metadata)
                } for entity in entities]
            )
            
            record = result.single()
            return record["count"] if record else 0
    
    def _save_relations_batch(self, relations: List[Relation]) -> int:
        """
        Save a batch of relations to Neo4j.
        
        Args:
            relations: List of relations to save
            
        Returns:
            Number of relations saved
        """
        if not self._driver or not relations:
            return 0
        
        with self._driver.session(database=self.database) as session:
            # Use UNWIND for batch operations
            result = session.run(
                """
                UNWIND $relations AS rel
                MATCH (source:Entity {id: rel.source})
                MATCH (target:Entity {id: rel.target})
                CALL apoc.merge.relationship(
                    source, 
                    rel.type, 
                    {id: rel.id}, 
                    {weight: rel.weight, metadata: rel.metadata}, 
                    target
                ) YIELD rel as created
                RETURN count(created) AS count
                """,
                relations=[{
                    "id": relation.id,
                    "source": relation.source,
                    "target": relation.target,
                    "type": relation.type,
                    "weight": relation.weight,
                    "metadata": self._serialize_json_property(relation.metadata)
                } for relation in relations]
            )
            
            record = result.single()
            if record:
                return record["count"]
            else:
                # If APOC is not available, fall back to standard Cypher
                return self._save_relations_batch_fallback(relations)
    
    def _save_relations_batch_fallback(self, relations: List[Relation]) -> int:
        """
        Alternative method to save relations when APOC is not available.
        
        Args:
            relations: List of relations to save
            
        Returns:
            Number of relations saved
        """
        if not self._driver or not relations:
            return 0
            
        count = 0
        with self._driver.session(database=self.database) as session:
            for relation in relations:
                try:
                    # We need to handle each relationship type individually in Cypher
                    cypher_query = f"""
                    MATCH (source:Entity {{id: $source_id}})
                    MATCH (target:Entity {{id: $target_id}})
                    MERGE (source)-[r:`{relation.type}`]->(target)
                    SET r.id = $rel_id,
                        r.weight = $weight,
                        r.metadata = $metadata
                    RETURN r
                    """
                    
                    result = session.run(
                        cypher_query,
                        source_id=relation.source,
                        target_id=relation.target,
                        rel_id=relation.id,
                        weight=relation.weight,
                        metadata=self._serialize_json_property(relation.metadata)
                    )
                    
                    if result.single():
                        count += 1
                except Exception as e:
                    logger.error(f"Error saving relation {relation.id}: {e}")
                    
        return count
    
    def _load_entities(self, kg: KnowledgeGraph) -> int:
        """
        Load entities from Neo4j into a knowledge graph.
        
        Args:
            kg: Knowledge graph to load into
            
        Returns:
            Number of entities loaded
        """
        with self._driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (e:Entity)
                RETURN e
                """
            )
            
            count = 0
            for record in result:
                node = record["e"]
                
                # Convert node properties to entity
                entity = Entity(
                    id=node["id"],
                    name=node["name"],
                    type=node["type"],
                    metadata=self._parse_json_property(node.get("metadata", "{}"))
                )
                
                # Add to knowledge graph
                kg.entities[entity.id] = entity
                kg.graph.add_node(
                    entity.id,
                    name=entity.name,
                    type=entity.type,
                    metadata=entity.metadata
                )
                
                count += 1
            
            return count
    
    def _load_relations(self, kg: KnowledgeGraph) -> int:
        """
        Load relations from Neo4j into a knowledge graph.
        
        Args:
            kg: Knowledge graph to load into
            
        Returns:
            Number of relations loaded
        """
        with self._driver.session(database=self.database) as session:
            result = session.run(
                """
                MATCH (source:Entity)-[r]->(target:Entity)
                RETURN source.id AS source_id, target.id AS target_id, type(r) AS relation_type,
                       r.id AS relation_id, r.weight AS weight, r.metadata AS metadata
                """
            )
            
            count = 0
            for record in result:
                source_id = record["source_id"]
                target_id = record["target_id"]
                relation_type = record["relation_type"]
                relation_id = record.get("relation_id", str(uuid.uuid4()))
                weight = record.get("weight", 1.0)
                metadata = self._parse_json_property(record.get("metadata", "{}"))
                
                # Create relation
                relation = Relation(
                    id=relation_id,
                    source=source_id,
                    target=target_id,
                    type=relation_type,
                    weight=weight,
                    metadata=metadata
                )
                
                # Add to knowledge graph
                kg.relations[relation.id] = relation
                kg.graph.add_edge(
                    source_id,
                    target_id,
                    id=relation.id,
                    type=relation.type,
                    weight=relation.weight,
                    metadata=relation.metadata
                )
                
                count += 1
            
            return count
    
    def _serialize_json_property(self, obj: Any) -> str:
        """
        Serialize an object to JSON string for Neo4j.
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON string
        """
        import json
        if obj is None:
            return "{}"
        return json.dumps(obj)
    
    def _parse_json_property(self, json_str: str) -> Any:
        """
        Parse a JSON string from Neo4j.
        
        Args:
            json_str: JSON string to parse
            
        Returns:
            Parsed object
        """
        import json
        if not json_str:
            return {}
        try:
            return json.loads(json_str)
        except Exception:
            return {}