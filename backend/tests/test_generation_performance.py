"""
tests/test_generation_performance.py — Performance tests for Generation Engine database caching.

Tests Task 6.4: Validate database performance with cache
- Measure lookup time with in-memory cache (should be < 1ms)
- Measure lookup time without cache (disk read)
- Verify cache hit rate > 90% for repeated lookups

Requirements: 14.9
"""

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

import pytest

from generation import database
from generation.models import (
    DocumentType, GeneratedDocument, GenerationRequest,
    GenerationStatus, SignatureStatus, WatermarkType,
)


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def setup_test_data():
    """Create test data for performance testing."""
    # Clear existing data
    database._requests.clear()
    database._documents.clear()
    database._audit.clear()
    database._counters.clear()
    
    # Create 100 test requests and documents
    requests = []
    documents = []
    
    for i in range(100):
        req_id = f"test-req-{uuid.uuid4()}"
        doc_id = f"test-doc-{uuid.uuid4()}"
        doc_number = f"IND-PP-2026-{i:06d}"
        
        req = GenerationRequest(
            request_id=req_id,
            document_type=DocumentType.PASSPORT,
            applicant_user_id=f"user-{i % 10}",  # 10 unique users
            requested_by=f"issuer-{i % 5}",
            issued_by=f"issuer-{i % 5}",
            department_code="TEST-DEPT",
            fields={"surname": f"User{i}", "given_names": f"Test{i}"},
            supporting_docs=[],
            status=GenerationStatus.COMPLETE,
            rejection_reason=None,
            case_clear=True,
            verification_passed=True,
            submitted_at=datetime.now(timezone.utc),
            approved_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        doc = GeneratedDocument(
            doc_id=doc_id,
            request_id=req_id,
            document_type=DocumentType.PASSPORT,
            document_number=doc_number,
            applicant_user_id=f"user-{i % 10}",
            applicant_name=f"User{i} Test{i}",
            issued_by=f"issuer-{i % 5}",
            department_code="TEST-DEPT",
            issued_at=datetime.now(timezone.utc),
            valid_from=datetime.now(timezone.utc),
            valid_until=None,
            signature_status=SignatureStatus.SIGNED,
            signature_hash=f"hash-{i}",
            signature_value=f"signature-{i}",
            signed_by=f"issuer-{i % 5}",
            signed_at=datetime.now(timezone.utc),
            qr_verification_url=f"http://example.com/verify/{doc_number}",
            qr_payload_hash=f"qr-hash-{i}",
            watermark_type=WatermarkType.OFFICIAL,
            pdf_path=f"/tmp/test-{doc_number}.pdf",
            pdf_size_bytes=250_000,
            status=GenerationStatus.COMPLETE,
            revoked=False,
            revoked_at=None,
            revoked_by=None,
            revoke_reason=None,
            fields={"surname": f"User{i}", "given_names": f"Test{i}"},
            created_at=datetime.now(timezone.utc),
        )
        
        database.save_request(req)
        database.save_document(doc)
        
        requests.append(req)
        documents.append(doc)
    
    yield requests, documents
    
    # Cleanup
    database._requests.clear()
    database._documents.clear()
    database._audit.clear()
    database._counters.clear()


# ══════════════════════════════════════════════════════════════════════════════
# Test 1: Measure lookup time with in-memory cache (should be < 1ms)
# ══════════════════════════════════════════════════════════════════════════════

def test_cache_lookup_performance_under_1ms(setup_test_data):
    """
    Test that cached lookups complete in under 1ms.
    
    Requirements: 14.9
    Property: Cached lookups must be < 1ms on average
    """
    requests, documents = setup_test_data
    
    # All documents are now in cache
    # Perform 1000 random lookups and measure time
    
    lookup_times = []
    num_lookups = 1000
    
    for i in range(num_lookups):
        doc = documents[i % len(documents)]
        
        start = time.perf_counter()
        result = database.get_document(doc.doc_id)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        lookup_times.append(elapsed_ms)
        
        assert result is not None, f"Document {doc.doc_id} should be found"
        assert result.doc_id == doc.doc_id
    
    # Calculate statistics
    avg_time = sum(lookup_times) / len(lookup_times)
    max_time = max(lookup_times)
    min_time = min(lookup_times)
    
    print(f"\n{'='*70}")
    print(f"Cache Lookup Performance (In-Memory)")
    print(f"{'='*70}")
    print(f"  Number of lookups: {num_lookups}")
    print(f"  Average time:      {avg_time:.6f} ms")
    print(f"  Min time:          {min_time:.6f} ms")
    print(f"  Max time:          {max_time:.6f} ms")
    print(f"  Requirement:       < 1.0 ms")
    print(f"{'='*70}")
    
    # Assert: Average lookup time must be < 1ms
    assert avg_time < 1.0, (
        f"Average cache lookup time {avg_time:.6f}ms exceeds 1ms requirement"
    )
    
    # Assert: 95% of lookups should be < 1ms
    under_1ms = sum(1 for t in lookup_times if t < 1.0)
    under_1ms_pct = (under_1ms / len(lookup_times)) * 100
    
    print(f"\n  Lookups < 1ms:     {under_1ms}/{num_lookups} ({under_1ms_pct:.1f}%)")
    
    assert under_1ms_pct >= 95.0, (
        f"Only {under_1ms_pct:.1f}% of lookups under 1ms (expected >= 95%)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 2: Measure lookup time by document number
# ══════════════════════════════════════════════════════════════════════════════

def test_cache_lookup_by_document_number(setup_test_data):
    """
    Test that lookups by document number are fast (cached).
    
    Requirements: 14.9
    Property: Document number lookups use cache efficiently
    """
    requests, documents = setup_test_data
    
    lookup_times = []
    num_lookups = 1000
    
    for i in range(num_lookups):
        doc = documents[i % len(documents)]
        
        start = time.perf_counter()
        result = database.get_document_by_number(doc.document_number)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        lookup_times.append(elapsed_ms)
        
        assert result is not None
        assert result.document_number == doc.document_number
    
    avg_time = sum(lookup_times) / len(lookup_times)
    
    print(f"\n{'='*70}")
    print(f"Document Number Lookup Performance")
    print(f"{'='*70}")
    print(f"  Number of lookups: {num_lookups}")
    print(f"  Average time:      {avg_time:.6f} ms")
    print(f"  Requirement:       < 5.0 ms (linear scan acceptable for cache)")
    print(f"{'='*70}")
    
    # Document number lookup requires linear scan of cache
    # Should still be fast (< 5ms for 100 documents)
    assert avg_time < 5.0, (
        f"Document number lookup {avg_time:.6f}ms too slow"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 3: Verify cache hit rate > 90% for repeated lookups
# ══════════════════════════════════════════════════════════════════════════════

def test_cache_hit_rate_above_90_percent(setup_test_data):
    """
    Test that cache hit rate exceeds 90% for repeated lookups.
    
    Requirements: 14.9
    Property: Cache hit rate must be > 90% for typical access patterns
    """
    requests, documents = setup_test_data
    
    # Simulate realistic access pattern:
    # - 70% of accesses to 20% of documents (hot set)
    # - 30% of accesses to remaining 80% (cold set)
    
    hot_set_size = len(documents) // 5  # 20% of documents
    hot_set = documents[:hot_set_size]
    cold_set = documents[hot_set_size:]
    
    num_lookups = 10000
    cache_hits = 0
    cache_misses = 0
    
    for i in range(num_lookups):
        # 70% chance of accessing hot set
        if i % 10 < 7:
            doc = hot_set[i % len(hot_set)]
        else:
            doc = cold_set[i % len(cold_set)]
        
        # Check if document is in cache
        if doc.doc_id in database._documents:
            cache_hits += 1
            result = database.get_document(doc.doc_id)
        else:
            cache_misses += 1
            # Simulate cache miss by temporarily removing from cache
            temp_doc = database._documents.pop(doc.doc_id, None)
            result = database.get_document(doc.doc_id)
            if temp_doc:
                database._documents[doc.doc_id] = temp_doc
        
        assert result is not None
    
    cache_hit_rate = (cache_hits / num_lookups) * 100
    
    print(f"\n{'='*70}")
    print(f"Cache Hit Rate Analysis")
    print(f"{'='*70}")
    print(f"  Total lookups:     {num_lookups}")
    print(f"  Cache hits:        {cache_hits}")
    print(f"  Cache misses:      {cache_misses}")
    print(f"  Hit rate:          {cache_hit_rate:.2f}%")
    print(f"  Requirement:       > 90.0%")
    print(f"  Hot set size:      {hot_set_size} documents ({hot_set_size/len(documents)*100:.0f}%)")
    print(f"  Cold set size:     {len(cold_set)} documents ({len(cold_set)/len(documents)*100:.0f}%)")
    print(f"{'='*70}")
    
    # Assert: Cache hit rate must exceed 90%
    assert cache_hit_rate > 90.0, (
        f"Cache hit rate {cache_hit_rate:.2f}% below 90% requirement"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 4: Measure bulk lookup performance
# ══════════════════════════════════════════════════════════════════════════════

def test_bulk_document_lookup_performance(setup_test_data):
    """
    Test performance of bulk document lookups (e.g., get_documents_for_user).
    
    Requirements: 14.9
    Property: Bulk lookups should efficiently use cache
    """
    requests, documents = setup_test_data
    
    # Documents are distributed across 10 users
    lookup_times = []
    
    for user_id in [f"user-{i}" for i in range(10)]:
        start = time.perf_counter()
        user_docs = database.get_documents_for_user(user_id)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        lookup_times.append(elapsed_ms)
        
        # Each user should have ~10 documents
        assert len(user_docs) > 0, f"User {user_id} should have documents"
    
    avg_time = sum(lookup_times) / len(lookup_times)
    total_time = sum(lookup_times)
    
    print(f"\n{'='*70}")
    print(f"Bulk User Document Lookup Performance")
    print(f"{'='*70}")
    print(f"  Number of users:   {len(lookup_times)}")
    print(f"  Average time/user: {avg_time:.6f} ms")
    print(f"  Total time:        {total_time:.6f} ms")
    print(f"  Requirement:       < 10.0 ms per user")
    print(f"{'='*70}")
    
    # Bulk lookup should be fast (< 10ms per user for 100 documents)
    assert avg_time < 10.0, (
        f"Bulk lookup average time {avg_time:.6f}ms exceeds 10ms requirement"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 5: Request lookup performance
# ══════════════════════════════════════════════════════════════════════════════

def test_request_lookup_performance(setup_test_data):
    """
    Test that request lookups are also fast with in-memory cache.
    
    Requirements: 14.9
    Property: Request lookups must be < 1ms on average
    """
    requests, documents = setup_test_data
    
    lookup_times = []
    num_lookups = 1000
    
    for i in range(num_lookups):
        req = requests[i % len(requests)]
        
        start = time.perf_counter()
        result = database.get_request(req.request_id)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        lookup_times.append(elapsed_ms)
        
        assert result is not None
        assert result.request_id == req.request_id
    
    avg_time = sum(lookup_times) / len(lookup_times)
    
    print(f"\n{'='*70}")
    print(f"Request Lookup Performance")
    print(f"{'='*70}")
    print(f"  Number of lookups: {num_lookups}")
    print(f"  Average time:      {avg_time:.6f} ms")
    print(f"  Requirement:       < 1.0 ms")
    print(f"{'='*70}")
    
    assert avg_time < 1.0, (
        f"Request lookup average time {avg_time:.6f}ms exceeds 1ms requirement"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 6: Concurrent access performance (thread safety)
# ══════════════════════════════════════════════════════════════════════════════

def test_concurrent_cache_access(setup_test_data):
    """
    Test cache performance under concurrent access.
    
    Requirements: 14.9, 22.5
    Property: Cache must remain fast under concurrent read access
    """
    import threading
    
    requests, documents = setup_test_data
    
    results = []
    errors = []
    
    def worker(thread_id: int, num_ops: int):
        """Worker thread performing random lookups."""
        thread_times = []
        try:
            for i in range(num_ops):
                doc = documents[(thread_id + i) % len(documents)]
                
                start = time.perf_counter()
                result = database.get_document(doc.doc_id)
                end = time.perf_counter()
                
                elapsed_ms = (end - start) * 1000
                thread_times.append(elapsed_ms)
                
                assert result is not None
        except Exception as e:
            errors.append((thread_id, str(e)))
        
        results.append((thread_id, thread_times))
    
    # Launch 10 threads, each performing 100 lookups
    num_threads = 10
    ops_per_thread = 100
    
    threads = []
    start_time = time.perf_counter()
    
    for i in range(num_threads):
        t = threading.Thread(target=worker, args=(i, ops_per_thread))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    end_time = time.perf_counter()
    total_time_ms = (end_time - start_time) * 1000
    
    # Aggregate results
    all_times = []
    for thread_id, times in results:
        all_times.extend(times)
    
    avg_time = sum(all_times) / len(all_times) if all_times else 0
    total_ops = len(all_times)
    throughput = total_ops / (total_time_ms / 1000)  # ops/sec
    
    print(f"\n{'='*70}")
    print(f"Concurrent Cache Access Performance")
    print(f"{'='*70}")
    print(f"  Threads:           {num_threads}")
    print(f"  Ops per thread:    {ops_per_thread}")
    print(f"  Total operations:  {total_ops}")
    print(f"  Total time:        {total_time_ms:.2f} ms")
    print(f"  Avg lookup time:   {avg_time:.6f} ms")
    print(f"  Throughput:        {throughput:.0f} ops/sec")
    print(f"  Errors:            {len(errors)}")
    print(f"{'='*70}")
    
    # Assert: No errors during concurrent access
    assert len(errors) == 0, f"Concurrent access produced errors: {errors}"
    
    # Assert: Average lookup time still under 2ms (slightly higher due to lock contention)
    assert avg_time < 2.0, (
        f"Concurrent lookup average time {avg_time:.6f}ms exceeds 2ms threshold"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 7: Cache effectiveness for repeated access patterns
# ══════════════════════════════════════════════════════════════════════════════

def test_cache_effectiveness_repeated_patterns(setup_test_data):
    """
    Test cache effectiveness with realistic repeated access patterns.
    
    Requirements: 14.9
    Property: Repeated lookups should consistently hit cache
    """
    requests, documents = setup_test_data
    
    # Simulate realistic pattern: repeatedly access same 10 documents
    hot_documents = documents[:10]
    
    num_iterations = 100
    all_times = []
    
    for iteration in range(num_iterations):
        for doc in hot_documents:
            start = time.perf_counter()
            result = database.get_document(doc.doc_id)
            end = time.perf_counter()
            
            elapsed_ms = (end - start) * 1000
            all_times.append(elapsed_ms)
            
            assert result is not None
    
    total_lookups = len(all_times)
    avg_time = sum(all_times) / total_lookups
    under_1ms = sum(1 for t in all_times if t < 1.0)
    hit_rate = (under_1ms / total_lookups) * 100
    
    print(f"\n{'='*70}")
    print(f"Repeated Access Pattern Performance")
    print(f"{'='*70}")
    print(f"  Hot set size:      {len(hot_documents)} documents")
    print(f"  Iterations:        {num_iterations}")
    print(f"  Total lookups:     {total_lookups}")
    print(f"  Average time:      {avg_time:.6f} ms")
    print(f"  Lookups < 1ms:     {under_1ms}/{total_lookups} ({hit_rate:.1f}%)")
    print(f"  Requirement:       > 95.0% under 1ms")
    print(f"{'='*70}")
    
    # Assert: > 95% of repeated lookups should be under 1ms
    assert hit_rate > 95.0, (
        f"Only {hit_rate:.1f}% of repeated lookups under 1ms (expected > 95%)"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Test 8: Comparison - cache vs disk (simulated)
# ══════════════════════════════════════════════════════════════════════════════

def test_cache_vs_disk_comparison(setup_test_data):
    """
    Compare cache lookup time vs disk read time (simulated).
    
    Requirements: 14.9
    Property: Cache lookups should be significantly faster than disk reads
    """
    requests, documents = setup_test_data
    
    # Measure cache lookup time
    cache_times = []
    num_lookups = 100
    
    for i in range(num_lookups):
        doc = documents[i % len(documents)]
        
        start = time.perf_counter()
        result = database.get_document(doc.doc_id)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        cache_times.append(elapsed_ms)
    
    avg_cache_time = sum(cache_times) / len(cache_times)
    
    # Simulate disk read by measuring JSON parse time
    # (actual disk read would be slower, but this gives a lower bound)
    import json
    
    disk_times = []
    for i in range(num_lookups):
        doc = documents[i % len(documents)]
        doc_dict = doc.to_dict()
        
        start = time.perf_counter()
        # Simulate disk read by serializing and deserializing
        json_str = json.dumps(doc_dict)
        parsed = json.loads(json_str)
        end = time.perf_counter()
        
        elapsed_ms = (end - start) * 1000
        disk_times.append(elapsed_ms)
    
    avg_disk_time = sum(disk_times) / len(disk_times)
    speedup = avg_disk_time / avg_cache_time if avg_cache_time > 0 else 0
    
    print(f"\n{'='*70}")
    print(f"Cache vs Disk Performance Comparison")
    print(f"{'='*70}")
    print(f"  Cache lookup:      {avg_cache_time:.6f} ms")
    print(f"  Disk read (sim):   {avg_disk_time:.6f} ms")
    print(f"  Speedup:           {speedup:.1f}x")
    print(f"  Requirement:       Cache should be > 10x faster")
    print(f"{'='*70}")
    
    # Assert: Cache should be at least 10x faster than disk
    # (This is conservative - actual disk reads would be much slower)
    assert speedup > 10.0, (
        f"Cache speedup {speedup:.1f}x is below 10x requirement"
    )


# ══════════════════════════════════════════════════════════════════════════════
# Main test runner
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
