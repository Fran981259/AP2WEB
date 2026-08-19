#!/usr/bin/env bash
# Encerra os servidores do AP2WEB.
pkill -f "uvicorn app.main" 2>/dev/null || true
pkill -f "node.*vite" 2>/dev/null || true
sleep 1
echo "Servidores do AP2WEB encerrados."
