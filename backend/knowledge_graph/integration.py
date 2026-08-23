"""
Enhanced RAG integration with knowledge graph for improved retrieval and response generation.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Union, Set
import numpy as np

# Configure logging
logger = logging.getLogger(__name__)


class KnowledgeGraphEnhancedRetrieval:
    """
    Enhanced document retriever that uses knowledge graph to improve retrieval.
    """
    
    def __init__(
        self,
        vector_db,
        knowledge_graph,
        query_expansion_weight: float = 0.3,
        graph_ranking_weight: float = 0.5,
        max_expansion_terms: int = 5,
        top_k: int = 10
    ):
        """
        Initialize the knowledge graph enhanced retriever.
        
        Args:
            vector_db: Vector database for document storage and retrieval
            knowledge_graph: Knowledge graph for enhancing retrieval
            query_expansion_weight: Weight for query expansion terms
            graph_ranking_weight: Weight for graph-based ranking
            max_expansion_terms: Maximum number of terms to add to query
            top_k: Default number of documents to retrieve
        """
        self.vector_db = vector_db
        self.knowledge_graph = knowledge_graph
        self.query_expansion_weight = query_expansion_weight
        self.graph_ranking_weight = graph_ranking_weight
        self.max_expansion_terms = max_expansion_terms
        self.top_k = top_k
    
    def retrieve(
        self,
        query: str,
        query_embedding: np.ndarray,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve documents enhanced with knowledge graph.
        
        Args:
            query: Query string
            query_embedding: Query embedding vector
            top_k: Number of documents to retrieve
            filter_dict: Optional filter for documents
            
        Returns:
            List of retrieved documents with scores
        """
        if top_k is None:
            top_k = self.top_k
        
        # Extract query entities
        query_entities = self.extract_entities_from_query(query)
        logger.info(f"Found {len(query_entities)} entities in query: {query_entities}")
        
        # Extract key terms for expansion
        expansion_terms = self.generate_expansion_terms(query_entities)
        logger.info(f"Generated {len(expansion_terms)} expansion terms: {expansion_terms}")
        
        # Get expanded query embedding from original query embedding
        if expansion_terms:
            expanded_query = self.create_expanded_query(query, expansion_terms)
            logger.info(f"Expanded query: {expanded_query}")
        else:
            expanded_query = query
        
        # Retrieve initial documents
        retrieved_docs = self.basic_retrieve(query_embedding, top_k * 2, filter_dict)
        
        # Rerank documents based on graph relevance
        reranked_docs = self.graph_rerank(retrieved_docs, query_entities)
        
        # Return top_k documents
        return reranked_docs[:top_k]
    
    def basic_retrieve(
        self,
        query_embedding: np.ndarray,
        top_k: int,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform basic retrieval using vector database.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of documents to retrieve
            filter_dict: Optional filter for documents
            
        Returns:
            List of retrieved documents with scores
        """
        # Create filter function if filter_dict is provided
        filter_func = None
        if filter_dict:
            def filter_func(doc):
                for key, value in filter_dict.items():
                    if key not in doc.metadata or doc.metadata[key] != value:
                        return False
                return True
        
        # Perform search
        results = self.vector_db.search(query_embedding, top_k, filter_func)
        
        # Convert to document dictionaries
        return [
            {
                "id": doc.id,
                "text": doc.text,
                "metadata": doc.metadata,
                "score": float(score)
            }
            for doc, score in results
        ]
    
    def extract_entities_from_query(self, query: str) -> List[str]:
        """
        Extract entities from query string.
        
        Args:
            query: Query string
            
        Returns:
            List of entity names found in query
        """
        entities = []
        
        # First try to find exact matches with entities in KG
        known_entities = set()
        for entity in self.knowledge_graph.entities.values():
            entity_name = entity["name"]
            if entity_name.lower() in query.lower():
                known_entities.add(entity_name)
        
        # Sort by length (longest first) to handle nested entities
        entities = sorted(known_entities, key=len, reverse=True)
        
        # If no known entities found, try noun phrase extraction
        if not entities:
            # Simple noun phrase extraction
            noun_phrases = []
            
            # Define patterns for noun phrases
            patterns = [
                r'\b[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*\b',  # Proper nouns
                r'\b[a-z]+\s+[a-z]+(?:\s+[a-z]+)*\b'     # Common noun phrases
            ]
            
            for pattern in patterns:
                matches = re.finditer(pattern, query)
                for match in matches:
                    phrase = match.group(0)
                    if len(phrase) > 3 and phrase.lower() not in ["the", "and", "for", "with"]:
                        noun_phrases.append(phrase)
            
            entities.extend(noun_phrases)
        
        return entities
    
    def generate_expansion_terms(self, query_entities: List[str]) -> List[str]:
        """
        Generate expansion terms from query entities using knowledge graph.
        
        Args:
            query_entities: List of entity names
            
        Returns:
            List of expansion terms
        """
        expansion_terms = set()
        
        for entity_name in query_entities:
            # Find matching entities in knowledge graph
            entity_matches = self.knowledge_graph.get_entity_by_name(entity_name)
            
            for entity in entity_matches:
                entity_id = entity["id"]
                
                # Get neighbors
                neighbors = self.knowledge_graph.get_neighbors(entity_id, direction="both")
                
                # Add neighbor names as expansion terms
                for neighbor in neighbors:
                    neighbor_entity = neighbor["entity"]
                    relation = neighbor["relation"]
                    
                    # Weight terms based on relation confidence
                    if relation["confidence"] > 0.6:
                        expansion_terms.add(neighbor_entity["name"])
        
        # Limit number of expansion terms
        sorted_terms = sorted(expansion_terms, key=len)
        return sorted_terms[:self.max_expansion_terms]
    
    def create_expanded_query(self, original_query: str, expansion_terms: List[str]) -> str:
        """
        Create an expanded query string.
        
        Args:
            original_query: Original query string
            expansion_terms: List of expansion terms
            
        Returns:
            Expanded query string
        """
        if not expansion_terms:
            return original_query
        
        expansion_string = " ".join(expansion_terms)
        expanded_query = f"{original_query} {expansion_string}"
        
        return expanded_query
    
    def graph_rerank(
        self,
        retrieved_docs: List[Dict[str, Any]],
        query_entities: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Rerank retrieved documents based on graph relevance.
        
        Args:
            retrieved_docs: List of retrieved documents
            query_entities: List of entity names in query
            
        Returns:
            Reranked list of documents
        """
        if not query_entities or not retrieved_docs:
            return retrieved_docs
        
        # Extract entities from documents
        doc_entities: Dict[str, List[str]] = {}
        
        for doc in retrieved_docs:
            doc_id = doc["id"]
            doc_text = doc["text"]
            
            # Extract entities from document text
            entities = self.extract_entities_from_text(doc_text)
            doc_entities[doc_id] = entities
        
        # Calculate graph relevance scores
        graph_scores: Dict[str, float] = {}
        
        for doc_id, entities in doc_entities.items():
            # Calculate relevance based on entity overlap and graph connections
            graph_scores[doc_id] = self.calculate_graph_relevance(query_entities, entities)
        
        # Rerank documents using both vector similarity and graph relevance
        reranked_docs = []
        
        for doc in retrieved_docs:
            doc_id = doc["id"]
            vector_score = doc["score"]
            graph_score = graph_scores.get(doc_id, 0.0)
            
            # Combined score (weighted average)
            combined_score = (
                (1.0 - self.graph_ranking_weight) * vector_score +
                self.graph_ranking_weight * graph_score
            )
            
            # Create new document with updated scores
            reranked_doc = doc.copy()
            reranked_doc["score"] = combined_score
            reranked_doc["graph_score"] = graph_score
            reranked_doc["vector_score"] = vector_score
            
            reranked_docs.append(reranked_doc)
        
        # Sort by combined score
        reranked_docs.sort(key=lambda x: x["score"], reverse=True)
        
        return reranked_docs
    
    def extract_entities_from_text(self, text: str) -> List[str]:
        """
        Extract entities from document text.
        
        Args:
            text: Document text
            
        Returns:
            List of entity names
        """
        entities = []
        
        # Check for mentions of known entities
        for entity in self.knowledge_graph.entities.values():
            entity_name = entity["name"]
            if entity_name.lower() in text.lower():
                entities.append(entity_name)
        
        return entities
    
    def calculate_graph_relevance(self, query_entities: List[str], doc_entities: List[str]) -> float:
        """
        Calculate graph-based relevance between query entities and document entities.
        
        Args:
            query_entities: List of entity names from query
            doc_entities: List of entity names from document
            
        Returns:
            Relevance score
        """
        if not query_entities or not doc_entities:
            return 0.0
        
        # Direct overlap score
        overlap_count = sum(1 for e in query_entities if e in doc_entities)
        overlap_score = overlap_count / max(len(query_entities), 1)
        
        # Graph connection score
        connection_score = 0.0
        connection_count = 0
        
        for q_entity in query_entities:
            for d_entity in doc_entities:
                # Skip if same entity
                if q_entity == d_entity:
                    continue
                
                # Find entities in knowledge graph
                q_matches = self.knowledge_graph.get_entity_by_name(q_entity)
                d_matches = self.knowledge_graph.get_entity_by_name(d_entity)
                
                # Skip if no matches found
                if not q_matches or not d_matches:
                    continue
                
                # Check for paths between entities
                q_id = q_matches[0]["id"]
                d_id = d_matches[0]["id"]
                
                paths = self.knowledge_graph.find_path(q_id, d_id, max_hops=2)
                
                if paths:
                    connection_count += 1
                    # Score is higher for shorter paths
                    path_length = len(paths[0])
                    connection_score += 1.0 / path_length
        
        # Normalize connection score
        max_possible_connections = len(query_entities) * len(doc_entities)
        if max_possible_connections > 0 and connection_count > 0:
            connection_score /= max_possible_connections
        
        # Combined score with weights
        relevance_score = (0.6 * overlap_score) + (0.4 * connection_score)
        
        return relevance_score


class KnowledgeGraphEnhancedGenerator:
    """
    Enhanced response generator that uses knowledge graph for better answers.
    """
    
    def __init__(
        self,
        llm,
        knowledge_graph,
        use_graph_context: bool = True,
        use_graph_reasoning: bool = True
    ):
        """
        Initialize the knowledge graph enhanced generator.
        
        Args:
            llm: Language model for response generation
            knowledge_graph: Knowledge graph
            use_graph_context: Whether to include graph context
            use_graph_reasoning: Whether to use graph for reasoning
        """
        self.llm = llm
        self.knowledge_graph = knowledge_graph
        self.use_graph_context = use_graph_context
        self.use_graph_reasoning = use_graph_reasoning
    
    def generate(
        self,
        query: str,
        retrieved_contexts: List[str],
        query_entities: List[str],
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        """
        Generate a response using the retrieved contexts and knowledge graph.
        
        Args:
            query: User query
            retrieved_contexts: List of retrieved document contexts
            query_entities: List of entity names from query
            max_tokens: Maximum response length
            
        Returns:
            Dictionary with response and metadata
        """
        # Create basic context from retrieved documents
        base_context = self.format_document_context(retrieved_contexts)
        
        # Get knowledge graph context
        if self.use_graph_context and query_entities:
            graph_context = self.get_knowledge_graph_context(query_entities)
            combined_context = f"{base_context}\n\nKnowledge Graph Context:\n{graph_context}"
        else:
            combined_context = base_context
        
        # Determine if we need reasoning based on query complexity
        needs_reasoning = self.query_needs_reasoning(query)
        
        # Construct prompt template
        if needs_reasoning and self.use_graph_reasoning:
            prompt_template = self.get_reasoning_prompt_template()
        else:
            prompt_template = self.get_standard_prompt_template()
        
        # Format the prompt
        prompt = prompt_template.format(context=combined_context, query=query)
        
        # Generate response
        response_text = self.llm.generate_response(prompt, max_tokens)
        
        # Return response with metadata
        return {
            "response": response_text,
            "used_graph_context": self.use_graph_context and bool(query_entities),
            "used_reasoning": needs_reasoning and self.use_graph_reasoning,
            "context_length": len(combined_context)
        }
    
    def format_document_context(self, contexts: List[str]) -> str:
        """
        Format retrieved document contexts.
        
        Args:
            contexts: List of document contexts
            
        Returns:
            Formatted context string
        """
        if not contexts:
            return "No relevant documents found."
        
        formatted_parts = []
        
        for i, context in enumerate(contexts):
            formatted_parts.append(f"Document {i+1}:\n{context.strip()}\n")
        
        return "\n".join(formatted_parts)
    
    def get_knowledge_graph_context(self, query_entities: List[str]) -> str:
        """
        Get relevant context from knowledge graph for query entities.
        
        Args:
            query_entities: List of entity names from query
            
        Returns:
            Knowledge graph context string
        """
        if not query_entities:
            return ""
        
        context_parts = []
        
        for entity_name in query_entities:
            # Find matching entities in knowledge graph
            entity_matches = self.knowledge_graph.get_entity_by_name(entity_name)
            
            if not entity_matches:
                continue
            
            entity = entity_matches[0]
            entity_id = entity["id"]
            
            # Get entity information
            context_parts.append(f"Entity: {entity['name']} (Type: {entity['type']})")
            
            # Get entity connections
            neighbors = self.knowledge_graph.get_neighbors(entity_id, direction="both")
            
            if neighbors:
                # Group by relation type
                relations = {}
                for neighbor in neighbors:
                    relation_type = neighbor["relation"]["type"]
                    direction = neighbor["direction"]
                    entity_name = neighbor["entity"]["name"]
                    
                    # Format based on direction
                    if direction == "outgoing":
                        rel_key = f"{relation_type} ->"
                    else:
                        rel_key = f"<- {relation_type}"
                    
                    if rel_key not in relations:
                        relations[rel_key] = []
                    
                    relations[rel_key].append(entity_name)
                
                # Format relations
                for rel_type, entities in relations.items():
                    entities_str = ", ".join(entities[:5])
                    if len(entities) > 5:
                        entities_str += f", and {len(entities) - 5} more"
                    
                    context_parts.append(f"  {rel_type} {entities_str}")
            
            # Add separator
            context_parts.append("")
        
        # Find relationships between query entities
        if len(query_entities) > 1:
            context_parts.append("Entity Relationships:")
            
            for i, e1 in enumerate(query_entities):
                for e2 in query_entities[i+1:]:
                    # Find entities in knowledge graph
                    e1_matches = self.knowledge_graph.get_entity_by_name(e1)
                    e2_matches = self.knowledge_graph.get_entity_by_name(e2)
                    
                    if not e1_matches or not e2_matches:
                        continue
                    
                    # Check for paths between entities
                    e1_id = e1_matches[0]["id"]
                    e2_id = e2_matches[0]["id"]
                    
                    paths = self.knowledge_graph.find_path(e1_id, e2_id, max_hops=2)
                    
                    if paths:
                        # Format the shortest path
                        path = paths[0]
                        path_str = self.format_path(path)
                        context_parts.append(f"  {e1} → {path_str} → {e2}")
            
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    def format_path(self, path: List[Dict[str, Any]]) -> str:
        """
        Format a path for display.
        
        Args:
            path: Path from knowledge graph
            
        Returns:
            Formatted path string
        """
        path_parts = []
        
        for step in path[1:-1]:  # Skip first and last (they are the query entities)
            entity = step.get("entity", {})
            relation = step.get("relation", {})
            
            if entity and relation:
                path_parts.append(f"{relation['type']} {entity['name']}")
            elif entity:
                path_parts.append(entity["name"])
        
        return " → ".join(path_parts) if path_parts else "directly connected"
    
    def query_needs_reasoning(self, query: str) -> bool:
        """
        Determine if query needs reasoning based on complexity.
        
        Args:
            query: User query
            
        Returns:
            Whether query needs reasoning
        """
        # Check for complexity indicators
        complexity_indicators = [
            "why", "how", "explain", "reason", "analyze", "compare", "contrast",
            "difference", "similar", "relationship", "connect", "cause", "effect"
        ]
        
        query_lower = query.lower()
        for indicator in complexity_indicators:
            if indicator in query_lower:
                return True
        
        # Check for multiple question marks or multi-part questions
        if query.count("?") > 1 or ";" in query:
            return True
        
        # Check length - longer queries often require more complex reasoning
        if len(query.split()) > 15:
            return True
        
        return False
    
    def get_standard_prompt_template(self) -> str:
        """
        Get standard prompt template.
        
        Returns:
            Prompt template string
        """
        return """
        Answer the following question based on the provided context.
        If the context doesn't contain enough information, say so.
        
        Context:
        {context}
        
        Question: {query}
        
        Answer:
        """
    
    def get_reasoning_prompt_template(self) -> str:
        """
        Get reasoning prompt template.
        
        Returns:
            Prompt template string with reasoning steps
        """
        return """
        Answer the following question based on the provided context.
        Think step-by-step:
        
        1. Analyze what the question is asking for
        2. Identify the relevant information from the context
        3. Consider relationships between key concepts
        4. Form a logical chain of reasoning
        5. Provide a clear and concise answer
        
        Context:
        {context}
        
        Question: {query}
        
        Reasoning and answer:
        """


class EnhancedRAGSystem:
    """
    Enhanced RAG system with knowledge graph integration.
    """
    
    def __init__(
        self,
        embedder,
        vector_db,
        knowledge_graph,
        llm=None,
        top_k: int = 5
    ):
        """
        Initialize the enhanced RAG system.
        
        Args:
            embedder: Embedding model
            vector_db: Vector database
            knowledge_graph: Knowledge graph
            llm: Language model (optional)
            top_k: Number of documents to retrieve
        """
        self.embedder = embedder
        self.vector_db = vector_db
        self.knowledge_graph = knowledge_graph
        self.llm = llm
        self.top_k = top_k
        
        # Create enhanced retriever
        self.retriever = KnowledgeGraphEnhancedRetrieval(
            vector_db=vector_db,
            knowledge_graph=knowledge_graph,
            top_k=top_k
        )
        
        # Create enhanced generator
        if llm:
            self.generator = KnowledgeGraphEnhancedGenerator(
                llm=llm,
                knowledge_graph=knowledge_graph
            )
    
    def process_query(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        max_tokens: int = 512
    ) -> Dict[str, Any]:
        """
        Process a query using the enhanced RAG system.
        
        Args:
            query: User query
            top_k: Number of documents to retrieve
            filter_dict: Optional filter for documents
            max_tokens: Maximum response length
            
        Returns:
            Response dictionary
        """
        # Get query embedding
        query_embedding = self.embedder.embed(query)
        
        # Extract query entities
        query_entities = self.retriever.extract_entities_from_query(query)
        
        # Retrieve documents
        retrieved_docs = self.retriever.retrieve(
            query=query,
            query_embedding=query_embedding,
            top_k=top_k,
            filter_dict=filter_dict
        )
        
        # Extract contexts from retrieved documents
        contexts = [doc["text"] for doc in retrieved_docs]
        
        # Generate response
        if self.llm:
            response_data = self.generator.generate(
                query=query,
                retrieved_contexts=contexts,
                query_entities=query_entities,
                max_tokens=max_tokens
            )
        else:
            response_data = {
                "response": "No language model available for response generation.",
                "used_graph_context": False,
                "used_reasoning": False
            }
        
        # Construct final response
        result = {
            "query": query,
            "response": response_data["response"],
            "retrieved_documents": retrieved_docs,
            "query_entities": query_entities,
            "used_graph_context": response_data.get("used_graph_context", False),
            "used_reasoning": response_data.get("used_reasoning", False)
        }
        
        return result


class RAGEnhancer:
    """
    Integration between RAG system and knowledge graph.
    """
    
    def __init__(
        self,
        rag_engine,
        knowledge_graph=None,
        update_graph_on_add: bool = True
    ):
        """
        Initialize the RAG-Knowledge Graph integration.
        
        Args:
            rag_engine: RAG engine
            knowledge_graph: Knowledge graph (creates a new one if None)
            update_graph_on_add: Whether to update graph when documents are added
        """
        self.rag_engine = rag_engine
        self.update_graph_on_add = update_graph_on_add
        
        # Create knowledge graph if not provided
        if knowledge_graph:
            self.knowledge_graph = knowledge_graph
        else:
            from knowledge_graph.extractor import EnhancedKnowledgeGraph as KnowledgeGraph
            self.knowledge_graph = KnowledgeGraph()
        
        # Create knowledge graph extractor
        from knowledge_graph.extractor import KnowledgeGraphExtractor
        self.kg_extractor = KnowledgeGraphExtractor()
        self.kg_extractor.knowledge_graph = self.knowledge_graph
        
        # Create enhanced RAG system
        self.enhanced_rag = EnhancedRAGSystem(
            embedder=rag_engine.embedder,
            vector_db=rag_engine.vector_db,
            knowledge_graph=self.knowledge_graph,
            llm=rag_engine.llm,
            top_k=rag_engine.top_k
        )
    
    def add_documents(
        self,
        texts: List[str],
        metadata: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Add documents to both RAG engine and knowledge graph.
        
        Args:
            texts: List of document texts
            metadata: Optional metadata for documents
            
        Returns:
            List of document IDs
        """
        # Add to RAG engine
        doc_ids = self.rag_engine.add_documents(texts, metadata)
        
        # Update knowledge graph if enabled
        if self.update_graph_on_add:
            self.kg_extractor.process_document_chunks(texts, metadata)
        
        return doc_ids
    
    def process_query(
        self,
        query: str,
        top_k: Optional[int] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        max_tokens: int = 512,
        use_enhanced_rag: bool = True
    ) -> Dict[str, Any]:
        """
        Process a query using either standard or enhanced RAG.
        
        Args:
            query: User query
            top_k: Number of documents to retrieve
            filter_dict: Optional filter for documents
            max_tokens: Maximum response length
            use_enhanced_rag: Whether to use enhanced RAG with knowledge graph
            
        Returns:
            Response dictionary
        """
        if use_enhanced_rag:
            return self.enhanced_rag.process_query(
                query=query,
                top_k=top_k,
                filter_dict=filter_dict,
                max_tokens=max_tokens
            )
        else:
            return self.rag_engine.generate_response(
                query=query,
                top_k=top_k,
                filter_dict=filter_dict,
                max_tokens=max_tokens
            )
    
    def build_knowledge_graph(self, reset: bool = False) -> None:
        """
        Build or rebuild the knowledge graph from documents in RAG engine.
        
        Args:
            reset: Whether to reset existing knowledge graph
        """
        if reset:
            self.knowledge_graph.clear()
            self.kg_extractor.reset()
        
        # Get all documents from vector database
        documents = []
        metadata = []
        
        # Access vector database through RAG engine
        if hasattr(self.rag_engine, "vector_db") and hasattr(self.rag_engine.vector_db, "documents"):
            for doc_id, doc in self.rag_engine.vector_db.documents.items():
                documents.append(doc.text)
                metadata.append(doc.metadata)
        
        if not documents:
            logger.warning("No documents found in RAG engine")
            return
        
        logger.info(f"Building knowledge graph from {len(documents)} documents")
        
        # Process documents
        self.kg_extractor.process_document_chunks(documents, metadata)
        
        logger.info("Knowledge graph built successfully")
    
    def get_knowledge_graph(self):
        """
        Get the knowledge graph.
        
        Returns:
            Knowledge graph object
        """
        return self.knowledge_graph
    def generate_knowledge_graph_summary(self) -> Dict[str, Any]:
        """
        Generate a summary of the knowledge graph.
        
        Returns:
            Dictionary with summary information
        """
        # Basic statistics
        entity_count = len(self.knowledge_graph.entities)
        relation_count = len(self.knowledge_graph.relations)
        
        # Get entity types
        entity_types = {}
        for entity in self.knowledge_graph.entities.values():
            entity_type = entity["type"]
            if entity_type not in entity_types:
                entity_types[entity_type] = 0
            entity_types[entity_type] += 1
        
        # Get relation types
        relation_types = {}
        for relation in self.knowledge_graph.relations.values():
            relation_type = relation["type"]
            if relation_type not in relation_types:
                relation_types[relation_type] = 0
            relation_types[relation_type] += 1
        
        # Get key entities
        key_entities = []
        try:
            import networkx as nx
            centrality = nx.degree_centrality(self.knowledge_graph.graph)
            
            # Get top entities by centrality
            top_entities = sorted(
                [(entity_id, centrality[entity_id]) for entity_id in centrality],
                key=lambda x: x[1],
                reverse=True
            )[:10]
            
            for entity_id, score in top_entities:
                if entity_id in self.knowledge_graph.entities:
                    entity = self.knowledge_graph.entities[entity_id]
                    key_entities.append({
                        "name": entity["name"],
                        "type": entity["type"],
                        "centrality": score
                    })
        except Exception as e:
            logger.error(f"Error calculating centrality: {e}")
            pass
        
        return {
            "entity_count": entity_count,
            "relation_count": relation_count,
            "entity_types": entity_types,
            "relation_types": relation_types,
            "key_entities": key_entities
        }
    
    def visualize_graph(self, max_nodes: int = 50) -> Dict[str, Any]:
        """
        Generate data for graph visualization.
        
        Args:
            max_nodes: Maximum number of nodes to include
            
        Returns:
            Dictionary with graph visualization data
        """
        # Node colors by type
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
        links = []
        
        # Get key entities first
        try:
            import networkx as nx
            centrality = nx.degree_centrality(self.knowledge_graph.graph)
            
            # Get top entities by centrality
            top_entities = sorted(
                [(entity_id, centrality[entity_id]) for entity_id in centrality],
                key=lambda x: x[1],
                reverse=True
            )[:max_nodes]
            
            # Create nodes
            for entity_id, score in top_entities:
                if entity_id in self.knowledge_graph.entities:
                    entity = self.knowledge_graph.entities[entity_id]
                    
                    # Get color based on type
                    entity_type = entity["type"]
                    color = node_colors.get(entity_type, node_colors["Other"])
                    
                    nodes.append({
                        "id": entity_id,
                        "name": entity["name"],
                        "type": entity_type,
                        "color": color,
                        "size": 5 + score * 15  # Size based on centrality
                    })
            
            # Create edges between these entities
            node_ids = [node["id"] for node in nodes]
            
            for relation in self.knowledge_graph.relations.values():
                source_id = relation["source"]
                target_id = relation["target"]
                
                if source_id in node_ids and target_id in node_ids:
                    links.append({
                        "source": source_id,
                        "target": target_id,
                        "type": relation["type"]
                    })
        except Exception as e:
            logger.error(f"Error generating visualization data: {e}")
        
        return {
            "nodes": nodes,
            "links": links
        }