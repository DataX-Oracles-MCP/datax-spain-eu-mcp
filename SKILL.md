---
name: datax-spain-eu-oracle
description: Query official Spain & EU registries (BOE, BORME, BDNS, PLACSP, TED, Catastro Auctions, CNMV, EU FSF & Consolidated Laws) via USDC UTXO micropayments.
---

# DataX Spain & EU Intelligence Oracle

Base URL: `https://datax-es.duckdns.org`
Discovery: `GET /llms.txt`, `GET /mcp.json`, `GET /.well-known/agent-card.json`, `GET /openapi.json`

## Pricing (USDC on Base, Polygon, or Solana)
- **$0.10 (`100,000` micros):** `search_tenders`, `find_distressed_auctions` (LTV/discount real-estate auctions), `find_funded_companies` (new grants, public contract wins, capital raises). Returns opaque `item_ref` (`dx_...`).
- **$0.30 (`300,000` micros):** `check_company_risk` (BORME insolvencies + EU FSF sanctions + CNMV warnings + BDNS/PLACSP).
- **$0.50 (`500,000` micros):** `get_tender_detail` (unlocks `boe_id`, CIF, Ref Catastral, verbatim text & official URLs from any `item_ref`).

## Minimal Flow
1. `POST /api/v1/challenge` -> sign EIP-712 (EVM) or Ed25519 (Solana) -> `POST /api/v1/issue-token` with `scope_id = "ffffffffffffffff"`.
2. Call `POST /api/v1/execute/boe-spain` with `X-Payment-Proof: <token>` and use returned `change_token` for subsequent calls.
> **Session Persistence Note:** `mcp_bridge.py` rotates `change_token` in memory during the active `stdio` session only. Every paid result includes its `idempotency_key`. If the process dies with balance left, recover the last `change_token` via `GET /api/v1/execute/reconcile?idempotency_key=<key>` with `X-Payer-Auth` (wallet-signed, valid 300 s, from `/api/v1/challenge` + `/api/v1/issue-token` with `scope_id = "eeeeeeeeeeeeeeee"`). For multi-process agents, pre-split via `POST /api/v1/split-token`. All tokens, including change tokens, expire 24 h after the **original** `issue-token`.
