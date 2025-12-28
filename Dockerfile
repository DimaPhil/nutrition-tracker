# syntax=docker/dockerfile:1

FROM python:3.13-slim AS base

# Prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Create non-root user for security
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --gid 1001 appuser

# ============================================================================
# Development stage
# ============================================================================
FROM base AS development

# Install dev dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

COPY . .

USER appuser

CMD ["pytest"]

# ============================================================================
# Production stage
# ============================================================================
FROM base AS production

# Install only production dependencies
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

USER appuser

ENTRYPOINT ["nutrition-tracker"]
