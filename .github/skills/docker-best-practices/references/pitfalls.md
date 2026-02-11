# Common Docker Pitfalls and Solutions

## Pitfall 1: Large Images

**Problem:**
```dockerfile
FROM ubuntu:22.04
RUN apt-get update && apt-get install -y build-essential python3 python3-pip
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt
CMD ["python3", "app.py"]
```

Result: Image size **~1GB** due to build tools and full Ubuntu base.

**Solution:** Multi-stage with minimal base
```dockerfile
FROM ubuntu:22.04 AS builder
RUN apt-get update && apt-get install -y build-essential python3 python3-pip
COPY requirements.txt /
RUN pip install --target=/dependencies -r /requirements.txt

FROM python:3.12-slim
COPY --from=builder /dependencies /usr/local/lib/python3.12/site-packages
COPY app/ /app
WORKDIR /app
CMD ["python", "app.py"]
```

Result: Image size **~200MB**.

---

## Pitfall 2: Signal Handling Issues

**Problem:**
```dockerfile
CMD uvicorn app.main:app
```

When the container receives SIGTERM, the shell process ignores it (PID 1 is shell, not uvicorn). Application doesn't shut down gracefully.

**Solution:** Use exec form
```dockerfile
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0"]
```

Now uvicorn is PID 1 and receives signals directly.

---

## Pitfall 3: No .dockerignore

**Problem:**
```dockerfile
COPY . .
```

Copies everything including `.git/` (adds 50MB+), `node_modules/`, `__pycache__/`, test files, etc. Invalidates layer cache on every code change.

**Solution:** Create .dockerignore
```
.git
.gitignore
.github
.env
*.log
tests/
docs/
build/
dist/
node_modules/
__pycache__/
*.pyc
.pytest_cache/
```

---

## Pitfall 4: Running as Root

**Problem:**
```dockerfile
# Default: app runs as root
CMD ["python", "app.py"]
```

If attacker gains access, they have root. Can modify binaries, access all system resources.

**Solution:** Create unprivileged user
```dockerfile
RUN useradd -m -u 1000 appuser
WORKDIR /app
COPY . .
RUN chown -R appuser:appuser /app
USER appuser
CMD ["python", "app.py"]
```

---

## Pitfall 5: Secrets in Environment Variables

**Problem:**
```dockerfile
ENV DATABASE_PASSWORD=my_secret_123
```

Secret embedded in image layers and visible in image history:
```bash
docker history myimage
IMAGE           CREATED         CREATED BY                   SIZE
...             2 days ago      /bin/sh -c #(nop) ENV ...   my_secret_123
```

**Solution:** Inject at runtime
```dockerfile
# Dockerfile has no secret
CMD ["python", "app.py"]
```

Run container with:
```bash
docker run -e DATABASE_PASSWORD="my_secret_123" myimage
```

Or use Docker secrets (Swarm/Kubernetes).

---

## Pitfall 6: No Healthcheck

**Problem:**
```yaml
services:
  app:
    depends_on:
      - db
```

Container starts but app crashes after 5s. Compose doesn't detect failure; orchestrator can't restart.

**Solution:** Add healthcheck
```yaml
services:
  app:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
    depends_on:
      db:
        condition: service_healthy

  db:
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
      retries: 5
```

---

## Pitfall 7: Database + App in One Container

**Problem:**
```dockerfile
FROM ubuntu:22.04
RUN apt-get install -y postgresql python3 python3-pip
COPY . /app
CMD ["sh", "-c", "service postgresql start && python3 app.py"]
```

Issues:
- No container isolation
- Scaling app scales database (wasteful)
- Logs mixed
- Harder to debug

**Solution:** Separate containers
```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"

  db:
    image: postgres:17-alpine
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

---

## Pitfall 8: Unguarded Package Caches

**Problem:**
```dockerfile
RUN apt-get update
RUN apt-get install -y build-essential python3
# Cache files remain in /var/lib/apt/lists (~150MB)
```

**Solution:** Clean in same layer
```dockerfile
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential python3 \
 && rm -rf /var/lib/apt/lists/*
```

Or use BuildKit:
```dockerfile
RUN --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && apt-get install -y build-essential
```

---

## Pitfall 9: No OCI Labels

**Problem:**
```dockerfile
FROM python:3.12-slim
# No metadata; image provenance unknown
```

Deployed image has no way to identify version, build date, source repo.

**Solution:** Add labels
```dockerfile
ARG VERSION=unknown
ARG BUILD_DATE
ARG VCS_REF

LABEL org.opencontainers.image.title="myapp" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.source="https://github.com/myorg/myapp" \
      org.opencontainers.image.revision="${VCS_REF}"
```

In CI:
```bash
docker build \
  --build-arg VERSION=1.0.0 \
  --build-arg BUILD_DATE=$(date -u +'%Y-%m-%dT%H:%M:%SZ') \
  --build-arg VCS_REF=$(git rev-parse --short HEAD) \
  -t myapp:1.0.0 .
```

---

## Pitfall 10: Exposed Database Ports in Production

**Problem:**
```yaml
services:
  db:
    image: postgres:17
    ports:
      - "5432:5432"  # Database exposed to host and internet
```

Anyone can connect to database if host is accessible.

**Solution:** Expose only what's needed; use networks
```yaml
services:
  db:
    image: postgres:17
    # No ports section; db only accessible from app service
    networks:
      - backend

  app:
    networks:
      - frontend
      - backend
    ports:
      - "8000:8000"  # Only app exposed

networks:
  frontend:
  backend:
```

