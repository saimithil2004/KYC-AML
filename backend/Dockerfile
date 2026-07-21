# ─── BUILD STAGE ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ─── RUN STAGE ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runner

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed libraries from builder stage
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Create non-root system user
RUN groupadd -g 10001 compliance && \
    useradd -u 10001 -g compliance -s /bin/sh -m compliance_user

COPY . .

# Setup permissions for uploads and logs directories
RUN mkdir -p uploads logs shared_docs backups && \
    chown -R compliance_user:compliance /app

USER compliance_user

EXPOSE 8000

# Health check setup
HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health/live || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
