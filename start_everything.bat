@echo off
echo ===================================================
echo   TypeMAX by Bishwayan - Startup Script
echo ===================================================

echo.
echo Please ensure your PostgreSQL and Redis servers are currently running!
echo.
pause

echo.
echo Starting Backend API and Batch Processor...
cd backend
start make start-all
cd ..

echo.
echo Starting React Frontend...
cd frontend
start npm run dev
cd ..

echo.
echo All services are launching in separate windows!
echo Once the Vite server starts, open the local URL (usually http://localhost:5173) in your browser.
pause
