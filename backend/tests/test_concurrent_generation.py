"""
test_concurrent_generation.py — Property-based test for concurrent document generation.

Tests Task 6.2: Run concurrent generation test
- Launch 50 concurrent document generation requests
- Assert no data corruption or race conditions
- Assert all document numbers are unique
- Assert all PDFs written successfully

Validates: Requirements 14.8, 22.1-22.7
"""

import concurrent.futures
import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generation.workflow import run_full_pipeline
from generation.models import DocumentType
from generation.database import (
    get_document_by_number,
    get_all_documents,
    _documents,
)


def generate_test_fields(doc_type: DocumentType, index: int) -> Dict[str, Any]:
    """Generate valid test fields for different document types."""
    
    if doc_type == DocumentType.PASSPORT:
        return {
            "surname": f"TestUser{index}",
            "given_names": f"Concurrent Test {index}",
            "date_of_birth": "1990-01-15",
            "place_of_birth": "Mumbai, Maharashtra",
            "gender": "M",
            "nationality": "Indian",
            "aadhaar_number": f"{1000000000 + index:012d}",
            "father_name": f"Father {index}",
            "mother_name": f"Mother {index}",
            "address": f"{index} Test Street, Pune 411001",
            "application_type": "Fresh",
        }
    
    elif doc_type == DocumentType.DRIVING_LICENSE:
        return {
            "full_name": f"TestDriver {index}",
            "date_of_birth": "1990-01-15",
            "blood_group": "O+",
            "gender": "M",
            "address": f"{index} Test Road, Pune",
            "pincode": "411001",
            "vehicle_classes": "LMV",
            "rto_code": "MH12",
            "state": "Maharashtra",
            "aadhaar_number": f"{1000000000 + index:012d}",
            "father_or_spouse": f"Father {index}",
        }
    
    elif doc_type == DocumentType.BIRTH_CERTIFICATE:
        return {
            "child_name": f"TestChild {index}",
            "date_of_birth": "2024-01-10",
            "time_of_birth": "10:30",
            "place_of_birth": "Test Hospital, Pune",
            "gender": "Male",
            "father_name": f"Father {index}",
            "mother_name": f"Mother {index}",
            "father_nationality": "Indian",
            "mother_nationality": "Indian",
            "permanent_address": f"{index} Test Street, Pune 411001",
            "registration_date": "2024-01-12",
        }
    
    elif doc_type == DocumentType.INCOME_CERTIFICATE:
        return {
            "full_name": f"TestIncome {index}",
            "date_of_birth": "1990-01-15",
            "gender": "Male",
            "address": f"{index} Test Street, Pune 411001",
            "aadhaar_number": f"{1000000000 + index:012d}",
            "annual_income": "480000",
            "income_source": "Employment",
            "income_source_detail": "Software Engineer",
            "family_income": "720000",
            "purpose": "Government scheme application",
            "father_name": f"Father {index}",
            "occupation": "Software Engineer",
            "caste_category": "General",
        }
    
    elif doc_type == DocumentType.LAND_RECORD:
        return {
            "owner_name": f"TestOwner {index}",
            "father_name": f"Father {index}",
            "owner_address": f"{index} Test Village, Pune 411001",
            "aadhaar_number": f"{1000000000 + index:012d}",
            "survey_number": f"45/{index}",
            "area": "1.5 Acres",
            "land_type": "Agricultural",
            "village": "Test Village",
            "tehsil": "Haveli",
            "district": "Pune",
            "state": "Maharashtra",
            "transaction_type": "Original Patta",
        }
    
    else:
        raise ValueError(f"Unknown document type: {doc_type}")


def generate_single_document(args: Tuple[DocumentType, int, str]) -> Dict[str, Any]:
    """
    Generate a single document (worker function for concurrent execution).
    
    Returns dict with:
    - success: bool
    - doc_id: str
    - doc_number: str
    - pdf_path: str
    - error: str (if failed)
    - index: int (worker index)
    """
    doc_type, index, base_user_id = args
    
    try:
        # Generate unique user IDs for each document
        applicant_id = f"{base_user_id}-applicant-{index}"
        issuer_id = f"{base_user_id}-issuer-{index}"
        
        # Generate fields
        fields = generate_test_fields(doc_type, index)
        
        # Run full pipeline
        request, document = run_full_pipeline(
            document_type=doc_type,
            applicant_user_id=applicant_id,
            issuer_user_id=issuer_id,
            issuer_name=f"Test Issuer {index}",
            submitted_fields=fields,
            department_code=f"TEST-DEPT-{index % 10}",
            ip_address=f"192.168.1.{index % 255}",
        )
        
        return {
            "success": True,
            "doc_id": document.doc_id,
            "doc_number": document.document_number,
            "pdf_path": document.pdf_path,
            "pdf_exists": os.path.exists(document.pdf_path),
            "signature_status": document.signature_status.value,
            "status": document.status.value,
            "index": index,
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "index": index,
        }


