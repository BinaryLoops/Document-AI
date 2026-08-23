# Quick Start Script for HuggingFace Integration
# This script helps you set up and run the server with HuggingFace AI

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  SIH Document Intelligence System" -ForegroundColor Cyan
Write-Host "  HuggingFace AI Setup (FREE!)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if HuggingFace API key is set
if ($env:HUGGINGFACE_API_KEY) {
    Write-Host "✓ HuggingFace API key is set!" -ForegroundColor Green
    Write-Host "  Token: $($env:HUGGINGFACE_API_KEY.Substring(0, 10))..." -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "⚠️  HuggingFace API key NOT set!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "To get your FREE token:" -ForegroundColor White
    Write-Host "1. Go to: https://huggingface.co/join" -ForegroundColor Cyan
    Write-Host "2. Sign up (FREE, no credit card needed)" -ForegroundColor Cyan
    Write-Host "3. Go to: https://huggingface.co/settings/tokens" -ForegroundColor Cyan
    Write-Host "4. Click 'New token' → Copy the token" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Then run this command:" -ForegroundColor White
    Write-Host '  $env:HUGGINGFACE_API_KEY = "hf_your_token_here"' -ForegroundColor Green
    Write-Host ""
    
    $response = Read-Host "Do you want to enter your token now? (y/n)"
    
    if ($response -eq "y" -or $response -eq "Y") {
        $token = Read-Host "Enter your HuggingFace token"
        $env:HUGGINGFACE_API_KEY = $token
        Write-Host ""
        Write-Host "✓ Token set successfully!" -ForegroundColor Green
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "⚠️  Running without token (will use free tier with limits)" -ForegroundColor Yellow
        Write-Host ""
    }
}

Write-Host "Starting server..." -ForegroundColor Cyan
Write-Host ""
Write-Host "Once running, test at: http://localhost:8000/docs" -ForegroundColor Green
Write-Host ""
Write-Host "Try these queries:" -ForegroundColor White
Write-Host '  {"query": "What color is the apple?"}' -ForegroundColor Gray
Write-Host '  {"query": "How sweet are the apples?"}' -ForegroundColor Gray
Write-Host '  {"query": "Summarize the document"}' -ForegroundColor Gray
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Start the server
python main.py
