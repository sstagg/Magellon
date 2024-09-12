@echo off


rmdir /s /q .\consul\data
mkdir .\consul\data
REM Step 1: Start Docker Compose
REM docker-compose  up -d
docker-compose --profile default up -d

REM Step 2: Wait for services to be ready
timeout /t 15



REM Step 3: Open browser with links
start chrome "http://localhost:8080/en/panel/images"
start chrome "http://localhost:8000"
start chrome "http://localhost:15672"
start chrome "http://localhost:8500"
REM start chrome "http://localhost:3000"
REM start chrome "http://localhost:9090"
