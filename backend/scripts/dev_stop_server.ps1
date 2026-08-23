# Stops the dev server started by scripts/dev_start_server.ps1.
if (Test-Path "uvicorn.pid") {
    $pidVal = Get-Content "uvicorn.pid"
    Stop-Process -Id $pidVal -Force -ErrorAction SilentlyContinue
    Remove-Item "uvicorn.pid" -ErrorAction SilentlyContinue
    Write-Host "Stopped uvicorn (PID=$pidVal)"
} else {
    Write-Host "No uvicorn.pid found -- server may not be running."
}
