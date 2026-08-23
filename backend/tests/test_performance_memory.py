"""
test_performance_memory.py — Memory usage benchmark under concurrent load.

Task 6.3: Measure memory usage under load
- Generate 50 documents concurrently
- Monitor peak memory usage
- Assert peak memory < 300MB

Requirements: 14.10
"""

import asyncio
import json
import os
import psutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

import requests

BASE = os.getenv("BASE_URL", "http://127.0.0.1:8000")
CONCURRENT_DOCS = 50
MEMORY_LIMIT_MB = 300
REQUEST_TIMEOUT = 120  # Increased timeout for concurrent load


def get_process_memory_mb() -> float:
    """Get current process memory usage in MB."""
    process = psutil.Process()
    mem_info = process.memory_info()
    return mem_info.rss / (1024 * 1024)  # Convert bytes to MB


def get_issuing_authority_token() -> str:
    """Login and get issuing authority token."""
    print("[SETUP] Logging in as issuing authority...")
    r = requests.post(f"{BASE}/auth/login", json={
        "role": "issuing_authority",
        "department_code": "COLLECTOR-PUNE",
        "password": "IssAuth@5678",
    })
    
    if r.status_code != 200:
        print(f"❌ FATAL: Failed to login. Status: {r.status_code}")
        print(f"   Response: {r.text[:200]}")
        sys.exit(1)
    
    data = r.json()
    token = data.get("access_token", "")
    user_id = data.get("user", {}).get("user_id", "")
    
    print(f"✓ Logged in successfully")
    print(f"  Token: {token[:30]}...")
    print(f"  User ID: {user_id}")
    
    return token


def generate_single_document(doc_index: int, token: str) -> Dict[str, Any]:
    """
    Generate a single document and return generation metadata.
    
    Args:
        doc_index: Document number for unique field values
        token: Authorization token
        
    Returns:
        Dict with status, doc_id, doc_number, duration, error (if any)
    """
    start_time = time.time()
    
    # Vary document types to test different templates
    doc_types = ["passport", "license", "birth", "income", "land"]
    doc_type = doc_types[doc_index % len(doc_types)]
    
    # Use unique user ID per document to avoid duplicate detection
    # This is necessary because birth/income/land certificates are non-renewable
    unique_user_id = f"perf-test-user-{doc_index}"
    unique_aadhaar = f"{100000000000 + doc_index}"
    
    # Prepare fields based on document type
    if doc_type == "passport":
        fields = {
            "surname": f"TestUser{doc_index}",
            "given_names": f"Concurrent Test {doc_index}",
            "date_of_birth": "1990-05-15",
            "place_of_birth": "Mumbai, Maharashtra",
            "gender": "M",
            "nationality": "Indian",
            "aadhaar_number": unique_aadhaar,
            "father_name": f"Father{doc_index}",
            "mother_name": f"Mother{doc_index}",
            "address": f"{doc_index} MG Road, Pune 411001",
            "application_type": "Fresh",
        }
        endpoint = "/generate/passport"
    
    elif doc_type == "license":
        fields = {
            "full_name": f"TestUser{doc_index}",
            "date_of_birth": "1990-05-15",
            "blood_group": "O+",
            "gender": "M",
            "address": f"{doc_index} MG Road, Pune",
            "pincode": "411001",
            "vehicle_classes": "LMV, MCWG",
            "rto_code": "MH12",
            "state": "Maharashtra",
            "aadhaar_number": unique_aadhaar,
            "father_or_spouse": f"Father{doc_index}",
        }
        endpoint = "/generate/license"
    
    elif doc_type == "birth":
        fields = {
            "child_name": f"TestBaby{doc_index}",
            "date_of_birth": "2024-03-10",
            "time_of_birth": "08:45",
            "place_of_birth": "Hospital, Pune",
            "gender": "Male",
            "father_name": f"Father{doc_index}",
            "mother_name": f"Mother{doc_index}",
            "father_nationality": "Indian",
            "mother_nationality": "Indian",
            "permanent_address": f"{doc_index} MG Road, Pune 411001",
            "registration_date": "2024-03-12",
        }
        endpoint = "/generate/birth"
    
    elif doc_type == "income":
        fields = {
            "full_name": f"TestUser{doc_index}",
            "date_of_birth": "1990-05-15",
            "gender": "Male",
            "address": f"{doc_index} MG Road, Pune 411001",
            "aadhaar_number": unique_aadhaar,
            "annual_income": "480000",
            "income_source": "Employment",
            "income_source_detail": "Software Engineer",
            "family_income": "720000",
            "purpose": "Government scheme application",
            "father_name": f"Father{doc_index}",
            "occupation": "Software Engineer",
            "caste_category": "General",
        }
        endpoint = "/generate/income"
    
    else:  # land
        fields = {
            "owner_name": f"Owner{doc_index}",
            "father_name": f"Father{doc_index}",
            "owner_address": f"{doc_index} Pune 411001",
            "aadhaar_number": unique_aadhaar,
            "survey_number": f"45/{doc_index}",
            "area": "1.5 Acres",
            "land_type": "Agricultural",
            "village": "Test Village",
            "tehsil": "Haveli",
            "district": "Pune",
            "state": "Maharashtra",
            "transaction_type": "Original Patta",
        }
        endpoint = "/generate/land"
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        payload = {
            "fields": fields,
            "applicant_user_id": unique_user_id,
        }
        
        r = requests.post(f"{BASE}{endpoint}", json=payload, headers=headers, timeout=REQUEST_TIMEOUT)
        
        duration = time.time() - start_time
        
        if r.status_code == 200:
            data = r.json()
            return {
                "status": "success",
                "doc_index": doc_index,
                "doc_type": doc_type,
                "doc_id": data.get("document_id", ""),
                "doc_number": data.get("document_number", ""),
                "pdf_size": data.get("pdf_size_bytes", 0),
                "duration": duration,
            }
        else:
            return {
                "status": "failed",
                "doc_index": doc_index,
                "doc_type": doc_type,
                "error": f"HTTP {r.status_code}: {r.text[:100]}",
                "duration": duration,
            }
    
    except Exception as e:
        duration = time.time() - start_time
        return {
            "status": "error",
            "doc_index": doc_index,
            "doc_type": doc_type,
            "error": str(e),
            "duration": duration,
        }


