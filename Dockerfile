# syntax=docker/dockerfile:1.10

FROM python:3.13.9-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.4 /uv /uvx /bin/

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PATH="/app/.venv/bin:/bin:$PATH"

WORKDIR /app

RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libzmq3-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libopenjp2-7-dev \
    libtiff-dev \
    tk-dev \
    tcl-dev \
    libwebp-dev \
    libharfbuzz-dev \
    libfribidi-dev \
    libxcb1-dev \
    pkg-config

COPY pyproject.toml uv.lock README.md LICENSE /app/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --extra instagram --extra tiktok --no-install-project

COPY ./src /app/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-dev --frozen --extra instagram --extra tiktok

FROM python:3.13.9-slim-bookworm
LABEL MAINTAINER="top-video-generator@olidroide.es"
LABEL org.opencontainers.image.source="https://github.com/olidroide/top-video-generator"
LABEL org.opencontainers.image.description="Automated trending music video pipeline"

ENV PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    IMAGEIO_FFMPEG_EXE="/usr/bin/ffmpeg" \
    PLAYWRIGHT_BROWSERS_PATH="/ms-playwright" \
    MAGICK_HOME="/usr" \
    MAGICK_CONFIGURE_PATH="/etc/ImageMagick-6" \
    FONTCONFIG_PATH="/etc/fonts"

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

# Install only runtime dependencies (no build tools)
RUN --mount=type=cache,target=/var/cache/apt \
    --mount=type=cache,target=/var/lib/apt/lists \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    libzmq5 \
    libjpeg62-turbo \
    zlib1g \
    libpng16-16 \
    libfreetype6 \
    liblcms2-2 \
    libopenjp2-7 \
    libtiff6 \
    libwebp7 \
    libharfbuzz0b \
    libfribidi0 \
    libxcb1 \
    ffmpeg \
    imagemagick \
    fonts-liberation \
    fonts-noto-mono \
    fonts-dejavu-core \
    fontconfig

# Install Playwright browser binaries required by tiktok-uploader.
RUN --mount=type=cache,target=/ms-playwright \
    /app/.venv/bin/playwright install --with-deps chromium

# Install project-provided fonts in standard locations and expose predictable paths
COPY ./src/resources/fonts/* /usr/share/fonts/truetype/custom/

RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml && \
    sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read,write" pattern="@*"/g' /etc/ImageMagick-6/policy.xml && \
    echo '<policy domain="resource" name="memory" value="256MiB"/>' >> /etc/ImageMagick-6/policy.xml && \
    echo '<policy domain="resource" name="disk" value="1GiB"/>' >> /etc/ImageMagick-6/policy.xml && \
    find /usr/share/fonts -type f \( -name "*.ttf" -o -name "*.otf" \) -exec chmod 644 {} + && \
    ln -sf /usr/share/fonts/truetype/custom/droidsans.ttf /usr/share/fonts/droidsans.ttf && \
    ln -sf /usr/share/fonts/truetype/custom/webdings.ttf /usr/share/fonts/webdings.ttf && \
    ln -sf /usr/share/fonts/truetype/custom/monocraft.otf /usr/share/fonts/monocraft.otf && \
    fc-cache -f -v && \
    dpkg-reconfigure -f noninteractive fontconfig && \
    echo "Available fonts (filtered):" && \
    fc-list | grep -i "droid\|monocraft\|webdings" || echo "Warning: Some fonts not found"

# Create non-root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g "${GID}" app && \
    useradd --create-home --no-log-init -u "${UID}" -g "${GID}" app && \
    mkdir -p /app/run && \
    chown app:app /app/run /ms-playwright

# Copy application files
COPY ./src /app/src
COPY ./src/resources /app/resources
COPY pyproject.toml /app/pyproject.toml
COPY Makefile /app/Makefile
COPY --chmod=755 docker-entrypoint.sh /app/docker-entrypoint.sh

ENV PYTHONPATH=/app
USER app

ENTRYPOINT ["/app/docker-entrypoint.sh"]
