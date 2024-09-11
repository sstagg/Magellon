@echo off

REM Step 1: Start Docker Compose
docker-compose --profile default up -d

REM Step 2: Wait for services to be ready
timeout /t 15

REM Step 3: Open browser with links
start chrome "http://localhost:8080"
start chrome "http://localhost:8000"
start chrome "http://localhost:15672"
