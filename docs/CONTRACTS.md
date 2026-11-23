# Multi-Tenant B2B Customer Support AI — Shared Team Contract (v2.3 Final)
**Maintainer:** Tarun Saini (Backend & Database)  
**Stakeholders:** Pulkit Singla (MCP), Akshit Chandel (RAG), Shashank Pathania (LangGraph)

---

## 1. Fixed Test Identities & Deterministic UUIDs

All unit tests, local mocks, and integration suites across all 4 repositories MUST use these deterministic identities:

| Identity | User ID | Customer ID | Org ID | Org Name | Role | Email |
|---|---|---|---|---|---|---|
| **Alice** | `aaaaaaa1-1111-1111-1111-111111111111` | `null` | `11111111-1111-1111-1111-111111111111` | Org A | `Org_Admin` | `alice@orga.com` |
| **Bob** | `bbbbbbb1-1111-1111-1111-111111111111` | `null` | `11111111-1111-1111-1111-111111111111` | Org A | `Support_Agent` | `bob@orga.com` |
| **Charlie** | `ccccccc1-1111-1111-1111-111111111111` | `ccccccc2-2222-2222-2222-222222222222` | `11111111-1111-1111-1111-111111111111` | Org A | `End_Customer` | `charlie@customer.com` |
| **Dave** | `ddddddd2-2222-2222-2222-222222222222` | `null` | `22222222-2222-2222-2222-222222222222` | Org B | `Org_Admin` | `dave@orgb.com` |

---

## 2. JWT Authentication & Zero-Trust Verification

### A. Environment Configuration & Algorithm Pinning
- **Signing Key:** Provided via environment variable `JWT_SECRET_KEY` in all 4 services.
- **Pinned Algorithm:** Every service must strictly pin `algorithms=["HS256"]` when calling `jwt.decode()` to prevent algorithm confusion attacks.
- **Propagation:** LangGraph forwards the bearer token in HTTP `Authorization: Bearer <token>` request headers. Raw tokens must NEVER be injected into LLM prompts or stored in conversation state.

### B. Minting vs. Verification
1. **Minting:** Tarun's Backend only (`POST /auth/login`).
2. **Verification:** Verified statelessly in memory by every service using `PyJWT` and `JWT_SECRET_KEY` (< 1ms execution, no database network call).

### C. Claims Structure
```json
{
  "sub": "ccccccc1-1111-1111-1111-111111111111",
  "user_id": "ccccccc1-1111-1111-1111-111111111111",
  "customer_id": "ccccccc2-2222-2222-2222-222222222222",
  "email": "charlie@customer.com",
  "org_id": "11111111-1111-1111-1111-111111111111",
  "role": "End_Customer",
  "exp": 1893456000,
  "iss": "support-ai-backend",
  "aud": "support-ai-services"
}
```
*(Note: `customer_id` is populated for `End_Customer` and `null` for staff).*

### D. Verified User Context (For LangGraph `AgentState`)
```python
user_context = {
    "user_id": "ccccccc1-1111-1111-1111-111111111111",
    "customer_id": "ccccccc2-2222-2222-2222-222222222222",
    "org_id": "11111111-1111-1111-1111-111111111111",
    "role": "End_Customer",
    "email": "charlie@customer.com"
}
```

---

## 3. Standardized Error Response & Service Health

### A. Error Envelope
All endpoints and tools return this JSON envelope on HTTP 4xx/5xx:
```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Only Org_Admin users can execute refunds.",
    "details": null
  }
}
```

### B. Standard Error Codes
- `UNAUTHORIZED` (HTTP 401): Missing, invalid, or expired JWT.
- `FORBIDDEN` (HTTP 403): Authenticated, but role or tenant lacks permission.
- `NOT_FOUND` (HTTP 404): Resource missing OR cross-tenant query (`org_id` mismatch).
- `VALIDATION_ERROR` (HTTP 422): Malformed JSON, missing fields, or invalid types.
- `CONFLICT` (HTTP 409): Duplicate operation or invalid status transition.
- `SERVICE_UNAVAILABLE` (HTTP 503): Database or downstream service unreachable.

