# Multi-Tenant B2B Customer Support AI — Shared Team Contract (v3.0 Locked)
**Maintainer:** Tarun Saini (Backend & Database)  
**Stakeholders:** Pulkit Singla (MCP), Akshit Chandel (RAG), Shashank Pathania (LangGraph)

---

## 1. Fixed Test Identities & Deterministic UUIDs

All unit tests, local mocks, and integration suites across all 4 repositories MUST use these deterministic identities:

| Identity | User ID (`sub`) | Customer ID | Org ID | Org Name | Seeded Role | Email |
|---|---|---|---|---|---|---|
| **Alice** | `aaaaaaa1-1111-1111-1111-111111111111` | `null` | `11111111-1111-1111-1111-111111111111` | Org A | `Org_Admin` | `alice@orga.com` |
| **Bob** | `bbbbbbb1-1111-1111-1111-111111111111` | `null` | `11111111-1111-1111-1111-111111111111` | Org A | `Support_Agent` | `bob@orga.com` |
| **Charlie** | `ccccccc1-1111-1111-1111-111111111111` | `ccccccc2-2222-2222-2222-222222222222` | `11111111-1111-1111-1111-111111111111` | Org A | `End_Customer` | `charlie@customer.com` |
| **Dave** | `ddddddd2-2222-2222-2222-222222222222` | `null` | `22222222-2222-2222-2222-222222222222` | Org B | `Org_Admin` | `dave@orgb.com` |

---

## 2. JWT Authentication, Lean Token & User Context Flow

### A. Environment Configuration & Algorithm Pinning
- **Signing Key:** Environment variable `JWT_SECRET_KEY` in all 4 services.
- **Pinned Algorithm:** Every service must strictly pin `algorithms=["HS256"]` when calling `jwt.decode()` to prevent algorithm confusion attacks.
- **Header Propagation:** Downstream services forward the token in HTTP `Authorization: Bearer <token>` headers. Raw tokens must NEVER be injected into LLM prompts or stored in conversation state.

### B. Lean JWT Claims Structure
To guarantee instant permission revocation and support custom roles per company, `role`, `org_id`, and `permissions` are NOT baked into the token. The token is a **Lean Token**:
```json
{
  "sub": "aaaaaaa1-1111-1111-1111-111111111111",
  "user_id": "aaaaaaa1-1111-1111-1111-111111111111",
  "exp": 1893456000,
  "iat": 1732440000,
  "iss": "support-ai-backend",
  "aud": "support-ai-services"
}
```

### C. User Context Resolution (`GET /auth/me`)
1. **Flow:** LangGraph calls `GET /auth/me` once at the start of a user session.
2. **Caching & Instant Revocation:** Backend caches resolved identity in Redis (`user:{user_id}:context`, TTL 5 minutes). When an administrator edits a role or user permissions, the backend immediately deletes the Redis key, providing zero-lag permission updates.
3. **Disabled Users:** If `users.is_active = FALSE`, `/auth/me` returns `401 UNAUTHORIZED` (`"Account is disabled"`).
4. **Response Schema:**
```json
{
  "id": "aaaaaaa1-1111-1111-1111-111111111111",
  "email": "alice@orga.com",
  "full_name": "Alice Admin",
  "org_id": "11111111-1111-1111-1111-111111111111",
  "customer_id": null,
  "role": "Org_Admin",
  "permissions": ["*"],
  "authorized_kb_tiers": ["public", "internal_staff", "admin_only"]
}
```

---

## 3. Standardized Error Response & Service Availability

### A. Error Envelope
All endpoints and MCP tools return this JSON envelope on HTTP 4xx/5xx:
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
- `UNAUTHORIZED` (HTTP 401): Missing, invalid, expired JWT, or disabled user.
- `FORBIDDEN` (HTTP 403): Authenticated, but lacking permission.
- `NOT_FOUND` (HTTP 404): Resource missing OR cross-tenant query (`org_id` mismatch).
- `VALIDATION_ERROR` (HTTP 422): Malformed JSON, missing fields, or invalid types.
- `CONFLICT` (HTTP 409): Duplicate operation or invalid status transition.
- `SERVICE_UNAVAILABLE` (HTTP 503): Database or downstream service unreachable.

### C. Liveness vs. Readiness Probes
- **`GET /health/live`**: Process liveness check (`{"status": "alive"}`).
- **`GET /health/ready`**: Dependency readiness check (verifies database pool & Redis). Returns `200 OK` (`{"status": "ready"}`) or `503 SERVICE_UNAVAILABLE`.

