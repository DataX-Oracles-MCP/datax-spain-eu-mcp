#!/usr/bin/env python3
"""
mcp_bridge.py (v1.0) - Zero-dependency MCP JSON-RPC 2.0 (stdio) bridge for DataX Truth Engine.
- Translates Claude/Cursor/Smithery/Glama stdio MCP calls to the DataX HTTPS REST API.
- Auto-rotates change_token in memory across consecutive paid calls.
Dependencies: Python 3.9+ standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

DEFAULT_BASE_URL = os.environ.get("DATAX_BASE_URL", "https://datax-es.duckdns.org").rstrip("/")
PAID_TOOLS = {"search_tenders", "find_distressed_auctions", "find_funded_companies", "check_company_risk", "get_tender_detail"}
TOOLS: list[dict[str, Any]] = [
    {"name": "get_pricing", "description": "Get USDC & MiCA EURC pricing (0.10/0.30/0.50), contracts, and treasuries.", "inputSchema": {"type": "object", "properties": {}}},
    {"name": "get_catalog", "description": "Get live Spain+EU dataset freshness (data_version) and section counts.", "inputSchema": {"type": "object", "properties": {}}},
    {
        "name": "search_tenders",
        "description": "Tier 1 Radar (0.10 USDC/EURC): Search BOE, BORME, BDNS, PLACSP, TED, CNMV, EU FSF & Laws. Returns encrypted item_ref (dx_...).",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}, "seccion": {"type": "string"}, "notice_type": {"type": "string"}, "date_from": {"type": "string"}, "date_to": {"type": "string"}, "limit": {"type": "integer"}}},
    },
    {
        "name": "find_distressed_auctions",
        "description": "Tier 1 Real-Estate Arbitrage (0.10 USDC/EURC): Rank Spain auctions by debt-to-value discount (ltv_pct) and concursal status.",
        "inputSchema": {"type": "object", "properties": {"ambito": {"type": "string"}, "min_value_eur": {"type": "number"}, "max_ltv_pct": {"type": "number"}, "concursal_only": {"type": "boolean"}, "limit": {"type": "integer"}}},
    },
    {
        "name": "find_funded_companies",
        "description": "Tier 1 B2B Cash-Flow Radar (0.10 USDC/EURC): Companies receiving BDNS grants, public awards, or capital raises.",
        "inputSchema": {"type": "object", "properties": {"event_type": {"type": "string"}, "min_importe_eur": {"type": "number"}, "ambito": {"type": "string"}, "query": {"type": "string"}, "limit": {"type": "integer"}}},
    },
    {
        "name": "check_company_risk",
        "description": "Tier 1.5 KYB (0.30 USDC/EURC): Screen corporate CIF or company_name across BORME insolvencies, EU FSF sanctions, CNMV & awards.",
        "inputSchema": {"type": "object", "properties": {"cif": {"type": "string"}, "company_name": {"type": "string"}}},
    },
    {
        "name": "get_tender_detail",
        "description": "Tier 2 Unlock (0.50 USDC/EURC): Unlock full verbatim record, CIF/razon social, Ref Catastral & official URLs from item_ref.",
        "inputSchema": {"type": "object", "properties": {"item_ref": {"type": "string"}}, "required": ["item_ref"]},
    },
]


class DataXBridge:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str = "") -> None:
        if not base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("DATAX_BASE_URL must use https:// (or loopback http:// for local dev)")
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()

    def _http_json(self, method: str, path: str, body: dict[str, Any] | None = None, token: str = "") -> tuple[int, dict[str, Any]]:
        hdrs = {"Accept": "application/json", "User-Agent": "DataX-MCP-Bridge/1.0"}
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            hdrs["Content-Type"] = "application/json"
        if token:
            hdrs["X-Payment-Proof"] = token
        req = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=hdrs, method=method)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as he:
            raw = he.read().decode("utf-8", errors="replace")
            try:
                return he.code, json.loads(raw)
            except ValueError:
                return he.code, {"error": raw}
        except (OSError, ValueError) as exc:
            # Timeout/DNS/TLS: token is kept; server replays the cached result for the same token+params.
            return 599, {"error": "network_error", "detail": str(exc), "hint": "Retry the exact same call; the server replays it without charging twice."}

    def call_tool(self, name: str, args: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        if name == "get_pricing":
            code, obj = self._http_json("GET", "/.well-known/ai-crawl-pricing.json")
            return obj, code >= 400
        if name == "get_catalog":
            code, obj = self._http_json("GET", "/agent-catalog.json")
            return obj, code >= 400
        if name in PAID_TOOLS:
            code, obj = self._http_json("POST", "/api/v1/execute/boe-spain", {"operation": name, "params": args}, token=self.token)
            if code == 200 and obj.get("change_token"):
                self.token = str(obj["change_token"])
            elif code == 200:
                self.token = ""  # balance fully spent; next paid call must 402 instead of replaying a spent token
            if code == 402:
                obj["hint"] = f"Set DATAX_TOKEN after redeeming USDC/EURC via {self.base_url}/api/v1/challenge & /api/v1/issue-token"
            return obj, code >= 400
        return {"error": f"Unknown tool: {name}"}, True

    def handle_rpc(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if req_id is None:  # notifications never get a response
            return None
        if method == "initialize":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"protocolVersion": params.get("protocolVersion", "2024-11-05"), "capabilities": {"tools": {}}, "serverInfo": {"name": "datax-spain-eu-oracle", "version": "2.2.0"}}}
        if method == "ping":
            return {"jsonrpc": "2.0", "id": req_id, "result": {}}
        if method == "tools/list":
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}}
        if method == "tools/call":
            res, is_err = self.call_tool(str(params.get("name", "")), dict(params.get("arguments") or {}))
            return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False)}], "isError": is_err}}
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def run_self_check() -> None:
    import http.server
    import threading

    class _Mock(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a: Any) -> None:
            pass

        def _send(self, status: int, body: dict[str, Any]) -> None:
            raw = json.dumps(body).encode()
            self.send_response(status); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)

        def do_GET(self) -> None:
            self._send(200, {"accepted_assets": ["USDC", "EURC"]})

        def do_POST(self) -> None:
            tok = self.headers.get("X-Payment-Proof", "")
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if tok == "tok_1m":
                self._send(200, {"status": "executed", "change_token": "tok_900k", "result": {"matches": [{"t": "subvención €"}]}})
            elif tok == "tok_900k":
                self._send(200, {"status": "executed", "result": {"matches": []}})  # exact spend, no change
            else:
                self._send(402, {"error": "payment_required"})

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    call = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "search_tenders", "arguments": {"query": "solar"}}}
    try:
        br = DataXBridge(f"http://127.0.0.1:{srv.server_address[1]}", token="tok_1m")
        assert br.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]["serverInfo"]["name"] == "datax-spain-eu-oracle"
        assert len(br.handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]) == 7
        assert br.handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        c1 = br.handle_rpc({**call, "id": 3})
        assert not c1["result"]["isError"] and br.token == "tok_900k"
        assert json.dumps(c1).isascii()  # stdout line stays ASCII-safe on Windows cp1252 pipes
        c2 = br.handle_rpc({**call, "id": 4})
        assert not c2["result"]["isError"] and br.token == ""
        c402 = br.handle_rpc({**call, "id": 5})
        assert c402["result"]["isError"] is True and "DATAX_TOKEN" in c402["result"]["content"][0]["text"]
        br.token = "tok_keep"
        port = srv.server_address[1]
    finally:
        srv.shutdown(); srv.server_close()
    br.base_url = f"http://127.0.0.1:{port}"  # server now down -> network error path
    cnet = br.handle_rpc({**call, "id": 6})
    assert cnet["result"]["isError"] is True and "network_error" in cnet["result"]["content"][0]["text"] and br.token == "tok_keep"
    print("  [MCP Bridge v1.0] OK: JSON-RPC 2.0 stdio, 7 tools, change_token rotation, 402, network-error token retention verified.")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        run_self_check()
        return
    sys.stdin.reconfigure(encoding="utf-8")  # Windows pipes default to cp1252
    bridge = DataXBridge(DEFAULT_BASE_URL, os.environ.get("DATAX_TOKEN", ""))
    for line in sys.stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            resp = bridge.handle_rpc(json.loads(raw))
        except Exception as exc:
            resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        if resp is not None:
            sys.stdout.write(json.dumps(resp) + "\n")  # ensure_ascii=True: encoding-proof on any OS
            sys.stdout.flush()


if __name__ == "__main__":
    main()
