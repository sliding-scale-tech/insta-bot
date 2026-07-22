#!/bin/bash
set -e
# Start a virtual display so Chrome can run HEADED (not headless) on the server.
# Headed + Xvfb dodges Instagram's headless-browser detection while still
# needing no physical monitor.
Xvfb :99 -screen 0 1280x800x24 -ac +extension GLX +render -noreset &
echo "[start] Xvfb :99 (1280x800x24)"
sleep 1
exec python -m uvicorn server.main:app --host 0.0.0.0 --port 8000