def test_concurrent_generation_50_documents():
    """
    Test Task 6.2: Run concurrent generation test.
    
    Tests:
    - 50 concurrent document generation requests
    - No data corruption or race conditions
    - All document numbers are unique
    - All PDFs written successfully
    
    Validates: Requirements 14.8, 22.1-22.7
    """
    
    print("\n" + "=" * 80)
    print("TEST: Concurrent Document Generation (50 workers)")
    print("=" * 80)
    
    # Test parameters
    num_workers = 50
    doc_type = DocumentType.PASSPORT  # Use passport for testing
    base_user_id = f"concurrent-test-{int(time.time())}"
    
    print(f"\nTest parameters:")
    print(f"  - Workers:       {num_workers}")
    print(f"  - Document type: {doc_type.value}")
    print(f"  - Base user ID:  {base_user_id}")
    
    # Record initial document count
    initial_doc_count = len(_documents)
    print(f"  - Initial docs:  {initial_doc_count}")
    
    # Prepare worker arguments
    worker_args = [(doc_type, i, base_user_id) for i in range(num_workers)]
    
    # Execute concurrent generation
    print(f"\n⏱️  Starting concurrent generation...")
    start_time = time.time()
    
    results: List[Dict[str, Any]] = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        # Submit all tasks
        futures = [executor.submit(generate_single_document, args) for args in worker_args]
        
        # Collect results as they complete
        for i, future in enumerate(concurrent.futures.as_completed(futures)):
            result = future.result()
            results.append(result)
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  ✓ Completed {i + 1}/{num_workers} requests...")
    
    elapsed_time = time.time() - start_time
    
    print(f"\n⏱️  Completed in {elapsed_time:.2f} seconds")
    print(f"  - Throughput: {num_workers / elapsed_time:.2f} docs/second")
    print(f"  - Avg time:   {elapsed_time / num_workers * 1000:.2f} ms/doc")
    
    # ─────────────────────────────────────────────────────────────
    # Assertion 1: All requests succeeded
    # ─────────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("ASSERTION 1: All requests succeeded")
    print("-" * 80)
    
    successes = [r for r in results if r.get("success")]
    failures = [r for r in results if not r.get("success")]
    
    print(f"  Successes: {len(successes)}/{num_workers}")
    print(f"  Failures:  {len(failures)}/{num_workers}")
    
    if failures:
        print("\n  Failed requests:")
        for fail in failures[:5]:  # Show first 5 failures
            print(f"    - Index {fail['index']}: {fail.get('error', 'Unknown error')}")
    
    assert len(successes) == num_workers, \
        f"Expected {num_workers} successes, got {len(successes)}"
    
    print("  ✅ PASS: All requests succeeded")
    
    # ─────────────────────────────────────────────────────────────
    # Assertion 2: All document numbers are unique
    # ─────────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("ASSERTION 2: All document numbers are unique")
    print("-" * 80)
    
    doc_numbers: List[str] = [r["doc_number"] for r in successes]
    unique_doc_numbers: Set[str] = set(doc_numbers)
    
    print(f"  Total doc numbers:  {len(doc_numbers)}")
    print(f"  Unique doc numbers: {len(unique_doc_numbers)}")
    
    if len(doc_numbers) != len(unique_doc_numbers):
        # Find duplicates
        seen = set()
        duplicates = []
        for num in doc_numbers:
            if num in seen:
                duplicates.append(num)
            seen.add(num)
        
        print(f"\n  ❌ DUPLICATES FOUND: {duplicates[:10]}")
    
    assert len(doc_numbers) == len(unique_doc_numbers), \
        f"Document number collision detected! {len(doc_numbers)} total, {len(unique_doc_numbers)} unique"
    
    print("  ✅ PASS: All document numbers are unique")
    
    # Print sample document numbers
    print(f"\n  Sample document numbers:")
    for num in sorted(doc_numbers)[:5]:
        print(f"    - {num}")
    if len(doc_numbers) > 5:
        print(f"    ... ({len(doc_numbers) - 5} more)")
    
    # ─────────────────────────────────────────────────────────────
    # Assertion 3: All PDFs written successfully
    # ─────────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("ASSERTION 3: All PDFs written successfully")
    print("-" * 80)
    
    pdf_paths = [r["pdf_path"] for r in successes]
    pdf_exists = [r["pdf_exists"] for r in successes]
    
    existing_pdfs = sum(pdf_exists)
    missing_pdfs = [p for p, exists in zip(pdf_paths, pdf_exists) if not exists]
    
    print(f"  PDFs exist:    {existing_pdfs}/{num_workers}")
    print(f"  PDFs missing:  {len(missing_pdfs)}/{num_workers}")
    
    if missing_pdfs:
        print(f"\n  Missing PDF files:")
        for path in missing_pdfs[:5]:
            print(f"    - {path}")
    
    assert existing_pdfs == num_workers, \
        f"Expected {num_workers} PDFs, only {existing_pdfs} exist on disk"
    
    print("  ✅ PASS: All PDFs written successfully")
    
    # ─────────────────────────────────────────────────────────────
    # Assertion 4: No data corruption (all documents retrievable)
    # ─────────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("ASSERTION 4: No data corruption (all documents retrievable)")
    print("-" * 80)
    
    retrievable_count = 0
    retrieval_failures = []
    
    for result in successes:
        doc = get_document_by_number(result["doc_number"])
        if doc:
            retrievable_count += 1
        else:
            retrieval_failures.append(result["doc_number"])
    
    print(f"  Retrievable:   {retrievable_count}/{num_workers}")
    print(f"  Not found:     {len(retrieval_failures)}/{num_workers}")
    
    if retrieval_failures:
        print(f"\n  Failed to retrieve:")
        for num in retrieval_failures[:5]:
            print(f"    - {num}")
    
    assert retrievable_count == num_workers, \
        f"Data corruption detected: {len(retrieval_failures)} documents not retrievable"
    
    print("  ✅ PASS: All documents retrievable from database")
    
    # ─────────────────────────────────────────────────────────────
    # Assertion 5: All documents have valid signature status
    # ─────────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("ASSERTION 5: All documents have valid signature status")
    print("-" * 80)
    
    signature_statuses = [r["signature_status"] for r in successes]
    signed_count = sum(1 for s in signature_statuses if s == "signed")
    
    print(f"  Signed:        {signed_count}/{num_workers}")
    print(f"  Not signed:    {num_workers - signed_count}/{num_workers}")
    
    invalid_sigs = [r for r in successes if r["signature_status"] != "signed"]
    if invalid_sigs:
        print(f"\n  Invalid signature statuses:")
        for r in invalid_sigs[:5]:
            print(f"    - Doc {r['doc_number']}: {r['signature_status']}")
    
    assert signed_count == num_workers, \
        f"Expected all {num_workers} documents signed, only {signed_count} signed"
    
    print("  ✅ PASS: All documents have valid signature status")
    
    # ─────────────────────────────────────────────────────────────
    # Assertion 6: All documents have status COMPLETE
    # ─────────────────────────────────────────────────────────────
    print("\n" + "-" * 80)
    print("ASSERTION 6: All documents have status COMPLETE")
    print("-" * 80)
    
    statuses = [r["status"] for r in successes]
    complete_count = sum(1 for s in statuses if s == "complete")
    
    print(f"  Complete:      {complete_count}/{num_workers}")
    print(f"  Incomplete:    {num_workers - complete_count}/{num_workers}")
    
    incomplete = [r for r in successes if r["status"] != "complete"]
    if incomplete:
        print(f"\n  Incomplete documents:")
        for r in incomplete[:5]:
            print(f"    - Doc {r['doc_number']}: {r['status']}")
    
    assert complete_count == num_workers, \
        f"Expected all {num_workers} documents complete, only {complete_count} complete"
    
    print("  ✅ PASS: All documents have status COMPLETE")
    
    # ─────────────────────────────────────────────────────────────
    # Final summary
    # ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("TEST RESULT: ✅ PASSED")
    print("=" * 80)
    
    print(f"\nSummary:")
    print(f"  ✅ All {num_workers} requests succeeded")
    print(f"  ✅ All document numbers are unique")
    print(f"  ✅ All PDFs written successfully")
    print(f"  ✅ No data corruption detected")
    print(f"  ✅ All documents have valid signatures")
    print(f"  ✅ All documents are complete")
    
    print(f"\nPerformance:")
    print(f"  - Total time:  {elapsed_time:.2f} seconds")
    print(f"  - Throughput:  {num_workers / elapsed_time:.2f} docs/second")
    print(f"  - Avg time:    {elapsed_time / num_workers * 1000:.2f} ms/doc")
    
    # Check if throughput meets requirement (100 docs/min = 1.67 docs/sec)
    required_throughput = 100 / 60  # 1.67 docs/sec
    actual_throughput = num_workers / elapsed_time
    
    if actual_throughput >= required_throughput:
        print(f"  ✅ Throughput meets requirement (>= {required_throughput:.2f} docs/sec)")
    else:
        print(f"  ⚠️  Throughput below requirement (>= {required_throughput:.2f} docs/sec)")
    
    print("\n" + "=" * 80)
    print("Validates: Requirements 14.8, 22.1, 22.2, 22.3, 22.4, 22.5, 22.6, 22.7")
    print("=" * 80 + "\n")


def main():
    """Main test runner."""
    try:
        test_concurrent_generation_50_documents()
        print("\n✅ All tests passed!\n")
        return 0
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}\n")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}\n")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
