# API reference (v1)

Base path `/api/v1`. JSON in and out. Interactive docs: `/docs`; machine-readable schema: [openapi.json](openapi.json).
All endpoints except `health` and `auth/token` need `Authorization: Bearer <token>`.
Request bodies are strict: unknown fields, NaN/Infinity, and malformed UUIDs are rejected with `422`.

## Error envelope

```json
{"error": {"code": "validation_error", "message": "Invalid input",
           "fields": [{"field": "ph", "issue": "must be between 0 and 14"}]},
 "request_id": "…"}
```

| HTTP | code | When |
| --- | --- | --- |
| 401 | `unauthorized`, `invalid_credentials` | Missing/expired/tampered token; bad login |
| 403 | `forbidden` | Role not allowed for this action |
| 404 | `not_found` | Resource missing **or** outside the caller's tenant (no existence leak) |
| 409 | `duplicate_conflict` | Same id reused with different data |
| 409 | `configuration_required` | Tank limits or customer mapping missing |
| 409 | `request_in_progress` | Same chat message already being processed |
| 409 | `duplicate_feedback`, `case_closed`, `conversation_mismatch` | See endpoint notes |
| 422 | `validation_error` | Schema, range, or timestamp problem |
| 429 | `rate_limited` | More than 6 chat messages/minute (`Retry-After: 10`) |
| 503 | `policy_unavailable` | Authorization engine failed; requests fail closed |

## Authorization matrix (policy/aquaguard.rego)

| Action | simulator | customer | agent |
| --- | --- | --- | --- |
| `readings:write` | assigned tanks only | — | — |
| `readings:read` | — | own client | scoped clients |
| `messages:write`, `cases:open`, `feedback:write` | — | own client | — |
| `cases:read`, `cases:reply`, `transcript:read` | — | (own transcript) | scoped clients |

## Endpoints

### `GET /health`
`200 {"status":"ok","version":"0.5.0-alpha","model_version":"aq-v1"}`

### `POST /auth/token`
Body `{"username","password"}` → `200 {"access_token","token_type":"bearer","expires_in":1800}`.

### `GET /me`
Current user, role, and visible tanks.

### `POST /tanks/{tank_id}/readings` (simulator)
```json
{"reading_id":"<uuid>","observed_at":"2026-11-07T12:00:00Z","temperature_c":25.4,"ph":8.1,"water_level_pct":95}
```
Ranges: temperature 0–50 °C, pH 0–14, level 0–100 %; `observed_at` within the last 24 h.
`201 {"reading_id","stored_at","threshold_status":"normal|alert"}`. Retrying the identical body returns `200`
with the original result; the same `reading_id` with different values returns `409 duplicate_conflict`.

### `GET /tanks/{tank_id}/readings?limit=100&cursor=…`
Newest first, `limit` 1–500, opaque `next_cursor` for the next page.

### `POST /tanks/{tank_id}/messages` (customer)
```json
{"message_id":"<uuid>","conversation_id":"<uuid>","text":"Why is the temperature rising?"}
```
`201` →
```json
{"message_id":"…","assistant_message_id":"…","reply":"…","anomaly_status":"normal|warning|insufficient_data|unavailable",
 "model_version":"aq-v1|fallback","handoff_required":false}
```
When `handoff_required` is true the response also has `case_id`. Escalation happens on an explicit request for a
human, an out-of-scope question, an AI timeout (deadline 8 s), or invalid model output. Retrying the same
`message_id` returns the stored answer (`200`).

### `POST /conversations/{conversation_id}/cases` (customer)
Body `{"reason"}`. `201 {"case_id","status":"open"}` new case; `200` if an open case already exists for the conversation (idempotent).

### `GET /cases?status=open|closed&limit=50` (agent)
Cases for the agent's scoped clients, oldest first.

### `GET /conversations/{conversation_id}/messages`
Transcript (customer, assistant, agent messages, oldest first; most recent `limit`). Customers see only their own conversations.

### `POST /cases/{case_id}/replies` (agent)
Body `{"reply_id":"<uuid>","text","close_case":true}`. `201`; identical retry `200`; new reply to a closed case `409 case_closed`.

### `POST /messages/{message_id}/feedback` (customer)
Body `{"helpful":true,"comment":"optional"}`. One per assistant message (`409 duplicate_feedback`).
`201 {"feedback_id","review_status":"pending"}`.
