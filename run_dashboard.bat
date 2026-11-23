@echo off
title AURA-Grid | Microgrid Formal Runtime Assurance Dashboard
echo =========================================================================
echo  Starting AURA-Grid Production Server (FastAPI + React Glassmorphism)
echo  Dashboard UI: http://localhost:8000
echo  Interactive API Docs: http://localhost:8000/docs
echo =========================================================================
cd /d "%~dp0"
python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
pause
