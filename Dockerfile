FROM python:3.15-slim

WORKDIR /app
COPY mcp_bridge.py /app/mcp_bridge.py

RUN useradd --system --no-create-home mcpuser
USER mcpuser

ENV PYTHONUNBUFFERED=1
ENV DATAX_BASE_URL="https://datax-es.duckdns.org"

ENTRYPOINT ["python3", "/app/mcp_bridge.py"]
