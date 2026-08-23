# =============================================================================
# DocuMind AI Backend — Dev server launcher (Windows PowerShell)
# =============================================================================
# Starts `uvicorn main:app` as a detached background process (so the
# launching shell/terminal can be closed or reused for other commands),
# redirecting stdout/stderr to uvicorn_out.log / uvicorn_err.log and
# recording the PID in uvicorn.pid.
#
# Usage:
#   .\scripts\dev_start_server.ps1
#   .\scripts\dev_stop_server.ps1
# =============================================================================
param(
    [string]$Host_ = "0.0.0.0",
    [int]$Port = 8000
)

$proc = Start-Process -FilePath "py" `
    -ArgumentList "-3.11", "-m", "uvicorn", "main:app", "--host", $Host_, "--port", $Port `
    -WorkingDirectory (Get-Location) `
    -RedirectStandardOutput "uvicorn_out.log" `
    -RedirectStandardError "uvicorn_err.log" `
    -PassThru
$proc.Id | Out-File -Encoding ascii "uvicorn.pid"
Write-Host "Started uvicorn (PID=$($proc.Id)) -- logs: uvicorn_out.log / uvicorn_err.log"
Write-Host "Health check:  curl http://localhost:$Port/health"
Write-Host "Swagger UI:    http://localhost:$Port/docs"
