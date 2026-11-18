# Production-Ready Examples

## Python FastAPI Production Setup

### Dockerfile.prod

```dockerfile
# syntax=docker/dockerfile:1.4

FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
      gcc \
      python3-dev \
  && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Runtime stage
FROM python:3.12-slim

WORKDIR /app

LABEL org.opencontainers.image.title="fastapi-app" \
      org.opencontainers.image.description="Production-ready FastAPI application" \
      org.opencontainers.image.vendor="MyCompany"

# Environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/appuser/.local/bin:$PATH"

# System dependencies only
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
      curl \
  && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /home/appuser/.local

# Application code
COPY --chown=appuser:appuser ./app /app

# Create non-root user
RUN groupadd -r appuser && \
    useradd -r -g appuser -u 1000 appuser

USER appuser

EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Use exec form for proper signal handling
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.prod.yml

```yaml
version: "3.9"

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile.prod
      args:
        ENVIRONMENT: production
    container_name: fastapi_app_prod
    restart: unless-stopped
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    networks:
      - app
    deploy:
      resources:
        limits:
          cpus: "1"
          memory: 512M
        reservations:
          cpus: "0.5"
          memory: 256M

  db:
    image: postgres:17-alpine
    container_name: fastapi_db_prod
    restart: always
    environment:
      POSTGRES_DB: appdb
      POSTGRES_USER: appuser
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    volumes:
      - db_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql
    secrets:
      - db_password
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "appuser"]
      interval: 10s
      timeout: 5s
      retries: 5
    networks:
      - app
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 1G

volumes:
  db_data:
    driver: local

secrets:
  db_password:
    external: true

networks:
  app:
    driver: bridge
```

### .dockerignore

```
.git
.gitignore
.github
.vscode
__pycache__
*.pyc
*.pyo
*.pyd
.Python
env/
venv/
.env
.pytest_cache
.coverage
htmlcov/
dist/
build/
*.egg-info/
.DS_Store
tests/
docs/
README.md
LICENSE
Makefile
.env.local
.env.*.local
```

---

## Node.js Production Setup

### Dockerfile.prod

```dockerfile
FROM node:20-alpine AS dependencies

WORKDIR /app

COPY package*.json ./
RUN npm ci --only=production

# Builder stage
FROM node:20-alpine AS builder

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

LABEL org.opencontainers.image.title="nodejs-app" \
      org.opencontainers.image.description="Production-ready Node.js application"

ENV NODE_ENV=production

COPY --from=dependencies /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package*.json ./

# Non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001
USER nodejs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

CMD ["node", "dist/index.js"]
```

### .dockerignore

```
.git
.gitignore
.github
node_modules
npm-debug.log
.env
.env.local
.env.*.local
coverage/
dist/
build/
.vscode
.next
out/
.DS_Store
*.log
README.md
LICENSE
.gitattributes
.editorconfig
tests/
.renovaterc*
docker-compose*.yml
Dockerfile*
.dockerignore
```

---

## Setup Production Secrets (Docker Swarm/Kubernetes)

### Docker Swarm

```bash
# Create secret
echo "secure_password_123" | docker secret create db_password -

# List secrets
docker secret ls

# Deploy stack
docker stack deploy -c docker-compose.prod.yml myapp
```

### Kubernetes

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
type: Opaque
stringData:
  password: "secure_password_123"
```

Then in Deployment:
```yaml
containers:
- name: app
  env:
  - name: DB_PASSWORD
    valueFrom:
      secretKeyRef:
        name: db-credentials
        key: password
```

---

## Pre-Production Checklist

- [ ] Base image pinned to minor version or specific digest
- [ ] Multi-stage build reduces final image to <500MB
- [ ] .dockerignore excludes all unnecessary files
- [ ] Non-root user created and used
- [ ] No secrets in Dockerfile or env files
- [ ] Healthcheck configured and tested
- [ ] ENTRYPOINT/CMD in exec form
- [ ] OCI labels included
- [ ] Resource limits defined (CPU, memory)
- [ ] Restart policies configured
- [ ] Log driver configured (json-file, awslogs, etc.)
- [ ] Network segmentation applied
- [ ] Database user/password randomized for prod
- [ ] Vulnerability scanning passes (Trivy, Scout)
- [ ] Tested locally with production Compose
- [ ] Secrets injected via orchestrator, not .env
