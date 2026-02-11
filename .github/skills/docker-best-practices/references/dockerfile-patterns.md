# Advanced Dockerfile Patterns

## Node.js Multi-Stage Build

```dockerfile
FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build application
COPY . .
RUN npm run build

# Runtime stage
FROM node:20-alpine

WORKDIR /app

# Copy only production dependencies
COPY package*.json ./
RUN npm ci --omit=dev

# Copy built artifacts from builder
COPY --from=builder /app/dist ./dist

# Non-root user
RUN addgroup -g 1001 -S nodejs && \
    adduser -S nodejs -u 1001

USER nodejs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/health', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})"

CMD ["node", "dist/index.js"]
```

## Go Multi-Stage Build with Scratch

```dockerfile
FROM golang:1.22-alpine AS builder

WORKDIR /build

COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -a -installsuffix cgo -o app .

# Minimal runtime image
FROM scratch

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/
COPY --from=builder /build/app /app

EXPOSE 8000

ENTRYPOINT ["/app"]
```

## Python with Distroless

```dockerfile
FROM python:3.12 AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM gcr.io/distroless/python3.12

WORKDIR /app

COPY --from=builder /root/.local /root/.local
COPY --from=builder /build/app ./app

ENV PATH=/root/.local/bin:$PATH
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["python", "-m", "app.main"]
```

## Conditional Build Steps

Use build arguments to control behavior:

```dockerfile
ARG INSTALL_DEV_TOOLS=false

RUN if [ "$INSTALL_DEV_TOOLS" = "true" ]; then \
      apt-get install -y curl wget; \
    fi
```

Build with: `docker build --build-arg INSTALL_DEV_TOOLS=true .`

## BuildKit Secrets

For sensitive build-time secrets (not in final image):

```dockerfile
# syntax=docker/dockerfile:1.4

RUN --mount=type=secret,id=npmrc,target=/root/.npmrc \
    npm ci --prefer-offline --no-audit
```

Build with: `docker build --secret npmrc=~/.npmrc .`

