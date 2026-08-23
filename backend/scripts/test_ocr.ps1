# OCR Test Script
# This script tests the OCR functionality by uploading an image

Write-Host "🧪 OCR Test Script" -ForegroundColor Cyan
Write-Host "==================`n" -ForegroundColor Cyan

# Check if test image exists
$imagePath = "test_document.png"
if (-not (Test-Path $imagePath)) {
    Write-Host "❌ Test image not found!" -ForegroundColor Red
    Write-Host "Creating test image..." -ForegroundColor Yellow
    python create_test_image.py
    if (-not (Test-Path $imagePath)) {
        Write-Host "❌ Failed to create test image" -ForegroundColor Red
        exit 1
    }
}

Write-Host "✅ Test image found: $imagePath" -ForegroundColor Green

# Check if server is running
Write-Host "`n🔍 Checking if server is running..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/health" -Method GET -ErrorAction Stop
    Write-Host "✅ Server is running!" -ForegroundColor Green
} catch {
    Write-Host "❌ Server is not running!" -ForegroundColor Red
    Write-Host "Please start the server with: python main.py" -ForegroundColor Yellow
    exit 1
}

# Upload the image
Write-Host "`n📤 Uploading image for OCR processing..." -ForegroundColor Yellow

$uri = "http://localhost:8000/upload?chunk_size=1000&chunk_overlap=200"
$fullPath = Resolve-Path $imagePath

try {
    # Create multipart form data
    $boundary = [System.Guid]::NewGuid().ToString()
    $LF = "`r`n"
    
    # Read file as bytes
    $fileBytes = [System.IO.File]::ReadAllBytes($fullPath)
    $fileName = [System.IO.Path]::GetFileName($fullPath)
    
    # Build multipart body
    $bodyLines = @(
        "--$boundary",
        "Content-Disposition: form-data; name=`"file`"; filename=`"$fileName`"",
        "Content-Type: image/png",
        "",
        [System.Text.Encoding]::GetEncoding("iso-8859-1").GetString($fileBytes),
        "--$boundary--"
    )
    
    $body = $bodyLines -join $LF
    
    $response = Invoke-RestMethod -Uri $uri -Method Post `
        -ContentType "multipart/form-data; boundary=$boundary" `
        -Body ([System.Text.Encoding]::GetEncoding("iso-8859-1").GetBytes($body))
    
    Write-Host "✅ Upload successful!" -ForegroundColor Green
    Write-Host "`n📊 OCR Results:" -ForegroundColor Cyan
    Write-Host "================`n" -ForegroundColor Cyan
    
    Write-Host "Status: " -NoNewline -ForegroundColor Yellow
    Write-Host $response.status -ForegroundColor Green
    
    Write-Host "Document ID: " -NoNewline -ForegroundColor Yellow
    Write-Host $response.document_id -ForegroundColor White
    
    Write-Host "Document Type: " -NoNewline -ForegroundColor Yellow
    Write-Host $response.document_type -ForegroundColor White
    
    Write-Host "Chunks Created: " -NoNewline -ForegroundColor Yellow
    Write-Host $response.chunk_count -ForegroundColor White
    
    Write-Host "Processing Time: " -NoNewline -ForegroundColor Yellow
    Write-Host "$($response.processing_time_seconds)s" -ForegroundColor White
    
    if ($response.extracted_fields) {
        Write-Host "`n📋 Extracted Fields:" -ForegroundColor Cyan
        foreach ($field in $response.extracted_fields) {
            if ($field.value) {
                Write-Host "  - $($field.field): " -NoNewline -ForegroundColor Yellow
                Write-Host $field.value -ForegroundColor Green
            }
        }
    }
    
    Write-Host "`n✅ OCR test completed successfully!" -ForegroundColor Green
    Write-Host "`n🔍 Now try querying at: http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "   Example query: {`"query`": `"What is the name?`", `"top_k`": 3}" -ForegroundColor White
    
} catch {
    Write-Host "❌ Upload failed!" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
