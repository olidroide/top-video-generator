FROM python:3.11.3-slim-buster
LABEL maintainer="top-video-generator@olidroide.es"

ENV PIP_DEFAULT_TIMEOUT=100 \
    # Allow statements and log messages to immediately appear
    PYTHONUNBUFFERED=1 \
    # disable a pip version check to reduce run-time & log-spam
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # cache is useless in docker image, so disable to reduce image size
    PIP_NO_CACHE_DIR=1 \
    OAUTHLIB_INSECURE_TRANSPORT=1



COPY ./requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt


COPY ./src/resources/fonts/* /usr/local/share/fonts/
COPY ./src/resources/fonts/* /usr/share/fonts/

# Fix Debian Buster sources for archive
RUN sed -i 's|http://deb.debian.org/debian|http://archive.debian.org/debian|g' /etc/apt/sources.list && \
    sed -i 's|http://security.debian.org/debian-security|http://archive.debian.org/debian-security|g' /etc/apt/sources.list && \
    apt-get -o Acquire::Check-Valid-Until=false update && \
    apt-get -y upgrade && \
    apt-get install -y ffmpeg imagemagick fonts-liberation fonts-droid-fallback fonts-noto-mono fontconfig && \
    apt-get -y clean && rm -rf /var/lib/apt/lists/*

RUN sed -i 's/none/read,write/g' /etc/ImageMagick-6/policy.xml
RUN dpkg-reconfigure fontconfig-config
RUN fc-cache -f && rm -rf /var/cache/*

RUN fc-cache -f -v

# USER
ARG UID=1000
ARG GID=1000

RUN groupadd -g "${GID}" app \
  && useradd --create-home --no-log-init -u "${UID}" -g "${GID}" app


WORKDIR /app
COPY ./src /app/src
COPY ./src/resources /app/resources
COPY ./src/web /app/web
COPY pyproject.toml /app
COPY Makefile /app
COPY docker-entrypoint.sh /app/docker-entrypoint.sh
ENV PYTHONPATH /app
USER app

#EXPOSE 8080
ENTRYPOINT ["/app/docker-entrypoint.sh"]

