Write-Host "=========================================================================" -ForegroundColor Cyan
Write-Host " Starting AURA-Grid Production Server (FastAPI + React Glassmorphism)" -ForegroundColor Green
Write-Host " Dashboard UI: http://localhost:8000" -ForegroundColor Yellow
Write-Host " Interactive API Docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host "=========================================================================" -ForegroundColor Cyan

Set-Location "$PSScriptRoot"
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
