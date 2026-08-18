#!/bin/bash

echo "Cleaning up any existing Uvicorn processes on ports 8000 and 8001..."
kill $(lsof -ti :8000 -ti :8001) 2>/dev/null
sleep 1

echo "Starting ML service on port 8001..."
(cd ml && uvicorn api.main:app --port 8001) &
ML_PID=$!

echo "Starting Backend service on port 8000..."
(cd backend && uvicorn src.server:app --port 8000) &
BACKEND_PID=$!


echo "Waiting 4 seconds for servers to fully initialize..."
sleep 4

echo "Executing proxy request to Backend (which should forward to ML service)..."
echo "--------------------------------------------------"
curl -s -w "\nHTTP_STATUS:%{http_code}\n" http://localhost:8000/api/v1/forecast/22222222-2222-2222-2222-222222222222
echo "--------------------------------------------------"

echo "Shutting down test servers..."
kill $ML_PID $BACKEND_PID 2>/dev/null
echo "Test complete."