### C. Service Health Probe
Every service must implement `GET /health`:
```json
{
  "status": "available",
  "database": "connected",
  "version": "1.0.0"
}
```

---

## 4. Canonical Enums & State Machines

- **Roles:** `"Org_Admin"`, `"Support_Agent"`, `"End_Customer"`
- **Ticket Status:** `"open"`, `"in_progress"`, `"resolved"`, `"closed"`
- **Ticket Priority:** `"low"`, `"medium"`, `"high"`, `"urgent"`
- **Ticket Category:** `"billing"`, `"technical"`, `"account"`, `"general"`
- **Sender Type (Messages):** `"customer"`, `"support_agent"`, `"ai_agent"`, `"system"`
- **Knowledge Base Access Level / Tier:** `"public"`, `"internal_staff"`, `"admin_only"`
- **Invoice Status:** `"paid"`, `"pending"`, `"refunded"`, `"partially_refunded"`
- **LangGraph Agents:** `"triage"`, `"knowledge"`, `"billing"`
- **Approval Status:** `"pending"`, `"approved"`, `"rejected"`, `"expired"`

### Ticket Status Lifecycle Rules:
- `open` -> `in_progress`, `closed`
- `in_progress` -> `resolved`, `closed`
- `resolved` -> `closed`, `in_progress` (reopened)
- `closed` -> `in_progress` (reopened by staff)
- Customers may only transition their own tickets from `resolved` -> `closed`. If a ticket is reopened to `in_progress`, only staff may move it back to `resolved`.

---

## 5. Akshit (RAG) — Chunked Vector Store & Access Control

**Table:** `knowledge_base_articles`
```sql
CREATE TABLE knowledge_base_articles (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    document_id UUID NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    access_level VARCHAR(32) NOT NULL, -- 'public' | 'internal_staff' | 'admin_only'
    embedding VECTOR(1536),            -- pgvector column
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_kb_lookup ON knowledge_base_articles (org_id, access_level);
```

### Role-to-Access-Level Query Matrix (Pre-Retrieval SQL Filter):
| Role | Authorized `access_level` Values |
|---|---|
| **End_Customer** | `['public']` |
| **Support_Agent** | `['public', 'internal_staff']` |
| **Org_Admin** | `['public', 'internal_staff', 'admin_only']` |

*Retrieval Security Rule:* The query must execute:  
`WHERE org_id = $1 AND access_level = ANY($2)`  
Filtering after retrieval in Python is strictly prohibited.

---

## 6. Pulkit & Shashank — The 6 Canonical MCP Tools

Pulkit's MCP service exposes these 6 tools to LangGraph agents:

### 1. `get_ticket_details`
- **Inputs:** `ticket_id: UUID`
- **Output:** Complete Ticket JSON object.
- **Permissions:** Staff can view any org ticket. Customer can ONLY view tickets matching their `customer_id`. (Mismatches return `404 NOT_FOUND`).

### 2. `search_tickets`
- **Inputs:** `query: str`, `status: Optional[str]`, `limit: Optional[int] = 10`
- **Output:** `list[Ticket]`
- **Search Scope:** Case-insensitive substring search matching against both `title` and `description` via PostgreSQL `ILIKE`.
- **Permissions:** Staff searches across org tickets. Customer searches strictly within their own tickets.

### 3. `create_ticket`
- **Inputs:** `title: str`, `description: str`, `category: str`, `priority: Optional[str] = "medium"`, `customer_id: Optional[UUID] = None`
- **Output:** Newly created `Ticket` object (status: `"open"`).
- **Rules:**
  - If caller is `End_Customer`: `customer_id` is automatically taken from their JWT (`claims['customer_id']`). Any passed `customer_id` is ignored.
  - If caller is `Support_Agent` or `Org_Admin`: caller may provide `customer_id: UUID`. Backend validates that the customer exists and belongs to the staff member's `org_id`. If invalid or cross-tenant, returns `404 NOT_FOUND` (`"Customer not found in this organization"`).

