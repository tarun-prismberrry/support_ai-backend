# Microservice Handoff & Integration Runbook

**Service**: Multi-Tenant B2B Customer Support AI — Backend & Database  
**Author**: Tarun Saini (Backend & Database Intern)  
**Status**: Production Ready & Fully Tested (24/24 Integration Tests Passing)  
**Base URL**: `http://localhost:8000/api/v1`  
**Database Host**: `localhost:5432` (`support_ai_db`)  
**Redis Host**: `localhost:6379`

---

## 1. Quickstart: Running the Infrastructure & Service

### Option A: Local Virtualenv Development
```bash
# 1. Start Database & Redis
docker compose up -d postgres redis

# 2. Run Database Migrations
alembic upgrade head

# 3. Seed Realistic Multi-Tenant Data (CONTRACTS.md §1 & §7)
python -m app.scripts.seed

# 4. Start FastAPI Application
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Option B: Full Containerized Stack
```bash
docker compose up --build -d
```
The backend automatically waits for Postgres & Redis healthchecks, applies Alembic migrations via `docker/entrypoint.sh`, and starts Uvicorn.

### Health Probes (CONTRACTS.md §3.C)
* **Liveness Probe**: `GET http://localhost:8000/health/live` -> `{"status": "alive"}`
* **Readiness Probe**: `GET http://localhost:8000/health/ready` -> `{"status": "ready"}` (verifies DB & Redis sockets)

---

## 2. Fixed Test Personas & Authentication (CONTRACTS.md §1 & §2)

All users share the default seeded password: `Password123!`

| Persona | Email | Organization | Org ID | Role & Scope |
|---|---|---|---|---|
| **Alice** | `alice@orga.com` | Org A (Alpha Corp) | `11111111-1111-1111-1111-111111111111` | Admin (`*` wildcard) |
| **Bob** | `bob@orga.com` | Org A (Alpha Corp) | `11111111-1111-1111-1111-111111111111` | Support Agent (`ticket.*`, `ticket.note:*`) |
| **Charlie** | `charlie@customer.com` | Org A (Alpha Corp) | `11111111-1111-1111-1111-111111111111` | Customer (`ticket.*:own`, `kb.read:public`) |
| **Dave** | `dave@orgb.com` | Org B (Beta LLC) | `22222222-2222-2222-2222-222222222222` | Org B Admin (Cross-tenant barrier) |
| **Eve** | `eve@customer-b.com` | Org B (Beta LLC) | `22222222-2222-2222-2222-222222222222` | Org B Customer (Cross-tenant barrier) |

### Obtaining JWT Tokens
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "bob@orga.com", "password": "Password123!"}'
```
**Response:**
```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### Inspecting Authenticated Identity & Permissions
Pass the token in the `Authorization: Bearer <token>` header:
```bash
curl -X GET http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <token>"
```
**Response:**
```json
{
  "user_id": "bbbbbbb1-1111-1111-1111-111111111111",
  "org_id": "11111111-1111-1111-1111-111111111111",
  "role_name": "Support_Agent",
  "permissions": [
    "ticket.read:all",
    "ticket.write:all",
    "ticket.note:read",
    "ticket.note:write",
    "kb.read:public",
    "kb.read:internal",
    "refund.issue"
  ],
  "authorized_kb_tiers": ["public", "internal_staff"]
}
```

---

## 3. Pulkit Singla — MCP Tools Integration Runbook

All 6 canonical MCP tools map directly to REST endpoints under `/api/v1/`.

### Tool 1: `get_customer_invoices`
* **Route**: `GET /api/v1/invoices`
* **Auth**: Bearer token (Customer Charlie sees own invoices; Staff Bob sees all Org A invoices).
* **Sample Request**:
  ```bash
  curl -X GET http://localhost:8000/api/v1/invoices \
    -H "Authorization: Bearer <token>"
  ```
* **Sample Response**:
  ```json
  [
    {
      "id": "769a2504-7c6c-5950-88f9-6382cfeafd12",
      "org_id": "11111111-1111-1111-1111-111111111111",
      "customer_id": "ccccccc2-2222-2222-2222-222222222222",
      "ticket_id": "c1111111-1111-1111-1111-111111111111",
      "product_name": "Enterprise Cloud Suite",
      "amount": "250.00",
      "currency": "USD",
      "status": "paid",
      "refunded_amount": "0.00",
      "created_at": "2026-11-20T10:00:00Z"
    }
  ]
  ```

