# Advanced Docker Compose Patterns

## Multi-Environment Setup with Compose

Directory structure:
```
project/
├── docker-compose.yml          # Base configuration
├── docker-compose.override.yml # Development overrides
├── docker-compose.prod.yml     # Production config
└── docker-compose.test.yml     # Test environment
```

**Base (docker-compose.yml):**
```yaml
version: "3.9"

services:
  app:
    build: .
    environment:
      - ENVIRONMENT
      - LOG_LEVEL
    networks:
      - internal

  db:
    image: postgres:17-alpine
    environment:
      - POSTGRES_DB
      - POSTGRES_USER
      - POSTGRES_PASSWORD
    volumes:
      - data:/var/lib/postgresql/data
    networks:
      - internal

volumes:
  data:

networks:
  internal:
```

**Development Override (docker-compose.override.yml):**
```yaml
services:
  app:
    ports:
      - "8000:8000"
    environment:
      - ENVIRONMENT=development
      - LOG_LEVEL=DEBUG
    volumes:
      - ./app:/app
    command: python -m uvicorn app.main:app --reload --host 0.0.0.0

  db:
    ports:
      - "5432:5432"
```

**Production (docker-compose.prod.yml):**
```yaml
services:
  app:
    restart: always
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: "1"
          memory: 512M
    environment:
      - ENVIRONMENT=production
      - LOG_LEVEL=INFO

  db:
    restart: always
    volumes:
      - data:/var/lib/postgresql/data
```

Usage:
```bash
# Development
docker compose up

# Production
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## Scaling Services

```yaml
services:
  app:
    build: .
    ports:
      - "8000-8002:8000"  # Maps 8000-8002 on host to 8000 in container
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
```

## Volume Types

**Named volume (persistent, managed by Docker):**
```yaml
volumes:
  db_data:
    driver: local
```

**Bind mount (development):**
```yaml
volumes:
  - ./src:/app/src  # host:container
```

**Temporary volume (ephemeral):**
```yaml
volumes:
  - /tmp/cache  # Only in container, lost on restart
```

## Networking Patterns

**Frontend + Backend + Database isolation:**
```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge

services:
  web:
    networks:
      - frontend

  api:
    networks:
      - frontend
      - backend

  db:
    networks:
      - backend
```

**External network (for inter-project communication):**
```yaml
services:
  app:
    networks:
      - shared_network

networks:
  shared_network:
    external: true
```

Create with: `docker network create shared_network`

## Conditional Services (Override Only)

In `docker-compose.override.yml` (dev), add extra services:

```yaml
services:
  adminer:
    image: adminer
    ports:
      - "8080:8080"
    depends_on:
      - db
    networks:
      - internal

  mailhog:
    image: mailhog/mailhog
    ports:
      - "1025:1025"
      - "8025:8025"
    networks:
      - internal
```

These are ignored in production unless explicitly included with `-f`.

## Secrets Management

**Development (.env file):**
```
DB_USER=app
DB_PASSWORD=app_password
```

```yaml
services:
  app:
    env_file:
      - .env
```

**Production (Docker secrets for Swarm):**
```bash
echo "app_password" | docker secret create db_password -
```

```yaml
services:
  app:
    environment:
      - DB_PASSWORD_FILE=/run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    external: true
```

## Health Checks and Restart Policy

```yaml
services:
  app:
    restart: unless-stopped  # Restart on failure unless manually stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 40s
    depends_on:
      db:
        condition: service_healthy

  db:
    restart: always
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "postgres"]
      interval: 5s
      timeout: 5s
      retries: 5
```

## Labels for Logging and Monitoring

```yaml
services:
  app:
    labels:
      - "com.example.app=myapp"
      - "com.example.version=1.0"
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

