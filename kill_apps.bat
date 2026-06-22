@echo off
echo ===================================================
echo   Bishwayan's App Killer - Stopping Dev Servers
echo ===================================================

echo.
echo Stopping Node.js (React/Vite Frontend)...
taskkill /F /IM node.exe /T >nul 2>&1

echo.
echo Stopping Python (FastAPI Backend)...
taskkill /F /IM python.exe /T >nul 2>&1

echo.
echo All development apps have been terminated.
pause
