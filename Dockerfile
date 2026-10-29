FROM python:3.12-slim AS runtime-base

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    APP_PORT=8080 \
    DATA_FILE=/data/invoices.json

COPY app.py ./
RUN mkdir -p /data

FROM runtime-base AS test
COPY tests ./tests
RUN python -m unittest discover -s tests -v

FROM runtime-base AS production
ARG APP_VERSION=v1
ENV APP_VERSION=${APP_VERSION}
LABEL org.opencontainers.image.title="Invoice System" \
      org.opencontainers.image.version="${APP_VERSION}"

EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=6 \
  CMD python -c "from urllib.request import urlopen; urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["python", "app.py"]
