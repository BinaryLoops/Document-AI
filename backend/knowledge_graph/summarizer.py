"""
Knowledge Graph-based document summarization for enhanced understanding and retrieval.
"""

import logging
import re
from typing import List, Dict, Any, Optional, Tuple, Union, Set
from collections import defaultdict

# Configure logging
logger = logging.getLogger(__name__)


class KnowledgeGraphSummarizer:
    """
    Summarize documents using knowledge graph-based extraction techniques.
    """
    
    def __init__(
        self,
        knowledge_graph,
        llm=None,
        min_concept_relevance: float = 0.3,
        max_concepts: int = 10,
        max_relations: int = 15
    ):
        """
        Initialize the knowledge graph summarizer.
        
        Args:
            knowledge_graph: Knowledge graph
            llm: Language model for generation (optional)
            min_concept_relevance: Minimum relevance for concepts
            max_concepts: Maximum number of concepts to include
            max_relations: Maximum number of relations to include
        """
        self.knowledge_graph = knowledge_graph
        self.llm = llm
        self.min_concept_relevance = min_concept_relevance
        self.max_concepts = max_concepts
        self.max_relations = max_relations
    
    def summarize_document(
        self,
        doc_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        max_length: int = 500
    ) -> Dict[str, Any]:
        """
        Generate a summary of a document using knowledge graph insights.
        
        Args:
            doc_text: Document text
            metadata: Optional document metadata
            max_length: Maximum summary length
            
        Returns:
            Dictionary containing summary and extracted information
        """
        # Extract entities and concepts from document
        doc_entities = self.extract_document_entities(doc_text)
        
        # Find key concepts based on knowledge graph
        key_concepts = self.extract_key_concepts(doc_entities)
        
        # Extract important relations
        key_relations = self.extract_key_relations(key_concepts)
        
        # Generate structured summary
        structured_summary = self.generate_structured_summary(
            doc_text=doc_text,
            key_concepts=key_concepts,
            key_relations=key_relations
        )
        
        # Generate natural language summary if LLM is available
        if self.llm:
            nl_summary = self.generate_nl_summary(
                doc_text=doc_text,
                structured_summary=structured_summary,
                max_length=max_length
            )
        else:
            nl_summary = self.create_fallback_summary(structured_summary)
        
        # Return combined result
        return {
            "summary": nl_summary,
            "structured_summary": structured_summary,
            "key_concepts": key_concepts,
            "key_relations": key_relations,
            "length": len(nl_summary)
        }
    
    def extract_document_entities(self, doc_text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from document text.
        
        Args:
            doc_text: Document text
            
        Returns:
            List of entity dictionaries with relevance scores
        """
        # Check for mentions of known entities in knowledge graph
        doc_entities = []
        
        # Calculate term frequency in document
        term_freq = defaultdict(int)
        
        # Normalize document text for better matching
        doc_lower = doc_text.lower()
        words = re.findall(r'\b\w+\b', doc_lower)
        
        for word in words:
            if len(word) > 2:  # Only count meaningful words
                term_freq[word] += 1
        
        # Calculate term frequency normalized scores
        total_words = max(1, len(words))
        term_freq_norm = {term: count / total_words for term, count in term_freq.items()}
        
        # Check for each entity in the knowledge graph
        for entity_id, entity in self.knowledge_graph.entities.items():
            entity_name = entity["name"]
            entity_lower = entity_name.lower()
            
            # Check if entity name appears in document
            if entity_lower in doc_lower:
                # Count occurrences
                occurrences = doc_lower.count(entity_lower)
                
                # Calculate position score (earlier is better)
                first_pos = doc_lower.find(entity_lower)
                pos_score = 1.0 - (first_pos / max(1, len(doc_lower)))
                
                # Calculate relevance score
                relevance = min(1.0, (
                    (occurrences / max(1, len(doc_lower) / 100)) * 0.5 +  # Frequency
                    pos_score * 0.3 +  # Position
                    term_freq_norm.get(entity_lower.split()[0], 0) * 0.2  # Term frequency
                ))
                
                doc_entities.append({
                    "id": entity_id,
                    "name": entity_name,
                    "type": entity["type"],
                    "relevance": relevance,
                    "occurrences": occurrences,
                    "position": first_pos
                })
        
        # Sort by relevance
        doc_entities.sort(key=lambda x: x["relevance"], reverse=True)
        
        return doc_entities
    
    def extract_key_concepts(self, doc_entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract key concepts from document entities.
        
        Args:
            doc_entities: List of document entities
            
        Returns:
            List of key concepts
        """
        if not doc_entities:
            return []
        
        # Filter entities by relevance
        relevant_entities = [
            entity for entity in doc_entities 
            if entity["relevance"] >= self.min_concept_relevance
        ]
        
        # Get centrality from knowledge graph
        try:
            import networkx as nx
            centrality = nx.degree_centrality(self.knowledge_graph.graph)
        except:
            centrality = {}
        
        # Calculate concept scores (combine relevance and centrality)
        key_concepts = []
        
        for entity in relevant_entities:
            entity_id = entity["id"]
            
            # Get centrality score
            cent_score = centrality.get(entity_id, 0)
            
            # Combined score
            combined_score = entity["relevance"] * 0.7 + cent_score * 0.3
            
            key_concepts.append({
                "id": entity_id,
                "name": entity["name"],
                "type": entity["type"],
                "relevance": entity["relevance"],
                "centrality": cent_score,
                "score": combined_score
            })
        
        # Sort by score and limit
        key_concepts.sort(key=lambda x: x["score"], reverse=True)
        key_concepts = key_concepts[:self.max_concepts]
        
        return key_concepts
    
    def extract_key_relations(self, key_concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract key relations between concepts.
        
        Args:
            key_concepts: List of key concepts
            
        Returns:
            List of key relations
        """
        if not key_concepts or len(key_concepts) < 2:
            return []
        
        key_relations = []
        concept_ids = [concept["id"] for concept in key_concepts]
        
        # Find relations between key concepts
        for i, concept1 in enumerate(key_concepts):
            for concept2 in key_concepts[i+1:]:
                # Get entities from knowledge graph
                entity1_id = concept1["id"]
                entity2_id = concept2["id"]
                
                # Find paths between entities
                paths = self.knowledge_graph.find_path(entity1_id, entity2_id, max_hops=2)
                
                if paths:
                    # Get the shortest path
                    path = paths[0]
                    
                    # Extract relation information
                    relation = None
                    for step in path:
                        if step.get("relation") and step["relation"].get("type"):
                            relation = step["relation"]
                            break
                    
                    if relation:
                        rel_type = relation.get("type", "related_to")
                        rel_confidence = relation.get("confidence", 0.5)
                        
                        key_relations.append({
                            "source": concept1["name"],
                            "source_id": entity1_id,
                            "target": concept2["name"],
                            "target_id": entity2_id,
                            "type": rel_type,
                            "confidence": rel_confidence,
                            "path_length": len(path)
                        })
        
        # Sort by confidence and path length (shorter is better)
        key_relations.sort(key=lambda x: (x["confidence"], -x["path_length"]), reverse=True)
        key_relations = key_relations[:self.max_relations]
        
        return key_relations
    
    def generate_structured_summary(
        self,
        doc_text: str,
        key_concepts: List[Dict[str, Any]],
        key_relations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Generate a structured summary of the document.
        
        Args:
            doc_text: Document text
            key_concepts: List of key concepts
            key_relations: List of key relations
            
        Returns:
            Structured summary dictionary
        """
        # Extract document metadata
        doc_length = len(doc_text)
        word_count = len(re.findall(r'\b\w+\b', doc_text))
        
        # Identify main topics based on concept types
        main_topics = []
        for concept in key_concepts[:3]:  # Top 3 concepts
            if concept["score"] > 0.5:
                main_topics.append(concept["name"])
        
        # Group concepts by type
        concepts_by_type = defaultdict(list)
        for concept in key_concepts:
            concepts_by_type[concept["type"]].append(concept["name"])
        
        # Extract document sections if possible
        sections = self.identify_document_sections(doc_text)
        
        # Create structured summary
        structured_summary = {
            "main_topics": main_topics,
            "key_concepts": [concept["name"] for concept in key_concepts],
            "key_relations": [f"{r['source']} {r['type']} {r['target']}" for r in key_relations],
            "concepts_by_type": dict(concepts_by_type),
            "document_length": doc_length,
            "word_count": word_count,
            "sections": sections
        }
        
        return structured_summary
    
    def identify_document_sections(self, doc_text: str) -> List[Dict[str, Any]]:
        """
        Attempt to identify document sections.
        
        Args:
            doc_text: Document text
            
        Returns:
            List of section dictionaries
        """
        sections = []
        
        # Look for section headers
        header_patterns = [
            r'#+\s+(.+)',  # Markdown headers
            r'^([A-Z][A-Z\s]{2,})',  # ALL CAPS HEADERS
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,5}:)',  # Title Case Headers with colon
            r'^\d+\.\s+([A-Z].+)',  # Numbered sections
        ]
        
        section_matches = []
        for pattern in header_patterns:
            for match in re.finditer(pattern, doc_text, re.MULTILINE):
                section_title = match.group(1).strip()
                start_pos = match.start()
                section_matches.append((start_pos, section_title))
        
        # Sort by position
        section_matches.sort()
        
        # Extract section content
        for i, (start_pos, title) in enumerate(section_matches):
            # Determine section end
            if i < len(section_matches) - 1:
                end_pos = section_matches[i+1][0]
            else:
                end_pos = len(doc_text)
            
            # Extract section content (excluding the header)
            header_end = doc_text.find('\n', start_pos)
            if header_end == -1:
                header_end = start_pos + len(title) + 1
            
            content = doc_text[header_end:end_pos].strip()
            
            # Add to sections
            sections.append({
                "title": title,
                "content_length": len(content),
                "position": i
            })
        
        return sections
    
    def generate_nl_summary(
        self,
        doc_text: str,
        structured_summary: Dict[str, Any],
        max_length: int = 500
    ) -> str:
        """
        Generate a natural language summary using the LLM.
        
        Args:
            doc_text: Document text
            structured_summary: Structured summary
            max_length: Maximum summary length
            
        Returns:
            Natural language summary
        """
        if not self.llm:
            return self.create_fallback_summary(structured_summary)
        
        # Prepare the prompt template
        prompt_template = """
        Generate a concise summary of the following document based on key concepts and relationships.
        
        Key Concepts:
        {concepts}
        
        Key Relationships:
        {relationships}
        
        Main Topics:
        {topics}
        
        Document Content:
        {content}
        
        Create a coherent summary that explains these key concepts and their relationships in the context of the document.
        The summary should be {max_length} characters or less and should capture the main points of the document.
        
        Summary:
        """
        
        # Format the prompt
        prompt = prompt_template.format(
            concepts=", ".join([concept["name"] for concept in structured_summary["key_concepts"]]),
            relationships="\n".join([f"- {rel}" for rel in structured_summary["key_relations"]]),
            topics=", ".join(structured_summary["main_topics"]),
            content=doc_text[:5000] if len(doc_text) > 5000 else doc_text,  # Limit content length
            max_length=max_length
        )
        
        # Generate summary
        summary = self.llm.generate_response(prompt, max_tokens=max_length)
        
        return summary
    
    def create_fallback_summary(self, structured_summary: Dict[str, Any]) -> str:
        """
        Create a simple summary without using an LLM.
        
        Args:
            structured_summary: Structured summary
            
        Returns:
            Simple natural language summary
        """
        # Create a simple summary based on structured data
        summary_parts = []
        
        # Main topics
        if structured_summary["main_topics"]:
            topics = ", ".join(structured_summary["main_topics"])
            summary_parts.append(f"This document is primarily about {topics}.")
        
        # Key concepts by type
        for concept_type, concepts in structured_summary["concepts_by_type"].items():
            if concepts and len(concepts) <= 5:
                concept_list = ", ".join(concepts)
                summary_parts.append(f"Key {concept_type}s mentioned: {concept_list}.")
        
        # Key relations (limited)
        if structured_summary["key_relations"]:
            relations = structured_summary["key_relations"][:3]
            relation_text = " ".join([f"{rel}." for rel in relations])
            summary_parts.append(f"Important relationships: {relation_text}")
        
        # Document structure
        if structured_summary["sections"]:
            section_count = len(structured_summary["sections"])
            summary_parts.append(f"The document contains {section_count} sections.")
        
        summary = " ".join(summary_parts)
        return summary
    
    def summarize_multiple_documents(
        self,
        documents: List[str],
        metadata_list: Optional[List[Dict[str, Any]]] = None,
        max_length: int = 800
    ) -> Dict[str, Any]:
        """
        Generate a summary of multiple related documents.
        
        Args:
            documents: List of document texts
            metadata_list: Optional list of metadata for each document
            max_length: Maximum summary length
            
        Returns:
            Dictionary containing summary and extracted information
        """
        # Summarize each document individually
        document_summaries = []
        for i, doc_text in enumerate(documents):
            metadata = metadata_list[i] if metadata_list and i < len(metadata_list) else None
            summary = self.summarize_document(doc_text, metadata, max_length=max_length//2)
            document_summaries.append(summary)
        
        # Collect all key concepts and relations
        all_concepts = []
        all_relations = []
        
        for summary in document_summaries:
            all_concepts.extend(summary["key_concepts"])
            all_relations.extend(summary["key_relations"])
        
        # Deduplicate and sort concepts
        unique_concepts = {}
        for concept in all_concepts:
            concept_id = concept["id"]
            if concept_id not in unique_concepts or concept["score"] > unique_concepts[concept_id]["score"]:
                unique_concepts[concept_id] = concept
        
        # Sort by score
        sorted_concepts = sorted(unique_concepts.values(), key=lambda x: x["score"], reverse=True)
        top_concepts = sorted_concepts[:self.max_concepts]
        
        # Deduplicate relations
        unique_relations = {}
        for relation in all_relations:
            # Create a key for the relation
            rel_key = f"{relation['source_id']}_{relation['type']}_{relation['target_id']}"
            
            if rel_key not in unique_relations or relation["confidence"] > unique_relations[rel_key]["confidence"]:
                unique_relations[rel_key] = relation
        
        # Sort by confidence
        sorted_relations = sorted(unique_relations.values(), key=lambda x: x["confidence"], reverse=True)
        top_relations = sorted_relations[:self.max_relations]
        
        # Create a combined structured summary
        combined_summary = {
            "main_topics": [],
            "key_concepts": top_concepts,
            "key_relations": top_relations,
            "document_count": len(documents),
            "individual_summaries": document_summaries
        }
        
        # Extract main topics from top concepts
        for concept in top_concepts[:3]:
            if concept["score"] > 0.5:
                combined_summary["main_topics"].append(concept["name"])
        
        # Generate a natural language summary
        if self.llm:
            nl_summary = self.generate_multi_doc_summary(documents, combined_summary, max_length)
        else:
            nl_summary = self.create_fallback_multi_summary(combined_summary)
        
        return {
            "summary": nl_summary,
            "structured_summary": combined_summary,
            "length": len(nl_summary)
        }
    
    def generate_multi_doc_summary(
        self,
        documents: List[str],
        combined_summary: Dict[str, Any],
        max_length: int = 800
    ) -> str:
        """
        Generate a natural language summary for multiple documents.
        
        Args:
            documents: List of document texts
            combined_summary: Combined structured summary
            max_length: Maximum summary length
            
        Returns:
            Natural language summary
        """
        # Prepare the prompt template
        prompt_template = """
        Generate a comprehensive summary of multiple related documents based on key concepts and relationships.
        
        Key Concepts:
        {concepts}
        
        Key Relationships:
        {relationships}
        
        Main Topics:
        {topics}
        
        Document Excerpts:
        {excerpts}
        
        Create a coherent summary that explains these key concepts and their relationships across the documents.
        The summary should be {max_length} characters or less and should synthesize the main points across all documents.
        
        Summary:
        """
        
        # Extract concept names
        concept_names = [concept["name"] for concept in combined_summary["key_concepts"][:10]]
        
        # Format relation strings
        relation_strings = []
        for relation in combined_summary["key_relations"][:10]:
            rel_str = f"{relation['source']} {relation['type']} {relation['target']}"
            relation_strings.append(rel_str)
        
        # Prepare document excerpts (first 200 chars of each)
        excerpts = []
        for i, doc in enumerate(documents):
            excerpt = doc[:200] + "..." if len(doc) > 200 else doc
            excerpts.append(f"Document {i+1}: {excerpt}")
        
        # Format the prompt
        prompt = prompt_template.format(
            concepts=", ".join(concept_names),
            relationships="\n".join([f"- {rel}" for rel in relation_strings]),
            topics=", ".join(combined_summary["main_topics"]),
            excerpts="\n\n".join(excerpts[:5]),  # Limit to 5 documents
            max_length=max_length
        )
        
        # Generate summary
        summary = self.llm.generate_response(prompt, max_tokens=max_length)
        
        return summary
    
    def create_fallback_multi_summary(self, combined_summary: Dict[str, Any]) -> str:
        """
        Create a simple multi-document summary without using an LLM.
        
        Args:
            combined_summary: Combined structured summary
            
        Returns:
            Simple natural language summary
        """
        # Create a simple summary based on structured data
        summary_parts = []
        
        # Document count
        doc_count = combined_summary["document_count"]
        summary_parts.append(f"This summary covers {doc_count} related documents.")
        
        # Main topics
        if combined_summary["main_topics"]:
            topics = ", ".join(combined_summary["main_topics"])
            summary_parts.append(f"The main topics across these documents are {topics}.")
        
        # Key concepts
        concept_names = [concept["name"] for concept in combined_summary["key_concepts"][:7]]
        if concept_names:
            concepts_text = ", ".join(concept_names)
            summary_parts.append(f"Key concepts discussed: {concepts_text}.")
        
        # Key relations (limited)
        relation_texts = []
        for relation in combined_summary["key_relations"][:3]:
            rel_text = f"{relation['source']} {relation['type']} {relation['target']}"
            relation_texts.append(rel_text)
        
        if relation_texts:
            relations = " ".join([f"{rel}." for rel in relation_texts])
            summary_parts.append(f"Important relationships identified: {relations}")
        
        # Individual documents
        for i, summary in enumerate(combined_summary["individual_summaries"][:3]):
            summary_parts.append(f"Document {i+1} focuses on {', '.join(summary['structured_summary']['main_topics'])}.")
        
        summary = " ".join(summary_parts)
        return summary