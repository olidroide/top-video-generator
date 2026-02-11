---
name: docker-best-practices
description: Design, review, and optimize Dockerfiles, Docker images, and Docker Compose configurations for production, performance, and maintainability. Use when auditing Docker configurations, creating production-ready images, designing multi-container architectures, or implementing container orchestration with focus on security, reproducibility, minimal attack surface, build optimization, and observability.
---

# Docker Best Practices

## Overview

This skill guides you through designing and optimizing Docker configurations with a focus on:

- **Production readiness**: Security, reproducibility, observability
- **Performance**: Build time optimization, minimal image size
- **Maintainability**: Clear structure, consistency, clean separation of concerns

Targeted at backend developers and DevOps engineers deploying containerized services (Python/FastAPI, Node.js, Go) to Docker/Kubernetes environments.

## When to Use This Skill

Activate when users:

- Ask to review or optimize a Dockerfile or Docker Compose configuration
- Want "best practices" for images, builds, or deployments
- Question multi-stage builds, base image selection, or .dockerignore strategy
- Need examples for containerized backend + database setups
- Ask conceptual Docker questions (images, containers, volumes, networks) with practical application focus

## General Behavior

When responding under this skill:

1. **Clarify minimal context** before prescriptive advice:
   - Language/platform (Python/FastAPI, Node, Go, etc.)
   - Environment (local development, CI, production VM, Kubernetes)
   - Key non-functional requirements (build time, security, size)

2. **Prioritize production over "works on my machine"**:
   - Reproducibility (pinned versions, deterministic builds)
   - Security defaults (non-root user, secret management, trusted images)
   - Observability (healthchecks, stdout logging, OCI labels)

3. **Balance conciseness with depth**:
   - Start with a **checklist summary**
   - Detail with concrete examples (Dockerfile, compose.yml)
   - Point toward idiomatic code aligned with clean architecture (app logic separated from infrastructure)

4. **Avoid anti-patterns explicitly**:
   - Explain **why** something is problematic (security, performance, debugging)
   - Propose a clear, immediately actionable alternative

---

## Key Docker Image Practices

### Minimal Base Images

- **Compiled languages (Go, Rust)**: Use `distroless` or `scratch` for runtime when possible—reduces attack surface and image size dramatically.
- **Interpreted languages (Node, Python)**: Prefer `-alpine` or `-slim` variants for production unless specific compatibility issues exist (e.g., glibc requirements on Alpine).

**Example (Python):**
```dockerfile
FROM python:3.12-slim
```

### Multi-Stage Builds

Separate builder stage (heavy dependencies) from runtime stage (minimal set only):

```dockerfile
FROM python:3.12-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY app/ .
USER appuser
CMD ["python", "app.py"]
```

### Layer Caching Optimization

Order layers by change frequency: rarely-changed to frequently-changed.

```dockerfile
# Good: dependencies first (rarely change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then application code (frequently changes)
COPY . .
```

### Reduce Layer Count

Combine related RUN commands in a single instruction, cleaning up in the same step:

```dockerfile
# Better than separate RUN commands
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl git \
 && rm -rf /var/lib/apt/lists/*
```

### Explicit Copying and .dockerignore

Use `.dockerignore` aggressively to exclude non-essential files:

```
.git
.gitignore
*.md
tests/
*.pyc
__pycache__
.env
.aws/
node_modules/
dist/
build/
```

Avoid `COPY . .` when possible; copy only what's needed:

```dockerfile
COPY requirements.txt .
COPY src/ ./app/
```

### Use WORKDIR Convention

Always use `WORKDIR` instead of `cd`:

```dockerfile
WORKDIR /app
# All subsequent commands run in /app context
COPY . .
```

### CMD/ENTRYPOINT in Exec Form

Always use array syntax so signals are passed correctly to the application:

```dockerfile
# Good
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Avoid
CMD uvicorn app.main:app --host 0.0.0.0 --port 8000
```

---

## Security and Hardening

### Run as Non-Root

Create a dedicated application user and run the container as that user:

```dockerfile
RUN useradd -m appuser && chown -R appuser /app
USER appuser
```

Pattern: Root owns binaries and code (read-only), application user executes only.

### Pin Base Image Versions

Never use `latest`; pin to major.minor at minimum, consider patch for maximum reproducibility:

```dockerfile
FROM python:3.12-slim  # Better than python:latest
# OR for reproducibility
FROM python:3.12.1-slim@sha256:abc123...
```

### Minimize "Attacker Toolkit"

Avoid including debugging tools (`curl`, `wget`, `nc`) unless necessary. For debugging, use ephemeral containers attached to the network:

```bash
docker run --rm -it --network app-network nicolaka/netshoot
```

### Secret Management

**Never**:
- `ENV API_KEY=secret` in Dockerfile
- Copy `.env` files into image
- Hardcode tokens or credentials

**Do**:
- Inject secrets at runtime via environment variables
- Use orchestrator secrets (Kubernetes, Docker Swarm)
- For advanced builds: use BuildKit secrets (`RUN --mount=type=secret=...`)

---

## Performance Optimization

### Build Time

- **Layer caching**: Order Dockerfile to cache frequently-used layers early
- **.dockerignore**: Reduce build context size
- **CI caching**: Cache layers in registry, reuse across builds

### Image Size

- Multi-stage builds (builder vs. runtime)
- Clean package caches in the same layer:
  ```dockerfile
  RUN pip install --no-cache-dir -r requirements.txt
  ```
- Drop development tools from production image
- Use `distroless` or `-alpine` base images

### Vulnerability Scanning

