# Build stage for compiling Python packages
FROM python:3.12.8-slim-bookworm AS builder

ENV PIP_DEFAULT_TIMEOUT=100 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies for compiling Python packages
RUN apt-get update && \
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
        libtiff5-dev \
        tk-dev \
        tcl-dev \
        libwebp-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        libxcb1-dev \
        pkg-config \
        && rm -rf /var/lib/apt/lists/*

# Create virtual environment and install packages
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt

# Runtime stage - minimal final image
FROM python:3.12.8-slim-bookworm
LABEL MAINTAINER="top-video-generator@olidroide.es"

ENV PYTHONUNBUFFERED=1 \
    OAUTHLIB_INSECURE_TRANSPORT=1 \
    PATH="/opt/venv/bin:$PATH"

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Install only runtime dependencies (no build tools)
RUN apt-get update && \
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
        fonts-droid-fallback \
        fonts-noto-mono \
        fonts-dejavu-core \
        fontconfig \
        && apt-get clean \
        && rm -rf /var/lib/apt/lists/* \
        && rm -rf /var/cache/apt/*

COPY ./src/resources/fonts/* /usr/local/share/fonts/
COPY ./src/resources/fonts/* /usr/share/fonts/

RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml && \
    fc-cache -fv && \
    dpkg-reconfigure -f noninteractive fontconfig && \
    rm -rf /var/cache/*

# Create non-root user
ARG UID=1000
ARG GID=1000
RUN groupadd -g "${GID}" app && \
    useradd --create-home --no-log-init -u "${UID}" -g "${GID}" app

WORKDIR /app

# Copy application files
COPY ./src /app/src
COPY ./src/resources /app/resources  
COPY ./src/web /app/web
COPY pyproject.toml /app
COPY Makefile /app
COPY docker-entrypoint.sh /app/docker-entrypoint.sh

ENV PYTHONPATH=/app
USER app

ENTRYPOINT ["/app/docker-entrypoint.sh"]

