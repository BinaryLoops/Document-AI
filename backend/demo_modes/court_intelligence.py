"""
Court Intelligence Demo Mode.
P15 requirement: Specialized interface for court case analysis.
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class CourtIntelligence:
    """
    Court Intelligence mode for analyzing court case bundles.
    Leverages existing modules for court-specific workflows.
    """
    
    def __init__(
        self,
        case_manager,
        comparison_engine,
        timeline_extractor,
        kg_populator,
        rag_engine
    ):
        """
        Initialize Court Intelligence mode.
        
        Args:
            case_manager: CaseManager instance
            comparison_engine: DocumentComparison instance
            timeline_extractor: TimelineExtractor instance
            kg_populator: KnowledgeGraphAutoPopulator instance
            rag_engine: RAG engine instance
        """
        self.case_manager = case_manager
        self.comparison = comparison_engine
        self.timeline = timeline_extractor
        self.kg = kg_populator
        self.rag = rag_engine
        logger.info("CourtIntelligence mode initialized")
    
    def analyze_case_bundle(
        self,
        case_id: str,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Comprehensive analysis of a court case bundle.
        
        Args:
            case_id: Case identifier
            documents: List of case documents
            
        Returns:
            Complete case analysis
        """
        logger.info(f"Analyzing court case: {case_id}")
        
        # Get case details
        case_info = self.case_manager.get_case(case_id)
        
        # Extract parties
        parties = self._extract_parties(documents)
        
        # Build timeline
        timeline = self.timeline.extract_timeline(documents)
        
        # Find inconsistencies
        inconsistencies = self.comparison.compare_documents(documents)
        
        # Generate case summary
        summary = self._generate_case_summary(documents)
        
        # Build knowledge graph
        self._populate_case_graph(case_id, documents)
        
        return {
            'case_id': case_id,
            'case_info': case_info,
            'parties': parties,
            'document_count': len(documents),
            'timeline': timeline,
            'inconsistencies': inconsistencies,
            'summary': summary,
            'key_findings': self._extract_key_findings(documents, timeline, inconsistencies)
        }
    
    def search_case_law(
        self,
        query: str,
        case_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search within case documents.
        
        Args:
            query: Search query
            case_id: Optional case filter
            
        Returns:
            Search results with evidence
        """
        # Build filter for case if provided
        filter_dict = {'case_id': case_id} if case_id else None
        
        # Perform search
        results = self.rag.search(
            query=query,
            search_type='hybrid',
            filter_dict=filter_dict,
            top_k=10
        )
        
        return {
            'query': query,
            'results': results,
            'case_id': case_id
        }
    
    def _extract_parties(
        self,
        documents: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """Extract parties involved in the case."""
        parties = {
            'plaintiffs': set(),
            'defendants': set(),
            'judges': set(),
            'advocates': set()
        }
        
        for doc in documents:
            fields = doc.get('extracted_fields', [])
            
            for field in fields:
                field_name = field.get('field', '').lower()
                value = field.get('value')
                
                if value and field.get('confidence', 0) > 0.7:
                    if 'plaintiff' in field_name:
                        parties['plaintiffs'].add(str(value))
                    elif 'defendant' in field_name:
                        parties['defendants'].add(str(value))
                    elif 'judge' in field_name:
                        parties['judges'].add(str(value))
                    elif 'advocate' in field_name:
                        parties['advocates'].add(str(value))
        
        return {k: list(v) for k, v in parties.items()}
    
    def _generate_case_summary(
        self,
        documents: List[Dict[str, Any]]
    ) -> str:
        """Generate case summary using RAG."""
        # Combine document texts
        texts = []
        for doc in documents:
            chunks = doc.get('chunks', [])
            if chunks:
                texts.extend(chunks[:3])  # First 3 chunks per doc
        
        context = ' '.join(texts)[:3000]
        
        # Generate summary
        prompt = f"""Summarize this court case based on the provided documents:

{context}

Provide a concise summary including:
1. Case type and nature
2. Main parties involved
3. Key issues or claims
4. Current status or outcome (if mentioned)

Summary:"""
        
        try:
            summary = self.rag._generate_llm_response(prompt, max_tokens=300)
            return summary
        except Exception as e:
            logger.error(f"Failed to generate summary: {e}")
            return "Summary generation failed"
    
    def _extract_key_findings(
        self,
        documents: List[Dict[str, Any]],
        timeline: Dict[str, Any],
        inconsistencies: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract key findings from analysis."""
        findings = []
        
        # Timeline findings
        if timeline.get('total_events', 0) > 0:
            findings.append(
                f"Case spans {timeline.get('timeline_span_days', 0)} days with "
                f"{timeline['total_events']} documented events"
            )
        
        # Inconsistency findings
        if inconsistencies:
            major = len([i for i in inconsistencies if i.get('severity') == 'MAJOR'])
            if major > 0:
                findings.append(f"⚠ {major} major inconsistencies require attention")
        
        # Document completeness
        doc_types = set(doc.get('document_type', 'Unknown') for doc in documents)
        findings.append(f"Case contains {len(doc_types)} different document types")
        
        return findings
    
    def _populate_case_graph(
        self,
        case_id: str,
        documents: List[Dict[str, Any]]
    ):
        """Populate knowledge graph for the case."""
        document_ids = [doc.get('document_id') for doc in documents]
        self.kg.populate_case_relationships(case_id, document_ids)