Integrate tools into CI pipeline (Trivy, Docker Scout, Grype) without requiring detailed setup in the skill—mention as part of the production pipeline.

---

## Runtime, Observability, and Maintainability

### Healthchecks

Add HEALTHCHECK for production images:

```dockerfile
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
```

### OCI Labels

Include metadata for traceability:

```dockerfile
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

LABEL org.opencontainers.image.title="my-app" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.source="https://github.com/user/repo" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"
```

### Code Clarity

- Organize Dockerfile logically: base image → dependencies → build → runtime
- Sort package lists alphabetically (improves diffs)
- Comment decisions, not the obvious

---

## Docker Compose Best Practices

### One Container, One Responsibility

Separate services: backend, database, queue, reverse proxy in different containers. Never combine DB + app in one container.

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"

  db:
    image: postgres:17
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

### Use Service Names as Hostnames

Within a Compose network, reference services by name:

```yaml
environment:
  DB_HOST=db  # resolved to db service
  DB_PORT=5432
```

### Environment Separation

Use `compose.override.yml`, `.dev.yml`, `.prod.yml`:

```bash
docker compose -f compose.yml -f compose.prod.yml up
```

Or centralize via `.env`, explaining security implications (dev only; use orchestrator secrets in production).

### Volumes for Persistence, Not Convenience

- **Bind mounts** for code: development only (hot reload)
- **Named volumes** for data: databases, caches

```yaml
volumes:
  backend:
    - ./backend:/app  # dev only
  db:
    - db_data:/var/lib/postgresql/data  # persistent
```

### Dependency Management

`depends_on` ensures service start order but doesn't wait for readiness. Pair with healthchecks and retry logic in the application:

```yaml
services:
  backend:
    depends_on:
      db:
        condition: service_healthy

  db:
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
      retries: 5
```

### Networking

Use explicit networks for multi-tier architectures:

```yaml
networks:
  frontend:
  backend:
  data:

services:
  web:
    networks:
      - frontend
  app:
    networks:
      - frontend
      - backend
  db:
    networks:
      - backend
      - data
```

### Expose Only Necessary Ports

```yaml
services:
  db:
    # Don't expose ports unless needed from host
    ports:
      - "5432:5432"  # only if required
```

For inter-container communication, omit `ports` and rely on Compose network resolution.

---

## Example: FastAPI + PostgreSQL Compose

```yaml
version: "3.9"

services:
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: app_backend
    environment:
      - DB_HOST=db
      - DB_PORT=5432
      - DB_USER=app
      - DB_PASSWORD=app_password
      - DB_NAME=app_db
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./backend:/app  # dev only
    networks:
      - app

  db:
    image: postgres:17-alpine
    container_name: app_db
    environment:
      - POSTGRES_DB=app_db
      - POSTGRES_USER=app
      - POSTGRES_PASSWORD=app_password
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "app"]
      interval: 5s
      timeout: 5s
      retries: 5
    networks:
      - app

volumes:
  db_data:

networks:
  app:
    driver: bridge
```

**For production**, remove:
- Bind mounts for code
- Exposed database ports
- Password in environment variables (use secrets)

---

## Anti-Patterns to Avoid

| Anti-Pattern | Why It's Bad | Alternative |
|---|---|---|
| `FROM python:latest` | Non-reproducible, breaks unexpectedly | Pin version: `FROM python:3.12-slim` |
| `RUN apt-get install ...` without cleanup | Bloats image with caches | Combine commands: `RUN apt-get update && apt-get install ... && rm -rf /var/lib/apt/lists/*` |
| `COPY . .` | Includes unwanted files (tests, .git, etc.) | Use `.dockerignore` and selective `COPY` |
| `CMD uvicorn ...` | Shell form doesn't pass signals | Use exec form: `CMD ["uvicorn", ...]` |
| `ENV SECRET=value` | Credentials leak in image history | Use runtime secrets injection |
| Root user in container | Risk of privilege escalation | `USER appuser` after setup |
| Database + app in one container | Violates separation of concerns | Use Compose with separate services |
| No healthchecks | Orchestrator can't recover failed services | Add HEALTHCHECK or service health config |

---

## Advanced and Extended Resources

For deeper guidance on specific topics, refer to:

- **[dockerfile-patterns.md](references/dockerfile-patterns.md)**: Multi-stage builds for Node.js, Go, Python; conditional build steps; BuildKit secrets
- **[compose-patterns.md](references/compose-patterns.md)**: Multi-environment setups, scaling, networking, secrets management, logging
- **[pitfalls.md](references/pitfalls.md)**: 10 common mistakes with concrete before/after solutions
- **[production-examples.md](references/production-examples.md)**: Complete FastAPI and Node.js production setups, pre-deployment checklist

### Tooling

- **[scripts/dockerfile-linter.py](scripts/dockerfile-linter.py)**: Automated script to check Dockerfiles for security, performance, and best practices violations

---

## Quick Checklist

- [ ] Base image pinned, minimal (`-slim`, `-alpine`, `distroless`)
- [ ] Multi-stage build if applicable
- [ ] Layers ordered: dependencies first, code last
- [ ] `.dockerignore` excludes `.git`, tests, `.env`
- [ ] Non-root user, explicit permissions
- [ ] CMD in exec form (array syntax)
- [ ] Secrets injected at runtime, never hardcoded
- [ ] HEALTHCHECK included for production
- [ ] OCI labels with version/source metadata
- [ ] Compose: one service per responsibility
- [ ] Compose: volumes for persistence, bind mounts for dev only
- [ ] Secrets in production come from orchestrator
- [ ] Tested on target environment before deployment