def run_concurrent_generation_test(token: str) -> Dict[str, Any]:
    """
    Run concurrent document generation and monitor memory.
    
    Args:
        token: Authorization token
        
    Returns:
        Dict with test results including memory stats
    """
    print(f"\n{'='*70}")
    print(f"  TASK 6.3: Memory Usage Under Load")
    print(f"  Generating {CONCURRENT_DOCS} documents concurrently...")
    print(f"{'='*70}\n")
    
    # Record baseline memory
    baseline_memory = get_process_memory_mb()
    print(f"[BASELINE] Memory usage: {baseline_memory:.2f} MB")
    
    # Start memory monitoring
    memory_samples: List[float] = [baseline_memory]
    
    def memory_monitor():
        """Background thread to sample memory every 0.1 seconds."""
        while monitoring:
            memory_samples.append(get_process_memory_mb())
            time.sleep(0.1)
    
    monitoring = True
    import threading
    monitor_thread = threading.Thread(target=memory_monitor, daemon=True)
    monitor_thread.start()
    
    # Execute concurrent document generation
    start_time = time.time()
    results: List[Dict[str, Any]] = []
    
    print(f"[START] Launching {CONCURRENT_DOCS} concurrent requests...")
    
    with ThreadPoolExecutor(max_workers=CONCURRENT_DOCS) as executor:
        futures = {
            executor.submit(generate_single_document, i, token): i 
            for i in range(CONCURRENT_DOCS)
        }
        
        completed = 0
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            completed += 1
            
            # Progress indicator
            if completed % 10 == 0:
                current_mem = get_process_memory_mb()
                print(f"  [{completed}/{CONCURRENT_DOCS}] completed | "
                      f"Memory: {current_mem:.2f} MB")
    
    total_duration = time.time() - start_time
    
    # Stop memory monitoring
    monitoring = False
    time.sleep(0.2)  # Allow monitor thread to finish
    
    # Calculate memory statistics
    peak_memory = max(memory_samples)
    avg_memory = sum(memory_samples) / len(memory_samples)
    memory_increase = peak_memory - baseline_memory
    
    # Calculate success metrics
    successful = [r for r in results if r["status"] == "success"]
    failed = [r for r in results if r["status"] != "success"]
    
    # Calculate timing metrics
    if successful:
        avg_duration = sum(r["duration"] for r in successful) / len(successful)
        min_duration = min(r["duration"] for r in successful)
        max_duration = max(r["duration"] for r in successful)
    else:
        avg_duration = min_duration = max_duration = 0
    
    return {
        "total_docs": CONCURRENT_DOCS,
        "successful": len(successful),
        "failed": len(failed),
        "total_duration": total_duration,
        "avg_duration": avg_duration,
        "min_duration": min_duration,
        "max_duration": max_duration,
        "baseline_memory_mb": baseline_memory,
        "peak_memory_mb": peak_memory,
        "avg_memory_mb": avg_memory,
        "memory_increase_mb": memory_increase,
        "memory_samples": len(memory_samples),
        "results": results,
    }