---

### Tool 2: `issue_refund` (and HITL Approval Workflow)
* **Route**: `POST /api/v1/invoices/{invoice_id}/refund`
* **Rules**:
  * **Refund <= $100.00**: Directly issued without supervisor approval.
  * **Refund > $100.00**: Requires Human-in-the-Loop (HITL) supervisor approval.

#### Automatic Escalation Case (Amount > $100)
```bash
curl -X POST http://localhost:8000/api/v1/invoices/769a2504-7c6c-5950-88f9-6382cfeafd12/refund \
  -H "Authorization: Bearer <bob_token>" \
  -H "Content-Type: application/json" \
  -d '{"amount": "250.00", "reason": "Customer billing dispute"}'
```
**HTTP Status: `400 Bad Request`**
```json
{
  "error": {
    "code": "REQUIRES_APPROVAL",
    "message": "Refund amount ($250.00) exceeds $100.00 threshold and requires supervisor approval.",
    "details": {
      "invoice_id": "769a2504-7c6c-5950-88f9-6382cfeafd12",
      "amount": "250.00",
      "threshold": "100.00",
      "approval_token": "eyJhbGciOi..."
    }
  }
}
```

#### Supervisor Approval Execution
Admin (Alice) submits the signed approval token:
* **Route**: `POST /api/v1/invoices/{invoice_id}/refund/approve`
```bash
curl -X POST http://localhost:8000/api/v1/invoices/769a2504-7c6c-5950-88f9-6382cfeafd12/refund/approve \
  -H "Authorization: Bearer <alice_token>" \
  -H "Content-Type: application/json" \
  -d '{"approval_token": "eyJhbGciOi...", "amount": "250.00"}'
```
**HTTP Status: `200 OK`**
```json
{
  "id": "769a2504-7c6c-5950-88f9-6382cfeafd12",
  "status": "refunded",
  "refunded_amount": "250.00",
  "amount": "250.00"
}
```
*Token replay protection*: Once approved, the Redis token is deleted. Replaying the token returns `403 Forbidden` (`APPROVAL_TOKEN_INVALID`).

---

### Tool 3: `create_ticket`
* **Route**: `POST /api/v1/tickets`
```bash
curl -X POST http://localhost:8000/api/v1/tickets \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "System login latency",
    "description": "API responses are taking > 3 seconds during peak hours.",
    "priority": "high",
    "initial_message": "Please investigate our US-East region latency."
  }'
```

---

### Tool 4: `get_ticket`
* **Route**: `GET /api/v1/tickets/{ticket_id}`
* **Includes**: Ticket metadata, customer details, and full chronological dialogue message history.
```bash
curl -X GET http://localhost:8000/api/v1/tickets/c1111111-1111-1111-1111-111111111111 \
  -H "Authorization: Bearer <token>"
```

---

### Tool 5: `add_ticket_note` (Staff Internal Only)
* **Route**: `POST /api/v1/tickets/{ticket_id}/notes`
* **RBAC Rule**: Requires `ticket.note:write`. Customers attempting this endpoint receive `403 FORBIDDEN`.
```bash
curl -X POST http://localhost:8000/api/v1/tickets/c1111111-1111-1111-1111-111111111111/notes \
  -H "Authorization: Bearer <bob_token>" \
  -H "Content-Type: application/json" \
  -d '{"note": "Escalated to engineering L2. Verified customer tier is Gold."}'
```

---

### Tool 6: `update_ticket_status`
* **Route**: `PATCH /api/v1/tickets/{ticket_id}/status`
* **Valid Status Values**: `open`, `in_progress`, `waiting_customer`, `resolved`, `closed`
* **RBAC Rule**: Customers can only close their own tickets (`closed`). Only Agents/Admins can transition between `in_progress`, `waiting_customer`, and `resolved`.
```bash
curl -X PATCH http://localhost:8000/api/v1/tickets/c1111111-1111-1111-1111-111111111111/status \
  -H "Authorization: Bearer <bob_token>" \
  -H "Content-Type: application/json" \
  -d '{"status": "in_progress"}'
```

---

## 4. Akshit Chandel — RAG / Knowledge Base Integration Runbook

