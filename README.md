# openapi-to-human-reference

Convert an OpenAPI spec into a clean, human-readable API reference in Markdown — using a consistent style (docs-as-code friendly).

## Why this exists
OpenAPI is great as a contract, but many teams still need:
- a narrative “how to use it” reference
- consistent examples and error models
- a reviewer-friendly, readable format for docs sites (MkDocs, Docusaurus, etc.)

This repo is a small, practical tool to generate that human layer from an OpenAPI file.

## What it produces
Given an OpenAPI YAML/JSON file, it outputs a Markdown reference with:
- Endpoint summary table
- Authentication section
- Required headers + request body fields
- Response list (success + common error codes)
- A consistent error model section (optional but recommended)
- Copy/paste examples

## Status
MVP in progress. The first goal is a predictable, good-looking output for a small, common subset of OpenAPI.

## Planned features (near-term)
- Support OpenAPI 3.0/3.1 basics: paths, operations, requestBody, responses
- Render tables for fields and response schemas
- Examples: pull from `example` / `examples`
- Optional “At a glance” block (audience, auth, content-type, success criteria, pitfalls)

## Contributing
Issues and PRs are welcome. If you share an OpenAPI file that fails, please include:
- the spec (or a reduced sample)
- expected vs actual output
- your environment (Python version)

## License
MIT
