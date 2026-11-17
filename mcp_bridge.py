#!/usr/bin/env python3
"""
mcp_bridge.py (v1.1) - Zero-dependency MCP JSON-RPC 2.0 (stdio) bridge for DataX Spain + EU Truth Engine.
- Translates Claude/Cursor/Smithery/Glama stdio MCP calls to the DataX HTTPS REST API.
- Publishes MCP server instructions, tool annotations, input/output schemas, and rotates change_token in memory.
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
SERVER_INSTRUCTIONS = "DataX Spain & EU Official Registry MCP Server (datax-es.duckdns.org). 1) Call get_pricing and get_catalog for free to inspect accepted stablecoins (USDC, MiCA EURC), treasury addresses, prices ($0.10/$0.30/$0.50), and fresh section counts. 2) Set DATAX_TOKEN (issued via /api/v1/challenge and /api/v1/issue-token) to call search_tenders ($0.10), find_funded_companies ($0.10), find_distressed_auctions ($0.10), or check_company_risk ($0.30); each match returns an opaque item_ref ('dx_...'). 3) Pass any item_ref to get_tender_detail ($0.50) to unlock full verbatim text, corporate IDs, and official URLs. Unspent change_token balance rotates automatically in memory across consecutive calls."
TOOLS: list[dict[str, Any]] = [
    {
        "name": "get_pricing",
        "title": "Get Payment Pricing & Treasuries",
        "description": "Retrieve supported blockchains (Base, Polygon, Solana), accepted stablecoins (USDC and MiCA EURC), treasury recipient addresses, token contracts, and per-call USD/EUR prices ($0.10 search/screening, $0.30 corporate risk check, $0.50 full record unlock) for datax-es.duckdns.org. Free read-only call requiring no DATAX_TOKEN. Call this before minting payment tokens via /api/v1/challenge or calling paid tools.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "service": {
                    "type": "string"
                },
                "service_domain": {
                    "type": "string"
                },
                "feed_id": {
                    "type": "string"
                },
                "currency": {
                    "type": "string"
                },
                "accepted_assets": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    }
                },
                "base_price": {
                    "type": "string"
                },
                "kyb_price": {
                    "type": "string"
                },
                "detail_price": {
                    "type": "string"
                },
                "supported_networks": {
                    "type": "object"
                },
                "recipients": {
                    "type": "object"
                },
                "operations": {
                    "type": "object"
                }
            }
        }
    },
    {
        "name": "get_catalog",
        "title": "Get Live Dataset Catalog & Freshness",
        "description": "Retrieve live dataset freshness (data_version), total indexed records, earliest and latest publication dates (YYYYMMDD), and exact record counts grouped by registry section and notice type on datax-es.duckdns.org. Free read-only call requiring no DATAX_TOKEN. Call this to verify available sections and date coverage before querying with search_tenders or find_funded_companies.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "total_returned": {
                    "type": "integer"
                },
                "datasets": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "doc_id": {
                                "type": "string"
                            },
                            "data_version": {
                                "type": "string"
                            },
                            "total_records": {
                                "type": "integer"
                            },
                            "earliest_fecha_pub": {
                                "type": "string"
                            },
                            "latest_fecha_pub": {
                                "type": "string"
                            },
                            "counts_by_seccion": {
                                "type": "object"
                            },
                            "counts_by_notice_type": {
                                "type": "object"
                            }
                        }
                    }
                }
            }
        }
    },
    {
        "name": "search_tenders",
        "title": "Search Official Registry & Tender Records",
        "description": "Run full-text and structured searches across indexed Spain and EU official registries (BOE, BORME, BDNS, PLACSP, Catastro Auctions, CNMV, EU TED, SEDIA, EU FSF, and Consolidated Laws). Costs $0.10 USDC or EURC per call using DATAX_TOKEN (returns HTTP 402 payment instructions if unset or depleted; auto-rotates change_token in memory). Returns masked previews and opaque item_ref handles ('dx_...'); pass an item_ref to get_tender_detail ($0.50) to unlock full verbatim text, corporate IDs, and official URLs. Use find_funded_companies when filtering by EUR amounts/liquidity events, find_distressed_auctions for real-estate discounts, or check_company_risk to screen a specific company.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Full-text search keywords matched across notice titles, subjects, authorities, and body text (e.g. 'cloud infrastructure'). Optional when filtering by seccion, notice_type, or dates."
                },
                "seccion": {
                    "type": "string",
                    "enum": [
                        "ALL",
                        "1",
                        "2B",
                        "3",
                        "4",
                        "5A",
                        "5B",
                        "5C",
                        "BA",
                        "BB",
                        "SA",
                        "SC",
                        "PC",
                        "PA",
                        "EU",
                        "TE",
                        "LC",
                        "SF",
                        "MV"
                    ],
                    "default": "ALL",
                    "description": "Registry section filter: 'ALL' (default), 'PA' (contract awards), 'PC' (open tenders), 'BA'/'BB' (commercial registry), 'SA'/'SC' (grants), 'LC' (legislation), 'MV' (financial regulator), 'TE' (EU TED), 'EU' (EU SEDIA), 'SF' (EU sanctions), or BOE codes '1','2B','3','4','5A','5B','5C'."
                },
                "notice_type": {
                    "type": "string",
                    "enum": [
                        "ALL",
                        "LICITACION",
                        "FORMALIZACION",
                        "MODIFICACION",
                        "OPOSICION",
                        "SUBASTA",
                        "SUBVENCION",
                        "CONCESION",
                        "SANCION",
                        "ENERGIA_EXPROPIACION",
                        "NORMATIVA",
                        "CONSTITUCION",
                        "CONCURSO_DISOLUCION",
                        "MERCANTIL",
                        "ANUNCIO"
                    ],
                    "default": "ALL",
                    "description": "Notice classification filter: 'ALL' (default), 'LICITACION', 'FORMALIZACION', 'MODIFICACION', 'OPOSICION', 'SUBASTA', 'SUBVENCION', 'CONCESION', 'SANCION', 'ENERGIA_EXPROPIACION', 'NORMATIVA', 'CONSTITUCION', 'CONCURSO_DISOLUCION', 'MERCANTIL', or 'ANUNCIO'."
                },
                "date_from": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "Inclusive lower publication date bound in YYYYMMDD format (e.g. '20261110')."
                },
                "date_to": {
                    "type": "string",
                    "pattern": "^\\d{8}$",
                    "description": "Inclusive upper publication date bound in YYYYMMDD format (e.g. '20261117')."
                },
                "match_mode": {
                    "type": "string",
                    "enum": [
                        "AND",
                        "OR"
                    ],
                    "default": "AND",
                    "description": "Boolean operator for multi-word queries: 'AND' requires all words (default), 'OR' matches any word."
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "default": 10,
                    "description": "Maximum number of matching records to return (1 to 25, default 10)."
                }
            }
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "change_token": {
                    "type": "string"
                },
                "change_micros": {
                    "type": "integer"
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string"
                        },
                        "data_version": {
                            "type": "string"
                        },
                        "total_returned": {
                            "type": "integer"
                        },
                        "matches": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_ref": {
                                        "type": "string",
                                        "description": "Opaque encrypted record reference ('dx_...') for get_tender_detail."
                                    },
                                    "fecha_pub": {
                                        "type": "string",
                                        "description": "Publication date in YYYYMMDD format."
                                    },
                                    "seccion": {
                                        "type": "string",
                                        "description": "Registry section code."
                                    },
                                    "notice_type": {
                                        "type": "string",
                                        "description": "Notice classification."
                                    },
                                    "ambito": {
                                        "type": "string",
                                        "description": "Geographic jurisdiction or region."
                                    },
                                    "importe_texto": {
                                        "type": "string",
                                        "description": "Formatted amount string when available."
                                    },
                                    "preview": {
                                        "type": "string",
                                        "description": "Redacted summary preview without PII or entity identifiers."
                                    },
                                    "detail_locked": {
                                        "type": "boolean",
                                        "description": "Always true until unlocked with get_tender_detail."
                                    },
                                    "unlock_price_micros": {
                                        "type": "integer",
                                        "description": "Unlock price in USD/EUR micros (500000 = 0.50)."
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    {
        "name": "find_distressed_auctions",
        "title": "Find Discounted Real-Estate Auctions",
        "description": "Screen official Spanish judicial and notarial real-estate auctions enriched with Catastro valuation data, ranked ascending by debt-to-value ratio (ltv_pct) and equity margin. Costs $0.10 USDC or EURC per call via DATAX_TOKEN (returns HTTP 402 if unset). Returns masked auction previews and opaque item_ref handles ('dx_...') unlockable via get_tender_detail ($0.50). Use this specifically to discover discounted Spanish property auctions; use search_tenders for non-auction records.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "ambito": {
                    "type": "string",
                    "description": "Case-insensitive province or region substring filter (e.g. 'Madrid' or 'Valencia'). Leave empty to search all regions."
                },
                "min_value_eur": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0,
                    "description": "Minimum official appraisal or auction value in EUR (>= 0, default 0)."
                },
                "max_ltv_pct": {
                    "type": "number",
                    "minimum": 1,
                    "maximum": 1000,
                    "default": 100,
                    "description": "Maximum claimed debt as a percentage of appraisal value (1 to 1000, default 100). Lower percentages indicate deeper discounts."
                },
                "concursal_only": {
                    "type": "boolean",
                    "default": False,
                    "description": "When true, restrict results to bankruptcy/insolvency court auctions (SUB-JC-*)."
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "default": 10,
                    "description": "Maximum number of ranked auctions to return (1 to 25, default 10)."
                }
            }
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "change_token": {
                    "type": "string"
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string"
                        },
                        "data_version": {
                            "type": "string"
                        },
                        "total_returned": {
                            "type": "integer"
                        },
                        "matches": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_ref": {
                                        "type": "string",
                                        "description": "Opaque encrypted record reference ('dx_...') for get_tender_detail."
                                    },
                                    "fecha_pub": {
                                        "type": "string",
                                        "description": "Publication date in YYYYMMDD format."
                                    },
                                    "seccion": {
                                        "type": "string",
                                        "description": "Registry section code."
                                    },
                                    "notice_type": {
                                        "type": "string",
                                        "description": "Notice classification."
                                    },
                                    "ambito": {
                                        "type": "string",
                                        "description": "Geographic jurisdiction or region."
                                    },
                                    "importe_texto": {
                                        "type": "string",
                                        "description": "Formatted amount string when available."
                                    },
                                    "preview": {
                                        "type": "string",
                                        "description": "Redacted summary preview without PII or entity identifiers."
                                    },
                                    "detail_locked": {
                                        "type": "boolean",
                                        "description": "Always true until unlocked with get_tender_detail."
                                    },
                                    "unlock_price_micros": {
                                        "type": "integer",
                                        "description": "Unlock price in USD/EUR micros (500000 = 0.50)."
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    {
        "name": "find_funded_companies",
        "title": "Screen Companies Receiving Grants, Awards, or Capital",
        "description": "Identify companies in Spain receiving newly awarded government grants, public procurement contracts, or share-capital raises above an EUR threshold. Costs $0.10 USDC or EURC per call via DATAX_TOKEN (returns HTTP 402 if unset). Returns masked previews with EUR amounts and opaque item_ref handles ('dx_...') to unlock beneficiary identities via get_tender_detail ($0.50). Prefer this over search_tenders when filtering by EUR liquidity thresholds or event_type; use check_company_risk to vet a known company.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "event_type": {
                    "type": "string",
                    "enum": [
                        "ALL",
                        "SUBVENCION_SC",
                        "ADJUDICACION",
                        "CONSTITUCION_CAPITAL"
                    ],
                    "default": "ALL",
                    "description": "Liquidity event category: 'ALL' (default), 'SUBVENCION_SC' (corporate grants), 'ADJUDICACION' (public contract awards), or 'CONSTITUCION_CAPITAL' (incorporations and capital increases)."
                },
                "min_importe_eur": {
                    "type": "number",
                    "minimum": 0,
                    "default": 0,
                    "description": "Minimum grant, contract award, or capital amount in EUR (>= 0, default 0)."
                },
                "ambito": {
                    "type": "string",
                    "description": "Case-insensitive region, city, or department substring filter (e.g. 'Madrid or Cataluña'). Optional."
                },
                "query": {
                    "type": "string",
                    "description": "Optional full-text keywords to filter funded leads by sector, CPV, or activity."
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 25,
                    "default": 10,
                    "description": "Maximum number of funded company leads to return (1 to 25, default 10)."
                }
            }
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "change_token": {
                    "type": "string"
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string"
                        },
                        "event_type": {
                            "type": "string"
                        },
                        "data_version": {
                            "type": "string"
                        },
                        "total_returned": {
                            "type": "integer"
                        },
                        "matches": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_ref": {
                                        "type": "string",
                                        "description": "Opaque encrypted record reference ('dx_...') for get_tender_detail."
                                    },
                                    "fecha_pub": {
                                        "type": "string",
                                        "description": "Publication date in YYYYMMDD format."
                                    },
                                    "seccion": {
                                        "type": "string",
                                        "description": "Registry section code."
                                    },
                                    "notice_type": {
                                        "type": "string",
                                        "description": "Notice classification."
                                    },
                                    "ambito": {
                                        "type": "string",
                                        "description": "Geographic jurisdiction or region."
                                    },
                                    "importe_texto": {
                                        "type": "string",
                                        "description": "Formatted amount string when available."
                                    },
                                    "preview": {
                                        "type": "string",
                                        "description": "Redacted summary preview without PII or entity identifiers."
                                    },
                                    "detail_locked": {
                                        "type": "boolean",
                                        "description": "Always true until unlocked with get_tender_detail."
                                    },
                                    "unlock_price_micros": {
                                        "type": "integer",
                                        "description": "Unlock price in USD/EUR micros (500000 = 0.50)."
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    {
        "name": "check_company_risk",
        "title": "Corporate KYB & Compliance Risk Check",
        "description": "Perform corporate KYB compliance screening across BORME insolvencies, CNMV warnings, EU FSF sanctions, BDNS grants, and public contract awards. Costs $0.30 USDC or EURC per call via DATAX_TOKEN (returns HTTP 402 if unset). Requires cif and/or company_name (corporate tax/VAT IDs only; personal national IDs are blocked for GDPR). Returns risk_alert boolean, risk_level ('HIGH', 'LOW', or 'UNKNOWN'), hit counts by category, and item_ref handles ('dx_...') unlockable via get_tender_detail ($0.50).",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "cif": {
                    "type": "string",
                    "description": "Corporate tax, VAT, or commercial registry identifier without spaces (e.g. 'B86900001'). Natural-person IDs are rejected per GDPR. Required if company_name is omitted."
                },
                "company_name": {
                    "type": "string",
                    "description": "Registered corporate legal name (e.g. 'Indra Sistemas SA'). Required if cif is omitted; supply both for broader matching."
                }
            }
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "change_token": {
                    "type": "string"
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string"
                        },
                        "data_version": {
                            "type": "string"
                        },
                        "risk_alert": {
                            "type": "boolean"
                        },
                        "risk_level": {
                            "type": "string"
                        },
                        "summary": {
                            "type": "object"
                        },
                        "signals": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "item_ref": {
                                        "type": "string",
                                        "description": "Opaque encrypted record reference ('dx_...') for get_tender_detail."
                                    },
                                    "fecha_pub": {
                                        "type": "string",
                                        "description": "Publication date in YYYYMMDD format."
                                    },
                                    "seccion": {
                                        "type": "string",
                                        "description": "Registry section code."
                                    },
                                    "notice_type": {
                                        "type": "string",
                                        "description": "Notice classification."
                                    },
                                    "ambito": {
                                        "type": "string",
                                        "description": "Geographic jurisdiction or region."
                                    },
                                    "importe_texto": {
                                        "type": "string",
                                        "description": "Formatted amount string when available."
                                    },
                                    "preview": {
                                        "type": "string",
                                        "description": "Redacted summary preview without PII or entity identifiers."
                                    },
                                    "detail_locked": {
                                        "type": "boolean",
                                        "description": "Always true until unlocked with get_tender_detail."
                                    },
                                    "unlock_price_micros": {
                                        "type": "integer",
                                        "description": "Unlock price in USD/EUR micros (500000 = 0.50)."
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    {
        "name": "get_tender_detail",
        "title": "Unlock Full Official Record by Reference",
        "description": "Unlock the complete, unredacted official record—including full company and contracting authority names, corporate tax IDs, official document ID (boe_id), verbatim text, and official PDF/HTML/XML URLs—for $0.50 USDC or EURC per call via DATAX_TOKEN (returns HTTP 402 if unset). Requires an opaque item_ref ('dx_...') returned by search_tenders, find_funded_companies, find_distressed_auctions, or check_company_risk. Always run one of those screening tools first to obtain an item_ref.",
        "annotations": {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True
        },
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_ref": {
                    "type": "string",
                    "pattern": "^dx_[A-Za-z0-9_-]+$",
                    "description": "Required opaque encrypted record handle ('dx_...') obtained from search_tenders, find_funded_companies, find_distressed_auctions, or check_company_risk."
                }
            },
            "required": [
                "item_ref"
            ]
        },
        "outputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string"
                },
                "change_token": {
                    "type": "string"
                },
                "result": {
                    "type": "object",
                    "properties": {
                        "operation": {
                            "type": "string"
                        },
                        "found": {
                            "type": "boolean"
                        },
                        "item_ref": {
                            "type": "string"
                        },
                        "boe_id": {
                            "type": "string"
                        },
                        "tender": {
                            "type": "object"
                        }
                    }
                }
            }
        }
    }
]


class DataXBridge:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, token: str = "") -> None:
        if not base_url.startswith(("https://", "http://127.0.0.1", "http://localhost")):
            raise ValueError("DATAX_BASE_URL must use https:// (or loopback http:// for local dev)")
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()

    def _http_json(self, method: str, path: str, body: dict[str, Any] | None = None, token: str = "") -> tuple[int, dict[str, Any]]:
        hdrs = {"Accept": "application/json", "User-Agent": "DataX-MCP-Bridge/1.1"}
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
                self.token = ""
            if code == 402:
                obj["hint"] = f"Set DATAX_TOKEN after redeeming USDC/EURC via {self.base_url}/api/v1/challenge & /api/v1/issue-token"
            return obj, code >= 400
        return {"error": f"Unknown tool: {name}"}, True

    def handle_rpc(self, msg: dict[str, Any]) -> dict[str, Any] | None:
        req_id = msg.get("id")
        method = msg.get("method", "")
        params = msg.get("params") or {}
        if req_id is None:
            return None
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": params.get("protocolVersion", "2025-03-26"),
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "datax-spain-eu-oracle", "version": "2.2.0"},
                    "instructions": SERVER_INSTRUCTIONS,
                },
            }
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

    for tool in TOOLS:
        assert tool.get("annotations") and tool.get("outputSchema"), f"Missing annotations/outputSchema on {tool['name']}"
        props = (tool.get("inputSchema") or {}).get("properties") or {}
        assert all(p.get("description") for p in props.values()), f"Undocumented parameter on {tool['name']}"

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
                self._send(200, {"status": "executed", "result": {"matches": []}})
            else:
                self._send(402, {"error": "payment_required"})

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    call = {"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "search_tenders", "arguments": {"query": "solar"}}}
    try:
        br = DataXBridge(f"http://127.0.0.1:{srv.server_address[1]}", token="tok_1m")
        init_res = br.handle_rpc({"jsonrpc": "2.0", "id": 1, "method": "initialize"})["result"]
        assert init_res["serverInfo"]["name"] == "datax-spain-eu-oracle" and init_res["instructions"]
        assert len(br.handle_rpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})["result"]["tools"]) == 7
        assert br.handle_rpc({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
        c1 = br.handle_rpc({**call, "id": 3})
        assert not c1["result"]["isError"] and br.token == "tok_900k"
        assert json.dumps(c1).isascii()
        c2 = br.handle_rpc({**call, "id": 4})
        assert not c2["result"]["isError"] and br.token == ""
        c402 = br.handle_rpc({**call, "id": 5})
        assert c402["result"]["isError"] is True and "DATAX_TOKEN" in c402["result"]["content"][0]["text"]
        br.token = "tok_keep"
        port = srv.server_address[1]
    finally:
        srv.shutdown(); srv.server_close()
    br.base_url = f"http://127.0.0.1:{port}"
    cnet = br.handle_rpc({**call, "id": 6})
    assert cnet["result"]["isError"] is True and "network_error" in cnet["result"]["content"][0]["text"] and br.token == "tok_keep"
    print("  [MCP Bridge ES v1.1] OK: instructions, annotations, outputSchema, 100% inputSchema docs, 402 & rotation verified.")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        run_self_check()
        return
    sys.stdin.reconfigure(encoding="utf-8")
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
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
