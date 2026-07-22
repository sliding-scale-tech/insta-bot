# Backend only — FastAPI API + Playwright browser automation.
# The React dashboard is deployed separately (Vercel); it talks to this
# container's API/WebSocket over the network.
#
# Base image matches the Playwright floor in requirements.txt (>=1.48.0).
FROM mcr.microsoft.com/playwright/python:v1.48.0-jammy

ENV DISPLAY=:99
ENV ENV=production
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUNBUFFERED=1

# Xvfb = virtual display so a HEADED (non-headless) Chrome can run on a server
# with no monitor. Headed avoids Instagram's headless-bot detection.
RUN apt-get update && apt-get install -y xvfb && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-server.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-server.txt

# Match the Chromium build to whatever Playwright version pip resolved.
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 8000

COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
