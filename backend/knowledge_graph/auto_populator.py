"""
Knowledge Graph Auto-Population from Extracted Fields.
P9 requirement: Auto-populate entities and relationships from extracted documents.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeGraphAutoPopulator:
    """
    Automatically populate knowledge graph from extracted document fields.
    """
    
    def __init__(self, kg_store):
        """
        Initialize auto-populator.
        
        Args:
            kg_store: Knowledge graph storage backend (Neo4j or in-memory)
        """
        self.kg_store = kg_store
        logger.info("KnowledgeGraphAutoPopulator initialized")
    
    def populate_from_extraction(
        self,
        document_id: str,
        document_type: str,
        extracted_fields: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Populate knowledge graph from extracted fields.
        
        Args:
            document_id: Document identifier
            document_type: Type of document
            extracted_fields: List of extracted fields with evidence
            metadata: Additional document metadata
        """
        # Create document node
        self._create_document_node(document_id, document_type, metadata or {})
        
        # Extract and create entities
        entities = self._extract_entities(extracted_fields, document_type)
        
        for entity in entities:
            # Create entity node
            entity_id = self._create_entity_node(
                entity_type=entity['type'],
                entity_value=entity['value'],
                properties=entity.get('properties', {})
            )
            
            # Create relationship between document and entity
            self._create_relationship(
                from_id=document_id,
                to_id=entity_id,
                relationship_type=entity.get('relationship', 'MENTIONS')
            )
        
        logger.info(f"Populated {len(entities)} entities for document {document_id}")
    
    def _create_document_node(
        self,
        document_id: str,
        document_type: str,
        metadata: Dict[str, Any]
    ):
        """Create document node in knowledge graph."""
        properties = {
            'id': document_id,
            'type': document_type,
            'created_at': datetime.utcnow().isoformat(),
            **metadata
        }
        
        self.kg_store.create_node(
            node_type='Document',
            node_id=document_id,
            properties=properties
        )
    
    def _extract_entities(
        self,
        extracted_fields: List[Dict[str, Any]],
        document_type: str
    ) -> List[Dict[str, Any]]:
        """
        Extract entities from fields based on document type.
        
        Returns:
            List of entity dictionaries
        """
        entities = []
        
        # Field to entity type mapping
        field_mapping = {
            # Person fields
            'full_name': ('Person', 'HAS_PERSON'),
            'applicant_name': ('Person', 'HAS_APPLICANT'),
            'holder_name': ('Person', 'HAS_HOLDER'),
            'deponent_name': ('Person', 'HAS_DEPONENT'),
            'father_name': ('Person', 'HAS_FATHER'),
            'mother_name': ('Person', 'HAS_MOTHER'),
            'judge_name': ('Person', 'HAS_JUDGE'),
            'advocate_name': ('Person', 'HAS_ADVOCATE'),
            'party_a_name': ('Person', 'HAS_PARTY_A'),
            'party_b_name': ('Person', 'HAS_PARTY_B'),
            
            # Organization fields
            'issuing_authority': ('Organization', 'ISSUED_BY'),
            'court_name': ('Organization', 'FILED_IN'),
            'department': ('Organization', 'SUBMITTED_TO'),
            
            # Address fields
            'address': ('Address', 'HAS_ADDRESS'),
            'applicant_address': ('Address', 'HAS_ADDRESS'),
            
            # Date fields
            'date_of_birth': ('Date', 'HAS_DATE'),
            'issue_date': ('Date', 'ISSUED_ON'),
            'date_filed': ('Date', 'FILED_ON'),
            'statement_date': ('Date', 'DATED'),
            
            # ID fields
            'document_number': ('ID', 'HAS_ID'),
            'application_number': ('ID', 'HAS_APPLICATION_ID'),
            'case_number': ('ID', 'HAS_CASE_ID'),
            'certificate_number': ('ID', 'HAS_CERTIFICATE_ID'),
        }
        
        for field_data in extracted_fields:
            field_name = field_data.get('field', '')
            value = field_data.get('value')
            confidence = field_data.get('confidence', 0.0)
            
            if not value or confidence < 0.5:  # Skip low confidence
                continue
            
            # Get entity type and relationship
            if field_name in field_mapping:
                entity_type, relationship = field_mapping[field_name]
                
                entities.append({
                    'type': entity_type,
                    'value': str(value),
                    'relationship': relationship,
                    'properties': {
                        'confidence': confidence,
                        'source_field': field_name,
                        'evidence': field_data.get('evidence', {})
                    }
                })
        
        return entities
    
    def _create_entity_node(
        self,
        entity_type: str,
        entity_value: str,
        properties: Dict[str, Any]
    ) -> str:
        """
        Create entity node in knowledge graph.
        
        Returns:
            Entity ID
        """
        # Generate entity ID
        entity_id = f"{entity_type}_{entity_value}".replace(' ', '_')
        
        # Merge properties
        node_properties = {
            'value': entity_value,
            'type': entity_type,
            **properties
        }
        
        # Create or update node
        self.kg_store.create_node(
            node_type=entity_type,
            node_id=entity_id,
            properties=node_properties
        )
        
        return entity_id
    
    def _create_relationship(
        self,
        from_id: str,
        to_id: str,
        relationship_type: str,
        properties: Optional[Dict[str, Any]] = None
    ):
        """Create relationship in knowledge graph."""
        self.kg_store.create_relationship(
            from_node=from_id,
            to_node=to_id,
            relationship=relationship_type,
            properties=properties or {}
        )
    
    def populate_case_relationships(
        self,
        case_id: str,
        document_ids: List[str]
    ):
        """
        Create relationships between case and documents.
        
        Args:
            case_id: Case identifier
            document_ids: List of document identifiers in the case
        """
        # Create case node if not exists
        self.kg_store.create_node(
            node_type='Case',
            node_id=case_id,
            properties={'id': case_id}
        )
        
        # Link documents to case
        for doc_id in document_ids:
            self._create_relationship(
                from_id=case_id,
                to_id=doc_id,
                relationship_type='HAS_DOCUMENT'
            )
        
        logger.info(f"Created case relationships for {len(document_ids)} documents")


class InMemoryKGStore:
    """
    Simple in-memory knowledge graph store for testing.
    Replace with Neo4j in production.
    """
    
    def __init__(self):
        self.nodes = {}
        self.relationships = []
    
    def create_node(self, node_type: str, node_id: str, properties: Dict[str, Any]):
        """Create or update a node."""
        self.nodes[node_id] = {
            'type': node_type,
            'id': node_id,
            'properties': properties
        }
    
    def create_relationship(
        self,
        from_node: str,
        to_node: str,
        relationship: str,
        properties: Dict[str, Any]
    ):
        """Create a relationship."""
        self.relationships.append({
            'from': from_node,
            'to': to_node,
            'type': relationship,
            'properties': properties
        })
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get node by ID."""
        return self.nodes.get(node_id)
    
    def get_relationships(self, node_id: str) -> List[Dict[str, Any]]:
        """Get all relationships for a node."""
        return [
            r for r in self.relationships
            if r['from'] == node_id or r['to'] == node_id
        ]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics."""
        return {
            'total_nodes': len(self.nodes),
            'total_relationships': len(self.relationships),
            'node_types': list(set(n['type'] for n in self.nodes.values()))
        }
