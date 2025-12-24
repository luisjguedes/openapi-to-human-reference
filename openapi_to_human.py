#!/usr/bin/env python3
"""
openapi_to_human.py

Minimal OpenAPI -> human-readable Markdown reference generator (MVP).
Supports a practical subset of OpenAPI 3.x:
- paths
- operations (get/post/put/patch/delete)
- summary/description
- requestBody (application/json) schema properties
- responses (status codes + description)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None  # type: ignore


HTTP_METHODS = ("get", "post", "put", "patch", "delete", "head", "options")


def load_spec(path: Path) -> Dict[str, Any]:
    data = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise SystemExit("PyYAML is required to load YAML. Add 'pyyaml' to requirements.txt.")
        return yaml.safe_load(data)
    if path.suffix.lower() == ".json":
        return json.loads(data)
    raise SystemExit("Unsupported spec format. Use .yaml/.yml or .json")


def md_escape(text: str) -> str:
    return text.replace("|", "\\|").strip()


def pick_json_schema(operation: Dict[str, Any]) -> Dict[str, Any] | None:
    rb = operation.get("requestBody") or {}
    content = rb.get("content") or {}
    app_json = content.get("application/json") or {}
    schema = app_json.get("schema")
    return schema


def schema_properties(schema: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """
    Returns (properties, required_list) for an object schema.
    Handles shallow object properties only (MVP).
    """
    if not isinstance(schema, dict):
        return {}, []
    props = schema.get("properties") or {}
    required = schema.get("required") or []
    if not isinstance(props, dict):
        props = {}
    if not isinstance(required, list):
        required = []
    return props, [str(x) for x in required]


def type_of(prop: Dict[str, Any]) -> str:
    t = prop.get("type")
    if isinstance(t, str):
        return t
    # very small fallback
    if "oneOf" in prop:
        return "oneOf"
    if "anyOf" in prop:
        return "anyOf"
    if "allOf" in prop:
        return "allOf"
    return "object"


def render_request_fields(schema: Dict[str, Any]) -> str:
    props, required = schema_properties(schema)
    if not props:
        return "_No documented JSON fields in request body (MVP)._"

    lines = []
    lines.append("| Field | Type | Required | Notes |")
    lines.append("|---|---|:---:|---|")

    for name, prop in props.items():
        if not isinstance(prop, dict):
            prop = {}
        t = type_of(prop)
        req = "yes" if name in required else "no"
        notes = prop.get("description") or ""
        example = prop.get("example")
        if example is not None:
            notes = f"{notes} Example: `{example}`".strip()
        lines.append(f"| `{md_escape(str(name))}` | {md_escape(t)} | {req} | {md_escape(str(notes))} |")

    return "\n".join(lines)


def render_responses(operation: Dict[str, Any]) -> str:
    responses = operation.get("responses") or {}
    if not isinstance(responses, dict) or not responses:
        return "_No responses documented._"

    # Sort numeric codes first, then others
    def sort_key(k: str):
        return (0, int(k)) if k.isdigit() else (1, k)

    lines = []
    for code in sorted(responses.keys(), key=sort_key):
        r = responses.get(code) or {}
        if not isinstance(r, dict):
            r = {}
        desc = r.get("description") or ""
        lines.append(f"- `{code}` — {md_escape(str(desc))}".rstrip())
    return "\n".join(lines)


def endpoint_summary(spec: Dict[str, Any]) -> str:
    paths = spec.get("paths") or {}
    if not isinstance(paths, dict) or not paths:
        return "_No paths found._"

    rows = []
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in HTTP_METHODS:
            if method in path_item and isinstance(path_item[method], dict):
                op = path_item[method]
                purpose = op.get("summary") or op.get("description") or ""
                rows.append((method.upper(), str(path), str(purpose).strip()))

    if not rows:
        return "_No operations found._"

    lines = []
    lines.append("| Method | Path | Purpose |")
    lines.append("|---:|---|---|")
    for m, p, purpose in rows:
        lines.append(f"| {m} | `{md_escape(p)}` | {md_escape(purpose)} |")
    return "\n".join(lines)


def render_operation(path: str, method: str, operation: Dict[str, Any]) -> str:
    title = f"## {method.upper()} {path}"
    summary = (operation.get("summary") or "").strip()
    description = (operation.get("description") or "").strip()

    parts = [title]
    if summary:
        parts.append(summary)
    elif description:
        parts.append(description)

    schema = pick_json_schema(operation)
    if schema:
        parts.append("")
        parts.append("### Request body fields")
        parts.append(render_request_fields(schema))

    parts.append("")
    parts.append("### Responses")
    parts.append(render_responses(operation))

    return "\n".join(parts)


def generate_markdown(spec: Dict[str, Any], source_path: str) -> str:
    title = "# API reference\n"
    intro = f"This reference is generated from the OpenAPI source: `{source_path}`.\n"
    parts = [title, intro, "## Endpoint summary\n", endpoint_summary(spec), ""]

    paths = spec.get("paths") or {}
    if isinstance(paths, dict):
        for path, path_item in paths.items():
            if not isinstance(path_item, dict):
                continue
            for method in HTTP_METHODS:
                op = path_item.get(method)
                if isinstance(op, dict):
                    parts.append(render_operation(str(path), method, op))
                    parts.append("")

    return "\n".join(parts).strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate a human-readable Markdown API reference from OpenAPI.")
    ap.add_argument("spec", type=str, help="Path to OpenAPI file (.yaml/.yml/.json)")
    ap.add_argument("-o", "--out", type=str, default="REFERENCE.md", help="Output markdown file")
    args = ap.parse_args()

    spec_path = Path(args.spec)
    out_path = Path(args.out)

    spec = load_spec(spec_path)
    md = generate_markdown(spec, source_path=args.spec)
    out_path.write_text(md, encoding="utf-8")

    print(f"Wrote: {out_path}")


if __name__ == "__main__":
    main()