### 4. `update_ticket_status`
- **Inputs:** `ticket_id: UUID`, `status: str`
- **Output:** Updated `Ticket` object.
- **Permissions:** Staff only (`Org_Admin`, `Support_Agent`). Status change must follow the valid state machine.

### 5. `add_internal_note`
- **Inputs:** `ticket_id: UUID`, `note: str`
- **Output:** 
  ```json
  {
    "id": "uuid",
    "ticket_id": "uuid",
    "org_id": "uuid",
    "author_id": "uuid",
    "note": "string",
    "created_at": "ISO-8601 string"
  }
  ```
- **Permissions:** Staff only (`Org_Admin`, `Support_Agent`). Customer -> `403 FORBIDDEN`.

### 6. `issue_refund`
- **Inputs:** `invoice_id: UUID`, `amount: Decimal` (stringified, e.g. `"250.00"`), `reason: str`, `idempotency_key: str`, `approval_token: Optional[str] = None`
- **Output:** Updated Invoice object (status: `"refunded"` or `"partially_refunded"`).
- **Backend Defense-in-Depth Enforcement:**
  1. Only `Org_Admin` (Alice) allowed. (`Support_Agent` Bob -> `403 FORBIDDEN`).
  2. If `amount > 100.00`, backend requires a valid `approval_token`.
  3. Token Validation: Backend verifies `approval_token` signature and ensures it binds `invoice_id`, `amount`, `org_id`, and `approver_id`. The token has a 15-minute TTL and is single-use (consumed upon execution).
  4. Amount check: `amount` cannot exceed remaining unrefunded invoice balance.
  5. Idempotency: `idempotency_key` (globally unique UUID) checked against database to prevent duplicate refund executions.
  6. Atomic DB Transaction: Invoice update + Audit Log row inserted in single transaction.

---

## 7. Kaggle Dataset & External Support Data Mapping

When seeding or ingesting the Kaggle Customer Support Ticket Dataset, the flat CSV columns map to our relational tables as follows:

| Kaggle Dataset Column | Database Table | Column Name & Type | Mapping / Engineering Notes |
|---|---|---|---|
| **Ticket ID** | `tickets` | `id UUID` | Deterministically generated UUID |
| **Ticket Subject** | `tickets` | `title VARCHAR(255)` | Direct semantic mapping (standard industry naming) |
| **Ticket Description** | `tickets` | `description TEXT` | Direct semantic mapping |
| **Ticket Type / Category** | `tickets` | `category VARCHAR(64)` | Normalized to canonical categories |
| **Ticket Status** | `tickets` | `status VARCHAR(32)` | Normalized to `open`, `in_progress`, `resolved`, `closed` |
| **Ticket Priority** | `tickets` | `priority VARCHAR(32)` | Normalized to `low`, `medium`, `high`, `urgent` |
| **Ticket Channel** | `tickets` | `channel VARCHAR(32)` | `'chat'`, `'email'`, `'web'`, `'phone'` |
| **Resolution** | `tickets` | `resolution TEXT` | Nullable resolution summary |
| **Customer Satisfaction Rating**| `tickets` | `csat_rating INTEGER` | Integer 1 to 5 (nullable) |
| **First Response Time** | `tickets` | `first_response_at TIMESTAMPTZ` | Event timestamp for live SLA calculation |
| **Time to Resolution** | `tickets` | `resolved_at TIMESTAMPTZ` | Event timestamp for live SLA calculation |
| **Customer Name** | `customers` | `full_name VARCHAR(255)` | Customer account profile |
| **Customer Email** | `customers` | `email VARCHAR(255)` | Customer account profile |
| **Customer Age** | `customers` | `age INTEGER` | Nullable demographic field / `metadata JSONB` |
| **Customer Gender** | `customers` | `gender VARCHAR(32)` | Nullable demographic field / `metadata JSONB` |
| **Product Purchased** | `invoices` & `tickets` | `product_name VARCHAR(255)` | Billed product / ticket context |
| **Date of Purchase** | `invoices` | `created_at TIMESTAMPTZ` | Invoice transaction timestamp |
  