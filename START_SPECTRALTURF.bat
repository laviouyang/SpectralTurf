@echo off
REM ============================================================
REM  SpectralTurf - one-click start
REM  Put this file in D:\Lavi\SpectralTurf and double-click it.
REM  It opens 3 windows: Backend, Frontend, and Claude Code,
REM  then opens the app in your browser.
REM  To stop everything: close the windows (or press Ctrl+C in each).
REM ============================================================

set PROJECT=D:\Lavi\SpectralTurf

REM 1) Backend (Python / FastAPI) on port 8000
start "SpectralTurf Backend" cmd /k "cd /d %PROJECT%\backend && call venv\Scripts\activate.bat && uvicorn main:app --reload"

REM 2) Frontend (React / Vite) on port 5173
start "SpectralTurf Frontend" cmd /k "cd /d %PROJECT%\frontend && npm run dev"

REM 3) Claude Code, continuing your last conversation
start "Claude Code" cmd /k "cd /d %PROJECT% && claude --continue"

REM 4) Give the servers a few seconds, then open the app
timeout /t 8 /nobreak >nul
start "" http://localhost:5173
