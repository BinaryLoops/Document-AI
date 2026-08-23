# Test API Script for Document Intelligence Workspace
# Run this after starting the server with: python main.py

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Testing Document Intelligence API" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$baseUrl = "http://localhost:8000"

# Test 1: Root endpoint
Write-Host "Test 1: Root Endpoint" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/" -Method Get
    Write-Host "✓ Success!" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 2: Health endpoint
Write-Host "Test 2: Health Endpoint" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/health" -Method Get
    Write-Host "✓ Success!" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

# Test 3: Status endpoint
Write-Host "Test 3: Status Endpoint" -ForegroundColor Yellow
try {
    $response = Invoke-RestMethod -Uri "$baseUrl/status" -Method Get
    Write-Host "✓ Success!" -ForegroundColor Green
    $response | ConvertTo-Json
} catch {
    Write-Host "✗ Failed: $($_.Exception.Message)" -ForegroundColor Red
}
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Tests Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Open browser: http://localhost:8000/docs" -ForegroundColor White
Write-Host "2. Try uploading a document" -ForegroundColor White
Write-Host "3. Query your documents" -ForegroundColor White
Write-Host ""