### Database Connection
* **PostgreSQL URL**: `postgresql://postgres:postgres@localhost:5432/support_ai_db`
* **Table**: `knowledge_base_articles`
* **Vector Extension**: `pgvector` enabled (`vector` extension)
* **Dimension**: **384** (`sentence-transformers/all-MiniLM-L6-v2`)

### Schema Specification
```sql
CREATE TABLE knowledge_base_articles (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    document_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    access_level VARCHAR(32) NOT NULL, -- 'public' | 'internal_staff' | 'admin_only'
    embedding VECTOR(384),            -- 384-dimensional dense vectors
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### Performing Semantic Vector Search (`retrieve_kb`)
Call `/auth/me` with the caller's JWT to get `org_id` and `authorized_kb_tiers`. Then execute:

```sql
SELECT 
    document_id,
    chunk_index,
    title,
    content,
    access_level,
    1 - (embedding <=> :query_embedding::vector) AS similarity_score
FROM knowledge_base_articles
WHERE org_id = :caller_org_id
  AND access_level = ANY(:authorized_kb_tiers)
ORDER BY embedding <=> :query_embedding::vector ASC
LIMIT :limit;
```

*Notes on Multi-Chunk Articles*:
Seeded articles include multi-chunk documents (e.g., Refund Policy SOP broken into `chunk_index` 0, 1, 2) with distinct embeddings to test chunk retrieval and reranking.

---

## 5. Shashank — LangGraph Orchestrator Integration Runbook

### Dedicated Database Schema & User
* **User**: `orchestrator_user`
* **Password**: `orchestrator_pass`
* **Dedicated Schema**: `orchestrator`
* **Permissions**: Full read/write on `orchestrator` schema; access to `public` business tables is revoked to prevent unlogged state mutations.

### State Graph Checkpoint Persistence
Point LangGraph checkpointers (e.g. `PostgresSaver`) to:
```text
postgresql+asyncpg://orchestrator_user:orchestrator_pass@localhost:5432/support_ai_db
```
Configure your checkpointer table within the `orchestrator` schema:
```python
# Example checkpointer setup
checkpointer = PostgresSaver.from_conn_string(
    "postgresql://orchestrator_user:orchestrator_pass@localhost:5432/support_ai_db",
    schema="orchestrator"
)
```

### LangGraph HITL State Machine Flow
```mermaid
stateDiagram-v2
    [*] --> AgentTriage: User asks question / refund
    AgentTriage --> ExecuteDirect: Refund <= $100
    ExecuteDirect --> [*]: Refund Success

    AgentTriage --> InterruptNode: Refund > $100
    InterruptNode --> WaitSupervisor: Pause Graph & surface approval_token
    WaitSupervisor --> SupervisorApproved: Admin calls /refund/approve
    WaitSupervisor --> SupervisorRejected: Supervisor declines
    SupervisorApproved --> [*]: Graph Resumes & Emits Success
    SupervisorRejected --> [*]: Graph Resumes & Emits Rejection
```

---

## 6. Standardized Error Response Model (CONTRACTS.md §3)

All endpoints strictly adhere to this JSON format on failures:
```json
{
  "error": {
    "code": "ERROR_CODE_STRING",
    "message": "Human-readable explanation of error.",
    "details": null
  }
}
```

### Canonical Error Codes
| HTTP Status | Error Code | Description |
|---|---|---|
| `400 Bad Request` | `VALIDATION_ERROR` | Schema validation error |
| `400 Bad Request` | `REQUIRES_APPROVAL` | Refund exceeds threshold ($100) |
| `400 Bad Request` | `REFUND_EXCEEDS_BALANCE` | Refund requested exceeds remaining balance |
| `401 Unauthorized`| `UNAUTHORIZED` | Invalid or expired JWT token |
| `403 Forbidden`   | `FORBIDDEN` | Missing required RBAC permission |
| `403 Forbidden`   | `APPROVAL_TOKEN_INVALID` | Stale, tampered, or already-used HITL approval token |
| `404 Not Found`   | `NOT_FOUND` | Resource does not exist or belongs to another tenant |
| `409 Conflict`    | `STATE_CONFLICT` | Illegal ticket status transition |
| `500 Server Error`| `INTERNAL_ERROR` | Unhandled backend exception |
| `503 Unavailable` | `SERVICE_UNAVAILABLE` | Database or Redis readiness probe failed |
