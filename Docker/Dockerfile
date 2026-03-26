# =============================================================================
# RecommendMe API — Dockerfile
# =============================================================================
# Builds a minimal production-ready image using Python 3.12-slim.
#
# NOTE: Automatic deployment via Docker is intentionally disabled during the
# development phase.  This image can be built and run locally, but the CI/CD
# pipeline will not push or deploy it until the deploy workflow is re-enabled.
# See .github/workflows/deploy.yml for details.
#
# Local development usage (from repository root):
#   docker build -f Docker/Dockerfile -t recommendme-api .
#   docker run --env-file .env -p 8000:8000 recommendme-api
#
# Or, to include Redis:
#   docker compose up --build
# =============================================================================

FROM python:3.12-slim

WORKDIR /app

# Install minimal OS-level build tools required by some Python packages
# (e.g. pydantic-core).  The apt cache is cleaned in the same layer to keep
# the image size small.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies before copying application source so Docker can
# cache this layer and avoid reinstalling on every code change.
COPY Requirements/requirements.txt /app/Requirements/requirements.txt
RUN pip install --no-cache-dir -r /app/Requirements/requirements.txt

# Copy app source and selected runtime assets.
COPY app /app/app
COPY start.sh /app/start.sh
COPY railway.toml /app/railway.toml
COPY Environment /app/Environment

# Ensure startup script can be executed by the container runtime.
RUN chmod +x /app/start.sh

# Expose the port the Uvicorn server listens on.
EXPOSE 8000

# -----------------------------------------------------------------------------
# Production start command.
#
# Deployment temporarily disabled during development phase.
# This command will be used once backend integration is completed and
# the service has been fully tested.
# -----------------------------------------------------------------------------
CMD ["/app/start.sh"]
