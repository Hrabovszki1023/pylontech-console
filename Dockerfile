FROM python:3.13-slim

ARG PYLONTECH_BUILD_VERSION=""
ARG PYLONTECH_BUILD_REVISION=development

ENV PYLONTECH_BUILD_VERSION=${PYLONTECH_BUILD_VERSION}
ENV PYLONTECH_BUILD_REVISION=${PYLONTECH_BUILD_REVISION}

WORKDIR /app

COPY . .
RUN python -m pip install --no-cache-dir .

RUN groupadd --system pylontech \
    && useradd --system --gid pylontech --home-dir /app pylontech

USER pylontech

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os, urllib.request; port = os.environ.get('PYLONTECH_HTTP_PORT', '8000'); urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=3).read()"

CMD ["python", "-m", "pylontech_console.main"]
