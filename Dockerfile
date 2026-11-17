FROM python:3.15-slim

WORKDIR /app
COPY mcp_bridge.py /app/mcp_bridge.py

RUN useradd --system --no-create-home mcpuser
USER mcpuser

LABEL io.modelcontextprotocol.server.name="io.github.DataX-Oracles-MCP/datax-spain-eu-mcp"
LABEL org.opencontainers.image.source="https://github.com/DataX-Oracles-MCP/datax-spain-eu-mcp"
LABEL org.opencontainers.image.description="Zero-dependency MCP bridge for Spain & EU official registries with USDC & MiCA EURC settlement."
LABEL org.opencontainers.image.licenses="MIT"

ENV PYTHONUNBUFFERED=1
ENV DATAX_BASE_URL="https://datax-es.duckdns.org"

ENTRYPOINT ["python3", "/app/mcp_bridge.py"]
