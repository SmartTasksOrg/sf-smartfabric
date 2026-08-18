# SmartFabric node — containerized IFP node service.
# Builds the published package and runs `smartfabric serve`.
FROM python:3.11-slim

WORKDIR /app
# install from source in the image (copy the package tree)
COPY . /app
RUN pip install --no-cache-dir .

# node listens on 8770 by default
EXPOSE 8770
ENV SMARTFABRIC_HOST=0.0.0.0 SMARTFABRIC_PORT=8770

# healthcheck hits GET /health
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8770/health',timeout=2).status==200 else 1)"

CMD ["sh", "-c", "smartfabric serve --host ${SMARTFABRIC_HOST} --port ${SMARTFABRIC_PORT}"]