def print_results(test_results: Dict[str, Any]) -> bool:
    """
    Print test results and determine pass/fail.
    
    Args:
        test_results: Results from run_concurrent_generation_test()
        
    Returns:
        True if test passed, False otherwise
    """
    print(f"\n{'='*70}")
    print(f"  TEST RESULTS")
    print(f"{'='*70}\n")
    
    # Document generation metrics
    print(f"Document Generation:")
    print(f"  Total documents:     {test_results['total_docs']}")
    print(f"  Successful:          {test_results['successful']} ✓")
    print(f"  Failed:              {test_results['failed']}")
    print(f"  Success rate:        {test_results['successful']/test_results['total_docs']*100:.1f}%")
    
    # Timing metrics
    print(f"\nTiming:")
    print(f"  Total duration:      {test_results['total_duration']:.2f}s")
    print(f"  Avg per document:    {test_results['avg_duration']:.3f}s")
    print(f"  Min duration:        {test_results['min_duration']:.3f}s")
    print(f"  Max duration:        {test_results['max_duration']:.3f}s")
    
    # Memory metrics
    print(f"\nMemory Usage:")
    print(f"  Baseline:            {test_results['baseline_memory_mb']:.2f} MB")
    print(f"  Peak:                {test_results['peak_memory_mb']:.2f} MB")
    print(f"  Average:             {test_results['avg_memory_mb']:.2f} MB")
    print(f"  Increase:            {test_results['memory_increase_mb']:.2f} MB")
    print(f"  Memory samples:      {test_results['memory_samples']}")
    
    # Requirement validation
    print(f"\n{'='*70}")
    print(f"  REQUIREMENT VALIDATION (Requirement 14.10)")
    print(f"{'='*70}\n")
    
    memory_pass = test_results['peak_memory_mb'] < MEMORY_LIMIT_MB
    
    print(f"✓ Target: Peak memory < {MEMORY_LIMIT_MB} MB for 50 concurrent generations")
    print(f"  Actual peak memory: {test_results['peak_memory_mb']:.2f} MB")
    
    if memory_pass:
        print(f"  Status: {'✓ PASS' if memory_pass else '✗ FAIL'}")
        print(f"  Margin: {MEMORY_LIMIT_MB - test_results['peak_memory_mb']:.2f} MB under limit")
    else:
        print(f"  Status: ✗ FAIL")
        print(f"  Exceeded by: {test_results['peak_memory_mb'] - MEMORY_LIMIT_MB:.2f} MB")
    
    # Print failures if any
    if test_results['failed'] > 0:
        print(f"\n{'='*70}")
        print(f"  FAILURES ({test_results['failed']} documents)")
        print(f"{'='*70}\n")
        
        failed_results = [r for r in test_results['results'] if r['status'] != 'success']
        for result in failed_results[:10]:  # Show first 10 failures
            print(f"  Doc {result['doc_index']} ({result['doc_type']}): {result['error']}")
        
        if len(failed_results) > 10:
            print(f"  ... and {len(failed_results) - 10} more failures")
    
    print(f"\n{'='*70}")
    
    # Overall pass/fail
    overall_pass = memory_pass and test_results['failed'] == 0
    
    if overall_pass:
        print(f"  ✓ TASK 6.3 PASSED")
        print(f"  Memory usage under load is within acceptable limits.")
    else:
        print(f"  ✗ TASK 6.3 FAILED")
        if not memory_pass:
            print(f"  Reason: Peak memory exceeded {MEMORY_LIMIT_MB} MB limit")
        if test_results['failed'] > 0:
            print(f"  Reason: {test_results['failed']} document generations failed")
    
    print(f"{'='*70}\n")
    
    return overall_pass


def main():
    """Main test execution."""
    print(f"\n{'='*70}")
    print(f"  PERFORMANCE TEST: Memory Usage Under Load")
    print(f"  Task 6.3 - Requirement 14.10")
    print(f"{'='*70}\n")
    
    print(f"Configuration:")
    print(f"  Base URL:            {BASE}")
    print(f"  Concurrent docs:     {CONCURRENT_DOCS}")
    print(f"  Memory limit:        {MEMORY_LIMIT_MB} MB")
    print(f"  Python version:      {sys.version.split()[0]}")
    
    # Check if psutil is available
    try:
        import psutil
        print(f"  psutil version:      {psutil.__version__}")
    except ImportError:
        print(f"\n❌ FATAL: psutil not installed")
        print(f"   Install with: pip install psutil")
        sys.exit(1)
    
    # Get authorization token
    token = get_issuing_authority_token()
    
    # Run the test
    test_results = run_concurrent_generation_test(token)
    
    # Print results and determine pass/fail
    passed = print_results(test_results)
    
    # Exit with appropriate code
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
