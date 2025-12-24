# Example API — reference

This page is a human-readable reference generated from an OpenAPI spec.

**Base URL:** `https://api.example.com`


## Endpoint summary

| Method | Path | Purpose |
|---:|---|---|
| POST | `/webhooks/hello` | Hello webhook |


## Authentication

All requests require a bearer token:

`Authorization: Bearer <token>`


## POST /webhooks/hello

Returns a greeting message.


### Required headers

- `Authorization: Bearer <token>`
- `Content-Type: application/json`


### Request body fields

| Field | Type | Required | Notes |
|---|---|:---:|---|
| `name` | string | yes | Example: `Luís` |


### Responses

**200** — OK

```json
{
  "ok": true,
  "message": "Hello Luís"
}
```

**400** — Bad Request (validation)

```json
{
  "error": {
    "code": "invalid_request",
    "message": "Missing required field: name",
    "request_id": "req_01HZYXABCDE1234567890"
  }
}
```

