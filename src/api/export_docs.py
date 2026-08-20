"""src/api/export_docs.py — OpenAPI and Postman Collection Exporter (Day 40).

Sprint 6, Day 40

Generates:
1. docs/openapi.json — standard OpenAPI 3.1.0 JSON schema.
2. docs/postman_collection.json — Postman Collection v2.1.0 JSON format for all endpoints.

Usage:
    python -m src.api.export_docs
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from src.api.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_DIR = PROJECT_ROOT / "docs"


def export_openapi_json(output_path: Path = DOCS_DIR / "openapi.json") -> Path:
    """Extract and export OpenAPI 3.1 schema to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)
    return output_path


def export_postman_collection(
    output_path: Path = DOCS_DIR / "postman_collection.json",
    base_url: str = "http://localhost:8000",
) -> Path:
    """Generate Postman v2.1.0 collection JSON from registered FastAPI routes."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = app.openapi()

    items: List[Dict[str, Any]] = []

    # Map paths to Postman items
    for path, methods in schema.get("paths", {}).items():
        for method, details in methods.items():
            if method.lower() not in ["get", "post", "put", "delete", "patch"]:
                continue

            summary = details.get("summary", f"{method.upper()} {path}")
            description = details.get("description", "")
            tags = details.get("tags", ["General"])

            # Query params
            query_params = []
            for p in details.get("parameters", []):
                if p.get("in") == "query":
                    query_params.append({
                        "key": p.get("name"),
                        "value": str(p.get("schema", {}).get("default", "")),
                        "description": p.get("description", ""),
                        "disabled": not p.get("required", False),
                    })

            # Format path for Postman URL
            clean_path = path.lstrip("/")
            path_segments = clean_path.split("/")

            postman_item = {
                "name": summary,
                "request": {
                    "method": method.upper(),
                    "header": [
                        {"key": "Accept", "value": "application/json", "type": "text"}
                    ],
                    "url": {
                        "raw": f"{{{{base_url}}}}/{clean_path}",
                        "host": ["{{base_url}}"],
                        "path": path_segments,
                        "query": query_params,
                    },
                    "description": description,
                },
                "response": [],
            }

            items.append({
                "tag": tags[0] if tags else "General",
                "item": postman_item,
            })

    # Group items by tag / folder
    folders_map: Dict[str, List[Dict[str, Any]]] = {}
    for entry in items:
        tag = entry["tag"]
        if tag not in folders_map:
            folders_map[tag] = []
        folders_map[tag].append(entry["item"])

    postman_folders = [
        {"name": tag, "item": folder_items}
        for tag, folder_items in folders_map.items()
    ]

    collection = {
        "info": {
            "_postman_id": "nifty100-financial-intelligence-api",
            "name": "Nifty 100 Financial Intelligence API",
            "description": "Comprehensive REST API for Nifty 100 fundamental research, valuation, and analytics.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "version": schema.get("info", {}).get("version", "1.0.0"),
        },
        "variable": [
            {
                "key": "base_url",
                "value": base_url,
                "type": "string",
            }
        ],
        "item": postman_folders,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(collection, f, indent=2)

    return output_path


def main():
    openapi_file = export_openapi_json()
    postman_file = export_postman_collection()
    print("=" * 65)
    print("Day 40 — Documentation & Postman Collection Exporter")
    print("=" * 65)
    print(f"  • OpenAPI Spec:     {openapi_file} ({openapi_file.stat().st_size} bytes)")
    print(f"  • Postman Collection: {postman_file} ({postman_file.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
