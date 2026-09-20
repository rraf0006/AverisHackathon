# One container: API + dashboard. Backup host for Render, Koyeb, Fly.io or any
# Docker host. The live demo runs on Vercel (see docs/DEPLOY.md) and uses
# api/index.py instead — this file is not used there.
FROM python:3.12-slim

RUN useradd -m -u 1000 user
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user src/ src/
COPY --chown=user scripts/ scripts/
COPY --chown=user data/ data/
USER user

# Most container hosts set $PORT themselves; 7860 is just a default.
ENV PORT=7860 PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["sh", "-c", "uvicorn app.api:app --app-dir src --host 0.0.0.0 --port ${PORT}"]
