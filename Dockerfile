FROM python:3.12-slim
WORKDIR /app
COPY mcp_bridge.py /app/mcp_bridge.py
ENV DATAX_BASE_URL="https://datax-es.duckdns.org" PYTHONUNBUFFERED="1"
ENTRYPOINT ["python3", "/app/mcp_bridge.py"]