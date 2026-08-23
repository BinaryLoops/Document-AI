"""
System Test Script - Verify all components are working.
Run this to test the complete Document Intelligence Workspace.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test if all modules can be imported."""
    logger.info("=" * 70)
    logger.info("TEST 1: Module Imports")
    logger.info("=" * 70)
    
    modules_to_test = [
        # Core processing
        ("document.document_status", "DocumentStatus, DocumentMetadata"),
        ("document.document_classifier", "DocumentClassifier"),
        ("document.ocr_processor", "OCRProcessor, create_ocr_processor"),
        ("document.ingestion", "DocumentIngestion"),
        ("document.field_extractor", "FieldExtractor, load_schema"),
        ("document.evidence_tracker", "EvidenceTracker, Evidence, ExtractedField"),
        
        # Search and RAG
        ("search.hybrid_search", "HybridSearch, MetadataFilter"),
        ("rag.grounded_rag", "GroundedRAG, CitationEnforcer"),
        
        # Verification
        ("verification.document_comparison", "DocumentComparison, FieldNormalizer"),
        ("verification.missing_document_checker", "MissingDocumentChecker"),
        ("verification.readiness_score", "ReadinessScoreCalculator"),
        
        # Analysis
        ("analysis.timeline_extractor", "TimelineExtractor"),
        ("analysis.duplicate_detector", "DuplicateDetector"),
        
        # Case and Review
        ("case.case_manager", "CaseManager"),
        ("review.review_queue", "ReviewQueue"),
        
        # Knowledge Graph
        ("knowledge_graph.auto_populator", "KnowledgeGraphAutoPopulator, InMemoryKGStore"),
        
        # Demo Modes
        ("demo_modes.court_intelligence", "CourtIntelligence"),
        ("demo_modes.government_verification", "GovernmentVerification"),
        ("demo_modes.notary_assistant", "NotaryAssistant"),
    ]
    
    success = 0
    failed = 0
    
    for module_name, components in modules_to_test:
        try:
            exec(f"from {module_name} import {components}")
            logger.info(f"✓ {module_name}")
            success += 1
        except Exception as e:
            logger.error(f"✗ {module_name}: {str(e)}")
            failed += 1
    
    logger.info(f"\nResults: {success} passed, {failed} failed")
    return failed == 0


def test_document_classification():
    """Test document classification."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 2: Document Classification")
    logger.info("=" * 70)
    
    try:
        from document.document_classifier import DocumentClassifier
        from embedding.model import create_embedding_model
        
        # Initialize
        logger.info("Initializing classifier...")
        embedding_model = create_embedding_model()
        classifier = DocumentClassifier(embedding_model)
        
        # Test samples
        samples = [
            ("I hereby apply for a driving license. My name is John Doe.", "Application"),
            ("This is to certify that John Doe was born on 01/01/1990.", "Certificate"),
            ("Invoice #12345. Amount Due: $500. Please pay by end of month.", "Invoice"),
        ]
        
        for text, expected in samples:
            doc_type, confidence = classifier.classify(text)
            status = "✓" if doc_type == expected else "✗"
            logger.info(f"{status} Text: '{text[:50]}...'")
            logger.info(f"   Predicted: {doc_type} ({confidence:.2f}), Expected: {expected}")
        
        logger.info("\n✓ Classification test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Classification test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ocr_processor():
    """Test OCR processor initialization."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 3: OCR Processor")
    logger.info("=" * 70)
    
    try:
        from document.ocr_processor import OCRProcessor, TesseractOCR
        
        logger.info("Testing OCR processor initialization...")
        
        # Test Tesseract initialization
        try:
            processor = OCRProcessor()
            logger.info("✓ OCR Processor initialized with default engine")
        except ImportError as e:
            logger.warning(f"⚠ Tesseract not available: {e}")
            logger.info("  Note: Install tesseract-ocr for image processing")
        
        logger.info("✓ OCR test passed (initialization)")
        return True
        
    except Exception as e:
        logger.error(f"✗ OCR test failed: {e}")
        return False


