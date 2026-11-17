# DataX Spain & EU Truth Engine — MCP Server (`stdio`)

Zero-dependency **Model Context Protocol (MCP)** `stdio` bridge (`Python 3.9+` standard library only — no `pip install` required) connecting AI agents (Claude Desktop, Cursor, OpenClaw, custom MCP clients) to live official **Spain & EU** registries with non-custodial pay-per-call settlement in **USDC** (Base, Polygon, Solana) and **MiCA EURC** (Base, Solana).

- **Live Endpoint:** `https://datax-es.duckdns.org`
- **Machine Discovery:** [`/llms.txt`](https://datax-es.duckdns.org/llms.txt) · [`/mcp.json`](https://datax-es.duckdns.org/mcp.json) · [`/.well-known/agent-card.json`](https://datax-es.duckdns.org/.well-known/agent-card.json) · [`/openapi.json`](https://datax-es.duckdns.org/openapi.json) · [`/.well-known/ai-crawl-pricing.json`](https://datax-es.duckdns.org/.well-known/ai-crawl-pricing.json)
- **Agent Payment Protocol & Wallet Guide:** See [`SKILL.md`](./SKILL.md)

---

## Official Data Sources Indexed

- **Spain Official Gazette (`BOE`):** Laws, public employment (`2B`), energy/expropriations, sanctions, and public procurement (`5A`, `5B`, `5C`).
- **Spain Commercial Registry (`BORME`):** Daily incorporations, capital increases, appointments, M&A mergers, and insolvencies across all 50 provinces + Ceuta & Melilla.
- **Spain National Grants (`BDNS / SNPSAP`):** Open subsidy calls (`SA`) and corporate grant awards (`SC` with corporate CIF).
- **Spain & Regional Public Procurement (`PLACSP`):** National, municipal, and regional tenders/awards (`PC`, `PA`, including offer counts).
- **Real-Estate Judicial/Notarial Auctions (`subastas.boe.es` + `Catastro`):** Enriched with appraisal/auction value, claimed debt, surface (`m²`), usage, and build year.
- **Consolidated Spanish Core Laws (`Sec LC`):** Article-by-article latest active text of 12 foundational codes (Constitution, LPACAP 39/2015, LRJSP 40/2015, LCSP 9/2017, Civil/Penal/LEC, LSC, LGT, Labor, LOPDGDD).
- **Financial Markets & Sanctions:** Spain **CNMV** official RSS (`Sec MV`), **EU TED v3** procurement (`Sec TE`), **EU SEDIA** grants (`Sec EU`), and **EU Consolidated Financial Sanctions List (`FSF`, `Sec SF`)**.

---

## MCP Tools Exposed (7 Tools)

| Tool | Price (`USDC` / `EURC`) | Purpose |
| :--- | :---: | :--- |
| `get_pricing` | **Free** | Fetch supported networks, contracts, treasuries, and tier prices. |
| `get_catalog` | **Free** | Check live freshness (`data_version`) and record counts by section. |
| `search_tenders` | **`0.10`** | FTS5 BM25 + BI filter search across all Spain & EU registries; returns opaque `item_ref` (`dx_...`). |
| `find_distressed_auctions` | **`0.10`** | Ranks official real-estate auctions by debt-to-value (`ltv_pct`) and equity margin. |
| `find_funded_companies` | **`0.10`** | Screens companies with newly awarded grants, public contracts, or capital raises. |
| `check_company_risk` | **`0.30`** | Corporate KYB cross-check by `cif` / `company_name` across BORME insolvencies, EU FSF sanctions, CNMV & awards. |
| `get_tender_detail` | **`0.50`** | Unlocks full verbatim record, CIF/razón social, address, Cadastral Ref & official URLs from any `item_ref`. |

---

## Quick Setup (Claude Desktop / Cursor)

```json
{
  "mcpServers": {
    "datax-spain-eu": {
      "command": "python3",
      "args": ["/absolute/path/to/mcp_bridge.py"],
      "env": {
        "DATAX_BASE_URL": "https://datax-es.duckdns.org",
        "DATAX_TOKEN": "<unspent-utxo-token-from-issue-token>"
      }
    }
  }
}