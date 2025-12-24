#!/usr/bin/env python3
"""
openapi_to_human.py

Convert an OpenAPI YAML/JSON spec into a clean, human-readable Markdown API reference.

MVP goals:
- Endpoint summary table
- Authentication section (bearer token if present)
- Per-endpoint: required headers, request body fields table (simple object schemas),
  response codes list, and JSON examples when available
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)


def load_spec(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Spec not found: {path}")

    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    lower = path.lower()
    if lower.endswith(".json"):
        return json.loads(raw)

    # YAML (default)
    if yaml is None:
        raise RuntimeError("PyYAML is not installed. Add PyYAML>=6.0 to requirements.txt")
    return yaml.safe_load(raw)


def first_server_url(spec: Dict[str, Any]) -> Optional[str]:
    servers = spec.get("servers") or []
    if servers and isinstance(servers, list) and isinstance(servers[0], dict):
        return servers[0].get("url")
    return None


def detect_bearer_auth(spec: Dict[str, Any]) -> bool:
    components = spec.get("components") or {}
    sec = (components.get("securitySchemes") or {}) if isinstance(components, dict) else {}
    if not isinstance(sec, dict):
        return False

    for _, scheme in sec.items():
        if not isinstance(scheme, dict):
            continue
        if scheme.get("type") == "http" and str(scheme.get("scheme", "")).lower() == "bearer":
            return True
    return False


def collect_operations(spec: Dict[str, Any]) -> List[Tuple[str, str, Dict[str, Any]]]:
    """
    Returns list of (method, path, operationObject)
    """
    paths = spec.get("paths") or {}
    if not isinstance(paths, dict):
        return []

    ops: List[Tuple[str, str, Dict[str, Any]]] = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method, op in path_item.items():
            m = str(method).lower()
            if m not in {"get", "post", "put", "patch", "delete", "head", "options"}:
                continue
            if isinstance(op, dict):
                ops.append((m.upper(), str(path), op))
    # stable sort: path then method
    return sorted(ops, key=lambda t: (t[1], t[0]))


def md_escape(text: str) -> str:
    return text.replace("\n", " ").strip()


def md_h1(title: str) -> str:
    return f"# {title}\n"


def md_h2(title: str) -> str:
    return f"\n## {title}\n"


def md_h3(title: str) -> str:
    return f"\n### {title}\n"


def render_endpoint_summary(ops: List[Tuple[str, str, Dict[str, Any]]]) -> str:
    out = []
    out.append(md_h2("Endpoint summary"))
    out.append("| Method | Path | Purpose |")
    out.append("|---:|---|---|")
    for method, path, op in ops:
        purpose = md_escape(str(op.get("summary") or op.get("description") or ""))
        out.append(f"| {method} | `{path}` | {purpose} |")
    out.append("")
    return "\n".join(out)


def render_auth_section(has_bearer: bool) -> str:
    out = []
    out.append(md_h2("Authentication"))
    if has_bearer:
        out.append("All requests require a bearer token:")
        out.append("")
        out.append("`Authorization: Bearer <token>`")
    else:
        out.append("Authentication is not defined in this sample OpenAPI spec.")
    out.append("")
    return "\n".join(out)


def extract_json_example(content_obj: Dict[str, Any]) -> Optional[Any]:
    """
    Attempts to find a JSON example:
    - content.application/json.example
    - content.application/json.examples.<name>.value
    """
    if not isinstance(content_obj, dict):
        return None

    app_json = content_obj.get("application/json")
    if not isinstance(app_json, dict):
        return None

    if "example" in app_json:
        return app_json.get("example")

    examples = app_json.get("examples")
    if isinstance(examples, dict) and examples:
        # take first
        first_key = next(iter(examples.keys()))
        ex = examples.get(first_key)
        if isinstance(ex, dict) and "value" in ex:
            return ex.get("value")

    return None


def extract_request_fields(op: Dict[str, Any]) -> Tuple[List[Dict[str, str]], bool]:
    """
    Returns (fields, has_json_body)
    fields: list of {name,type,required,notes}
    MVP: supports application/json with schema type=object + properties + required
    """
    rb = op.get("requestBody")
    if not isinstance(rb, dict):
        return ([], False)

    content = rb.get("content")
    if not isinstance(content, dict):
        return ([], False)

    app_json = content.get("application/json")
    if not isinstance(app_json, dict):
        return ([], False)

    schema = app_json.get("schema")
    if not isinstance(schema, dict):
        return ([], True)  # json body exists but unknown schema

    if schema.get("type") != "object":
        return ([], True)

    required = schema.get("required") or []
    if not isinstance(required, list):
        required = []

    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        props = {}

    fields: List[Dict[str, str]] = []
    for field_name, field_schema in props.items():
        if not isinstance(field_schema, dict):
            field_schema = {}
        ftype = str(field_schema.get("type") or "object")
        notes = ""
        if "description" in field_schema:
            notes = md_escape(str(field_schema.get("description") or ""))
        example = field_schema.get("example")
        if example is not None:
            notes = (notes + " " if notes else "") + f"Example: `{example}`"
        fields.append(
            {
                "name": str(field_name),
                "type": ftype,
                "required": "yes" if field_name in required else "no",
                "notes": notes,
            }
        )

    # stable order: required first then alpha
    fields.sort(key=lambda r: (r["required"] != "yes", r["name"]))
    return (fields, True)


def render_required_headers(has_bearer: bool, has_json_body: bool) -> str:
    headers = []
    if has_bearer:
        headers.append("`Authorization: Bearer <token>`")
    if has_json_body:
        headers.append("`Content-Type: application/json`")

    out = []
    out.append(md_h3("Required headers"))
    if headers:
        for h in headers:
            out.append(f"- {h}")
    else:
        out.append("None.")
    out.append("")
    return "\n".join(out)


def render_request_body_fields(fields: List[Dict[str, str]], has_json_body: bool) -> str:
    out = []
    out.append(md_h3("Request body fields"))
    if not has_json_body:
        out.append("This endpoint does not define a request body.")
        out.append("")
        return "\n".join(out)

    if not fields:
        out.append("Request body schema is JSON, but fields are not expanded in this MVP.")
        out.append("")
        return "\n".join(out)

    out.append("| Field | Type | Required | Notes |")
    out.append("|---|---|:---:|---|")
    for f in fields:
        name = f.get("name", "")
        ftype = f.get("type", "")
        req = f.get("required", "")
        notes = md_escape(f.get("notes", ""))
        out.append(f"| `{name}` | {ftype} | {req} | {notes} |")
    out.append("")
    return "\n".join(out)


def render_responses(op: Dict[str, Any]) -> str:
    out = []
    out.append(md_h3("Responses"))

    responses = op.get("responses") or {}
    if not isinstance(responses, dict) or not responses:
        out.append("No responses defined.")
        out.append("")
        return "\n".join(out)

    # sort codes: numeric-ish first
    def sort_key(code: str) -> Tuple[int, str]:
        try:
            return (0, f"{int(code):04d}")
        except Exception:
            return (1, code)

    for code in sorted(responses.keys(), key=sort_key):
        r = responses.get(code)
        if not isinstance(r, dict):
            continue
        desc = md_escape(str(r.get("description") or ""))
        out.append(f"**{code}** — {desc}" if desc else f"**{code}**")

        content = r.get("content") or {}
        ex = extract_json_example(content) if isinstance(content, dict) else None
        if ex is not None:
            out.append("")
            out.append("```json")
            out.append(json.dumps(ex, ensure_ascii=False, indent=2))
            out.append("```")
        out.append("")

    return "\n".join(out)


def render_endpoint_sections(ops: List[Tuple[str, str, Dict[str, Any]]], has_bearer: bool) -> str:
    out = []
    for method, path, op in ops:
        title = f"{method} {path}"
        out.append(md_h2(title))

        desc = op.get("description") or op.get("summary")
        if desc:
            out.append(md_escape(str(desc)))
            out.append("")

        fields, has_json_body = extract_request_fields(op)
        out.append(render_required_headers(has_bearer, has_json_body))
        out.append(render_request_body_fields(fields, has_json_body))
        out.append(render_responses(op))

    return "\n".join(out).rstrip() + "\n"


def build_markdown(spec: Dict[str, Any]) -> str:
    title = (spec.get("info") or {}).get("title") if isinstance(spec.get("info"), dict) else None
    if not title:
        title = "API reference"

    ops = collect_operations(spec)
    base_url = first_server_url(spec)
    has_bearer = detect_bearer_auth(spec)

    out: List[str] = []
    out.append(md_h1(f"{title} — reference").rstrip() + "\n")
    out.append("This page is a human-readable reference generated from an OpenAPI spec.\n")

    if base_url:
        out.append(f"**Base URL:** `{base_url}`\n")

    if ops:
        out.append(render_endpoint_summary(ops))
    else:
        out.append("No operations found in `paths`.\n")

    out.append(render_auth_section(has_bearer))

    if ops:
        out.append(render_endpoint_sections(ops, has_bearer))

    return "\n".join(out).strip() + "\n"


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert an OpenAPI YAML/JSON spec into a clean Markdown API reference."
    )
    p.add_argument("input", help="Path to OpenAPI spec (.yaml/.yml/.json)")
    p.add_argument(
        "-o",
        "--output",
        help="Output markdown file path. If omitted, prints to stdout.",
        default=None,
    )
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    try:
        spec = load_spec(args.input)
        md = build_markdown(spec)
    except Exception as ex:
        eprint(f"ERROR: {ex}")
        return 1

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"Wrote: {args.output}")
    else:
        print(md, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
