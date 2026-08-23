# Quick Setup Script for Ollama
# This installs Ollama and sets up a local AI model

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Ollama Setup - Local AI (FREE!)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Ollama is installed
Write-Host "Checking if Ollama is installed..." -ForegroundColor Yellow
try {
    $version = ollama --version 2>&1
    Write-Host "✓ Ollama is installed: $version" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "❌ Ollama is not installed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Installing Ollama..." -ForegroundColor Yellow
    
    # Try winget first
    try {
        winget install Ollama.Ollama
        Write-Host "✓ Ollama installed via winget!" -ForegroundColor Green
    } catch {
        Write-Host ""
        Write-Host "⚠️  Automatic installation failed" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please install manually:" -ForegroundColor White
        Write-Host "1. Open: https://ollama.ai/download" -ForegroundColor Cyan
        Write-Host "2. Download Windows installer" -ForegroundColor Cyan
        Write-Host "3. Run installer" -ForegroundColor Cyan
        Write-Host "4. Run this script again" -ForegroundColor Cyan
        Write-Host ""
        Read-Host "Press Enter to exit"
        exit
    }
    
    Write-Host ""
    Write-Host "⚠️  Please close and reopen PowerShell, then run this script again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit
}

# Check if ollama serve is running
Write-Host "Checking if Ollama server is running..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:11434/api/tags" -Method Get -TimeoutSec 2 -ErrorAction Stop
    Write-Host "✓ Ollama server is running" -ForegroundColor Green
    $serverRunning = $true
} catch {
    Write-Host "⚠️  Ollama server is not running" -ForegroundColor Yellow
    $serverRunning = $false
}
Write-Host ""

# Pull llama2 model
Write-Host "Checking for llama2 model..." -ForegroundColor Yellow
if ($serverRunning) {
    try {
        $tags = Invoke-RestMethod -Uri "http://localhost:11434/api/tags"
        $hasLlama2 = $tags.models | Where-Object { $_.name -like "llama2*" }
        
        if ($hasLlama2) {
            Write-Host "✓ llama2 model is already installed" -ForegroundColor Green
        } else {
            Write-Host "⚠️  llama2 model not found. Pulling now..." -ForegroundColor Yellow
            Write-Host "This will download ~3.8GB (first time only)" -ForegroundColor Gray
            ollama pull llama2
            Write-Host "✓ llama2 model installed!" -ForegroundColor Green
        }
    } catch {
        Write-Host "⚠️  Could not check models. Server might not be running." -ForegroundColor Yellow
    }
} else {
    Write-Host "⚠️  Cannot pull model - server not running" -ForegroundColor Yellow
}
Write-Host ""

# Instructions
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not $serverRunning) {
    Write-Host "⚠️  IMPORTANT: Start Ollama server first!" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Open a NEW PowerShell window and run:" -ForegroundColor White
    Write-Host "  ollama serve" -ForegroundColor Green
    Write-Host ""
    Write-Host "Keep that window open!" -ForegroundColor Yellow
    Write-Host ""
}

Write-Host "To start your Document Intelligence system:" -ForegroundColor White
Write-Host "  cd back-end" -ForegroundColor Green
Write-Host "  python main.py" -ForegroundColor Green
Write-Host ""
Write-Host "You should see:" -ForegroundColor White
Write-Host "  Using Ollama LLM (Local, FREE, No Internet Needed)" -ForegroundColor Gray
Write-Host ""
Write-Host "Test at: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

if (-not $serverRunning) {
    $response = Read-Host "Do you want to start Ollama server now? (y/n)"
    if ($response -eq "y" -or $response -eq "Y") {
        Write-Host ""
        Write-Host "Starting Ollama server..." -ForegroundColor Green
        Write-Host "Press Ctrl+C to stop" -ForegroundColor Yellow
        Write-Host ""
        ollama serve
    }
}