---

## 4. Dynamic RBAC & Canonical Permission Catalog

### A. Canonical Permission Catalog
Code authorization checks **permissions, never role names**:
- `ticket.read:own` / `ticket.read:org`
- `ticket.write:own` / `ticket.write:org`
- `ticket.status:update`
- `ticket.note:read` / `ticket.note:write`
- `refund.issue`
- `kb.read:public` / `kb.read:internal_staff` / `kb.read:admin_only`
- `role.manage`
- `*` (Full administrative wildcard)

### B. Dynamic Roles Table
```sql
CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    name VARCHAR(64) NOT NULL,
    description TEXT NULL,
    is_system BOOLEAN NOT NULL DEFAULT FALSE,
    permissions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_org_role_name UNIQUE (org_id, name)
);
```

### C. Onboarding & Seeding Rules
1. **Production:** When a company onboarded, exactly ONE initial `super-admin` role is created (`is_system = TRUE`, `permissions = ["*"]`). The account owner can create, edit, or delete custom roles.
2. **Local Development / Testing:** Default test roles (`Org_Admin`, `Support_Agent`, `End_Customer`) are seeded per organization for test automation.

---

## 5. Akshit (RAG) — Chunked Vector Store & `retrieve_kb` Tool

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
    embedding VECTOR(1536),            -- OpenAI text-embedding-3-small
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_kb_lookup ON knowledge_base_articles (org_id, access_level);
```

### Tool Contract: `retrieve_kb`
- **Inputs:** `query: str`, `limit: Optional[int] = 5`
- **Output:**
  ```json
  {
    "results": [
      {
        "document_id": "uuid",
        "chunk_index": 14,
        "title": "Refund Policy SOP",
        "content": "Refunds above $100 require supervisor approval within 3 business days...",
        "access_level": "internal_staff",
        "similarity_score": 0.892
      }
    ]
  }
  ```
- **Security Rule:** Query uses the caller's resolved `authorized_kb_tiers` from `/auth/me`:  
  `WHERE org_id = $1 AND access_level = ANY($2)`

---

## 6. Pulkit & Shashank — The 6 Canonical MCP Tools

### 1. `get_ticket_details`
- **Inputs:** `ticket_id: UUID`
- **Output:** Complete Ticket JSON object.
- **Permissions:** Staff with `ticket.read:org` sees any org ticket. Customer with `ticket.read:own` sees only own tickets (`customer_id` match).

### 2. `search_tickets`
- **Inputs:** `query: str`, `status: Optional[str]`, `limit: Optional[int] = 10` (max 50)
- **Output:** `list[Ticket]`
- **Search Scope:** Case-insensitive substring search matching against `title` and `description` via PostgreSQL `ILIKE`.

### 3. `create_ticket`
- **Inputs:** `title: str`, `description: str`, `category: str`, `priority: Optional[str] = "medium"`, `customer_id: Optional[UUID] = None`
- **Output:** Newly created `Ticket` object (status: `"open"`).
- **Rules:**
  - Customer caller: `customer_id` bound automatically from JWT; argument ignored.
  - Staff caller: requires `ticket.write:org`; `customer_id` validated against staff `org_id` (invalid/cross-tenant returns `404 NOT_FOUND`).

### 4. `update_ticket_status`
- **Inputs:** `ticket_id: UUID`, `status: str`
- **Output:** Updated `Ticket` object.
- **Permissions & Lifecycle Rules:**
  - Staff with `ticket.status:update`: can perform valid state transitions (`open` -> `in_progress`, `in_progress` -> `resolved`, `resolved` -> `closed`, `closed` -> `in_progress`).
  - Customer: **Allowed ONLY if** updating own ticket from `resolved` -> `closed`. All other transitions return `403 FORBIDDEN`.

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
- **Permissions:** Staff with `ticket.note:write`. Customer -> `403 FORBIDDEN`.

### 6. `issue_refund` & Complete HITL Workflow
- **Inputs:** `invoice_id: UUID`, `amount: Decimal` (stringified, e.g. `"250.00"`), `reason: str`, `idempotency_key: str`, `approval_token: Optional[str] = None`
- **HITL Approval Workflow (Amount > 100.00):**
  1. LangGraph detects `amount > 100.00` and interrupts execution.
  2. Alice (`Org_Admin`) reviews and clicks "Approve".
  3. Client calls `POST /invoices/{id}/approve-refund`.
  4. Backend verifies Alice has `refund.issue` permission and returns a signed single-use HMAC token:
     `token = HMAC_SHA256(JWT_SECRET_KEY, f"{invoice_id}:{amount}:{org_id}:{alice_user_id}:{expires_at}")` (TTL: 15 minutes).
  5. LangGraph resumes and calls `issue_refund(..., approval_token=token)`.
- **Backend Defense-in-Depth Checks:**
  1. Idempotency Check FIRST: If `idempotency_key` already executed, return cached refund response with `200 OK`.
  2. Permission: Caller must have `refund.issue`.
  3. If `amount > 100.00`: Verify `approval_token` signature and ensure token is not expired (< 15 min).
  4. Amount check: `amount > 0.00` and `<= remaining unrefunded balance`.
  5. Atomic Transaction: Mark invoice refunded, consume approval token, record in `AUDIT_LOGS`.

---

## 7. Kaggle Dataset & External Support Data Mapping

When seeding or ingesting the Kaggle Customer Support Ticket Dataset:

| Kaggle Dataset Column | Database Table | Column Name & Type | Mapping / Engineering Notes |
|---|---|---|---|
| **Ticket ID** | `tickets` | `id UUID` | Deterministic generation: `uuid.uuid5(uuid.NAMESPACE_DNS, f"ticket-{kaggle_id}")` |
| **Ticket Subject** | `tickets` | `title VARCHAR(255)` | Direct semantic mapping |
| **Ticket Description** | `tickets` | `description TEXT` | Direct semantic mapping |
| **Ticket Type / Category** | `tickets` | `category VARCHAR(64)` | Normalized to canonical categories |
| **Ticket Status** | `tickets` | `status VARCHAR(32)` | Normalized to `open`, `in_progress`, `resolved`, `closed` |
| **Ticket Priority** | `tickets` | `priority VARCHAR(32)` | Normalized to `low`, `medium`, `high`, `urgent` |
| **Ticket Channel** | `tickets` | `channel VARCHAR(32)` | `'chat'`, `'email'`, `'web'`, `'phone'` |
| **Resolution** | `tickets` | `resolution TEXT` | Nullable resolution summary |
| **Customer Satisfaction Rating**| `tickets` | `csat_rating INTEGER` | Integer 1 to 5 (nullable) |
| **First Response Time** | `tickets` | `first_response_at TIMESTAMPTZ` | Timestamp: `created_at + timedelta(minutes=first_response_mins)` |
| **Time to Resolution** | `tickets` | `resolved_at TIMESTAMPTZ` | Timestamp: `created_at + timedelta(minutes=resolution_mins)` |
| **Customer Name** | `customers` | `full_name VARCHAR(255)` | Customer account profile |
| **Customer Email** | `customers` | `email VARCHAR(255)` | Customer account profile |
| **Customer Age** | `customers` | `age INTEGER` | Nullable demographic field / `metadata JSONB` |
| **Customer Gender** | `customers` | `gender VARCHAR(32)` | Nullable demographic field / `metadata JSONB` |
| **Product Purchased** | `invoices` & `tickets` | `product_name VARCHAR(255)` | Billed product / ticket context |
| **Date of Purchase** | `invoices` | `created_at TIMESTAMPTZ` | Invoice transaction timestamp |

---

## 8. Cross-Tenant Security & Negative Test Matrix

To guarantee tenant isolation and RBAC before Week 3 integration, the test suite verifies:

| Test Case | Actor | Action | Expected Result |
|---|---|---|---|
| **Cross-Tenant Ticket Access** | Alice (Org A) | `GET /tickets/{dave_ticket_id}` | `404 NOT_FOUND` |
| **Cross-Tenant KB Query** | Dave (Org B) | `retrieve_kb(query)` | Returns Org B docs only (Org A = 0) |
| **Staff Privilege Escalation** | Bob (Agent) | `issue_refund(...)` | `403 FORBIDDEN` |
| **Customer Reading Notes** | Charlie (Customer) | `GET /tickets/{id}/notes` | `403 FORBIDDEN` |
| **Customer Closing Other's Ticket** | Charlie | `update_ticket_status(other_id, "closed")` | `404 NOT_FOUND` |
| **Customer Reopening Ticket** | Charlie | `update_ticket_status(own_id, "in_progress")` | `403 FORBIDDEN` |
| **Unapproved Refund > $100** | Alice (Admin) | `POST /invoices/{id}/refund` (no approval) | `403 FORBIDDEN` |
| **Tampered / Replayed Approval** | Alice (Admin) | Reusing approval token on different invoice | `403 FORBIDDEN` |