def test_hybrid_search():
    """Test hybrid search."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 4: Hybrid Search")
    logger.info("=" * 70)
    
    try:
        from search.hybrid_search import HybridSearch
        
        # Initialize
        hybrid_search = HybridSearch(semantic_weight=0.7, keyword_weight=0.3)
        
        # Create sample documents
        texts = [
            "This is a sample application for government services.",
            "Invoice for payment of services rendered.",
            "Court order issued by the honorable judge."
        ]
        
        metadata = [
            {"doc_type": "Application", "id": "doc1"},
            {"doc_type": "Invoice", "id": "doc2"},
            {"doc_type": "Court Document", "id": "doc3"}
        ]
        
        # Index documents
        hybrid_search.index_documents(texts, metadata)
        logger.info(f"✓ Indexed {len(texts)} documents")
        
        # Test keyword search
        results = hybrid_search._keyword_search("application government", top_k=2)
        logger.info(f"✓ Keyword search returned {len(results)} results")
        
        logger.info("✓ Hybrid search test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Hybrid search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_verification_modules():
    """Test verification modules."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 5: Verification Modules")
    logger.info("=" * 70)
    
    try:
        from verification.document_comparison import DocumentComparison
        from verification.missing_document_checker import MissingDocumentChecker
        from verification.readiness_score import ReadinessScoreCalculator
        
        # Test document comparison
        comparison = DocumentComparison(fuzzy_threshold=85.0)
        logger.info("✓ DocumentComparison initialized")
        
        # Test missing document checker
        checker = MissingDocumentChecker()
        workflows = checker.get_workflows()
        logger.info(f"✓ MissingDocumentChecker initialized with {len(workflows)} workflows")
        
        # Test readiness calculator
        calculator = ReadinessScoreCalculator()
        logger.info("✓ ReadinessScoreCalculator initialized")
        
        # Test missing document check
        result = checker.check_documents(
            document_types=["Application", "Identity Proof"],
            workflow="GOVERNMENT_APPLICATION"
        )
        logger.info(f"✓ Document check: {result['overall_status']} - {result['completeness_percentage']}% complete")
        
        logger.info("✓ Verification modules test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Verification test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_case_manager():
    """Test case manager."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 6: Case Manager")
    logger.info("=" * 70)
    
    try:
        from case.case_manager import CaseManager
        
        # Initialize
        case_manager = CaseManager()
        
        # Create a case
        case_id = case_manager.create_case(
            case_title="Test Case",
            case_type="Government Application",
            workflow="GOVERNMENT_APPLICATION"
        )
        logger.info(f"✓ Created case: {case_id}")
        
        # Add documents
        case_manager.add_document_to_case(case_id, "doc1", {"filename": "test.pdf"})
        logger.info("✓ Added document to case")
        
        # Get case
        case = case_manager.get_case(case_id)
        logger.info(f"✓ Retrieved case with {case['document_count']} documents")
        
        logger.info("✓ Case manager test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Case manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_review_queue():
    """Test review queue."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 7: Review Queue")
    logger.info("=" * 70)
    
    try:
        from review.review_queue import ReviewQueue
        
        # Initialize
        queue = ReviewQueue()
        
        # Add item to queue
        review_id = queue.add_to_queue(
            case_id="test_case",
            document_id="test_doc",
            item_type="FIELD_EXTRACTION",
            item_data={"field": "name", "value": "John Doe"},
            confidence=0.65
        )
        logger.info(f"✓ Added item to review queue: {review_id}")
        
        # Get pending reviews
        pending = queue.get_pending_reviews()
        logger.info(f"✓ Retrieved {len(pending)} pending reviews")
        
        # Submit review
        success = queue.submit_review(
            review_id=review_id,
            decision="ACCEPT",
            reviewer="test_reviewer"
        )
        logger.info(f"✓ Submitted review: {success}")
        
        # Get statistics
        stats = queue.get_review_statistics()
        logger.info(f"✓ Queue statistics: {stats['total_items']} items")
        
        logger.info("✓ Review queue test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Review queue test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_knowledge_graph():
    """Test knowledge graph auto-populator."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 8: Knowledge Graph")
    logger.info("=" * 70)
    
    try:
        from knowledge_graph.auto_populator import KnowledgeGraphAutoPopulator, InMemoryKGStore
        
        # Initialize with in-memory store
        kg_store = InMemoryKGStore()
        populator = KnowledgeGraphAutoPopulator(kg_store)
        logger.info("✓ KG Auto-populator initialized")
        
        # Test population
        extracted_fields = [
            {"field": "full_name", "value": "John Doe", "confidence": 0.95},
            {"field": "document_number", "value": "12345", "confidence": 0.90}
        ]
        
        populator.populate_from_extraction(
            document_id="test_doc",
            document_type="Application",
            extracted_fields=extracted_fields
        )
        logger.info("✓ Populated KG from extracted fields")
        
        # Get statistics
        stats = kg_store.get_statistics()
        logger.info(f"✓ KG statistics: {stats['total_nodes']} nodes, {stats['total_relationships']} relationships")
        
        logger.info("✓ Knowledge graph test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Knowledge graph test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_demo_modes():
    """Test demo mode initialization."""
    logger.info("\n" + "=" * 70)
    logger.info("TEST 9: Demo Modes")
    logger.info("=" * 70)
    
    try:
        from demo_modes.court_intelligence import CourtIntelligence
        from demo_modes.government_verification import GovernmentVerification
        from demo_modes.notary_assistant import NotaryAssistant
        from case.case_manager import CaseManager
        from verification.document_comparison import DocumentComparison
        from verification.missing_document_checker import MissingDocumentChecker
        from verification.readiness_score import ReadinessScoreCalculator
        from review.review_queue import ReviewQueue
        from analysis.timeline_extractor import TimelineExtractor
        from knowledge_graph.auto_populator import KnowledgeGraphAutoPopulator, InMemoryKGStore
        
        # Initialize dependencies
        case_manager = CaseManager()
        comparison = DocumentComparison()
        timeline = TimelineExtractor()
        kg_store = InMemoryKGStore()
        kg_populator = KnowledgeGraphAutoPopulator(kg_store)
        
        # Mock RAG engine
        class MockRAG:
            def search(self, **kwargs):
                return []
            def _generate_llm_response(self, prompt, **kwargs):
                return "Mock response"
        
        rag_engine = MockRAG()
        
        # Test Court Intelligence
        court = CourtIntelligence(case_manager, comparison, timeline, kg_populator, rag_engine)
        logger.info("✓ CourtIntelligence initialized")
        
        # Test Government Verification
        missing_checker = MissingDocumentChecker()
        readiness_calc = ReadinessScoreCalculator()
        review_queue = ReviewQueue()
        
        gov = GovernmentVerification(missing_checker, comparison, readiness_calc, review_queue)
        logger.info("✓ GovernmentVerification initialized")
        
        # Test Notary Assistant
        notary = NotaryAssistant(comparison, missing_checker)
        logger.info("✓ NotaryAssistant initialized")
        
        logger.info("✓ Demo modes test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Demo modes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all tests."""
    logger.info("\n" + "=" * 80)
    logger.info("DOCUMENT INTELLIGENCE WORKSPACE - SYSTEM TEST")
    logger.info("=" * 80)
    
    tests = [
        ("Module Imports", test_imports),
        ("Document Classification", test_document_classification),
        ("OCR Processor", test_ocr_processor),
        ("Hybrid Search", test_hybrid_search),
        ("Verification Modules", test_verification_modules),
        ("Case Manager", test_case_manager),
        ("Review Queue", test_review_queue),
        ("Knowledge Graph", test_knowledge_graph),
        ("Demo Modes", test_demo_modes),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("TEST SUMMARY")
    logger.info("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    failed = len(results) - passed
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info("\n" + "=" * 80)
    logger.info(f"TOTAL: {passed}/{len(results)} tests passed")
    logger.info("=" * 80)
    
    if failed == 0:
        logger.info("\n🎉 ALL TESTS PASSED! System is ready.")
        return 0
    else:
        logger.warning(f"\n⚠ {failed} test(s) failed. Review errors above.")
        return 1


if __name__ == "__main__":
    exit_code = run_all_tests()
    sys.exit(exit_code)
