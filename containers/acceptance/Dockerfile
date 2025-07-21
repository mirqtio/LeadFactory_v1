# Multi-stage Dockerfile for Acceptance Runner
# PRP-1060: Containerized acceptance testing and SSH deployment automation

# Stage 1: Builder
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    ssh \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash acceptance

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim as runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    git \
    ssh \
    curl \
    postgresql-client \
    redis-tools \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash acceptance

# Copy Python packages from builder
COPY --from=builder /root/.local /home/acceptance/.local

# Set up environment
ENV PATH="/home/acceptance/.local/bin:$PATH"
ENV PYTHONPATH="/app:$PYTHONPATH"

# Create SSH directory with proper permissions
RUN mkdir -p /home/acceptance/.ssh && \
    chown -R acceptance:acceptance /home/acceptance/.ssh && \
    chmod 700 /home/acceptance/.ssh

# Create workspace directory
RUN mkdir -p /workspace && \
    chown -R acceptance:acceptance /workspace

# Switch to non-root user
USER acceptance
WORKDIR /workspace

# Copy application code
COPY --chown=acceptance:acceptance . /app/

# Copy entrypoint script
COPY --chown=acceptance:acceptance entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Container metadata
LABEL maintainer="LeadFactory Team"
LABEL description="Acceptance testing and deployment automation runner"
LABEL version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/leadfactory/acceptance-runner"

# Set entrypoint
ENTRYPOINT ["/entrypoint.sh"]
CMD ["acceptance_runner.py"]