# Project Context: Multi-Tenant B2B Customer Support AI Backend

---

## 1. System Overview & Multi-Service Architecture

We are building a production-grade, multi-tenant B2B Customer Support AI backend. The project is split into four independently developed microservices repositories:

1. **Backend & Database (This Repository - Tarun Saini):**
   * **Workspace:** `/home/tarun/Desktop/agentic-backend`
   * **Domain:** Core relational database schema (10 tables), multi-tenant Row-Level Security (RLS), dynamic RBAC, Lean JWT authentication, REST APIs, and team integration gateway.
2. **MCP Tools Service (Pulkit Singla):**
   * **Repo:** `cp-mcp_service`
   * **Domain:** Standardized Model Context Protocol (MCP) tool gateway exposing the 6 canonical support tools to the AI agent.
3. **RAG Knowledge Base (Akshit Chandel):**
   * **Repo:** `cp-rag_service`
   * **Domain:** Document ingestion, chunking, OpenAI vector embedding generation, and semantic document retrieval via `retrieve_kb`.
4. **LangGraph Agent Orchestrator (Shashank Pathania):**
   * **Repo:** `cp-agent_orchestrator`
   * **Domain:** Multi-agent state graph, HITL refund escalation interrupts (> $100), conversation checkpointer, and user identity resolution via `GET /auth/me`.

---

## 2. Database Strategy & Cross-Service Boundaries

### Shared PostgreSQL 16 Instance with Schema Isolation
All four services run against a single shared PostgreSQL 16 database instance (`support_ai_db`) running on port 5432 with the `pgvector` extension:

* **Schema `public` (Owned by Backend):**
  * Contains the 10 business domain tables.
  * Solely managed, migrated, and maintained by Tarun using Alembic (`version_table_schema = "public"`).
* **Schema `orchestrator` (Owned by LangGraph Orchestrator):**
  * Contains LangGraph checkpointer tables (`checkpoints`, `checkpoint_blobs`, `checkpoint_writes`), session memory, and SSE event replay buffers.
  * Managed independently by Shashank using `langgraph-checkpoint-postgres`.
  * Alembic in Backend strictly ignores this schema, guaranteeing zero migration conflicts.

### Strict Zero Direct Cross-Database SQL
* LangGraph Orchestrator and MCP Tools **never run direct SQL** against Backend's `public` tables.
* All interactions with tickets, customers, invoices, and roles happen through authenticated REST API calls and MCP tools.
* **Why:** Calling APIs ensures that Lean JWT authentication, PostgreSQL Row-Level Security (`SET LOCAL app.current_org_id`), and compliance `audit_logs` are strictly enforced.

---

## 3. Relational Database Schema (10 Core Tables)

All models inherit from `app.core.database.Base(DeclarativeBase)`:

1. **`organizations`** (`app/models/tenant.py`):
   * Root tenant entity (`id UUID PK`, `name VARCHAR(255)`, `slug VARCHAR(64) UK`, timestamps).
2. **`roles`** (`app/models/tenant.py`):
   * Dynamic RBAC roles (`id UUID PK`, `org_id UUID FK`, `name VARCHAR(64)`, `is_system BOOLEAN`, `permissions JSONB`, timestamps).
   * Unique constraint: `uq_org_role_name (org_id, name)`.
3. **`users`** (`app/models/user.py`):
   * Credentials & system access (`id UUID PK`, `org_id UUID FK`, `role_id UUID FK`, `email VARCHAR(255)`, `hashed_password VARCHAR(255)`, `full_name VARCHAR(255)`, `is_active BOOLEAN`, timestamps).
4. **`customers`** (`app/models/user.py`):
   * Customer account profile (`id UUID PK`, `org_id UUID FK`, `user_id UUID FK (1:1 nullable)`, `full_name VARCHAR(255)`, `email VARCHAR(255)`, `phone VARCHAR(32)`, `metadata_ JSONB`, timestamps).
5. **`tickets`** (`app/models/ticket.py`):
   * Support ticket lifecycle (`id UUID PK`, `org_id UUID FK`, `customer_id UUID FK`, `assigned_to_user_id UUID FK (nullable)`, `title VARCHAR(255)`, `description TEXT`, `status VARCHAR(32)`, `priority VARCHAR(32)`, `category VARCHAR(64)`, `channel VARCHAR(32)`, `product_name VARCHAR(255)`, `csat_rating INTEGER`, timestamps).
6. **`ticket_messages`** (`app/models/ticket.py`):
   * Public dialogue history (`id UUID PK`, `ticket_id UUID FK`, `sender_type VARCHAR(32)`, `sender_id UUID (nullable)`, `body TEXT`, `created_at TIMESTAMPTZ`).
7. **`ticket_notes`** (`app/models/ticket.py`):
   * Private internal whispers for staff only (`id UUID PK`, `org_id UUID FK`, `ticket_id UUID FK`, `author_id UUID FK`, `note TEXT`, `created_at TIMESTAMPTZ`).
8. **`invoices`** (`app/models/billing.py`):
   * Financial transactions & refunds (`id UUID PK`, `org_id UUID FK`, `customer_id UUID FK`, `ticket_id UUID FK (nullable)`, `product_name VARCHAR(255)`, `amount NUMERIC(10, 2)`, `currency VARCHAR(3)`, `status VARCHAR(32)`, `refunded_amount NUMERIC(10, 2)`, timestamps).
9. **`audit_logs`** (`app/models/audit.py`):
   * Immutable compliance events (`id UUID PK`, `org_id UUID FK`, `actor_id UUID FK (nullable)`, `action VARCHAR(64)`, `resource_type VARCHAR(64)`, `resource_id UUID (nullable)`, `details JSONB`, `created_at TIMESTAMPTZ`).
10. **`knowledge_base_articles`** (`app/models/rag.py`):
    * Chunked vector store (`id UUID PK`, `org_id UUID FK`, `document_id UUID`, `chunk_index INTEGER`, `title VARCHAR(255)`, `content TEXT`, `access_level VARCHAR(32)`, `embedding VECTOR(1536)`, `created_at TIMESTAMPTZ`).
    * Composite index: `idx_kb_lookup (org_id, access_level)`.

---

## 4. Key Architectural Decisions (ADRs)

1. **Shared DB + Shared Schema with PostgreSQL RLS:**
   Rows are tagged with `org_id`. On every request, `set_db_tenant_context()` runs `SET LOCAL app.current_org_id = :org_id`. The transaction-scoped parameter prevents connection pool state bleed.
2. **Lean JWT Token Design:**
   Token payload contains only `sub` and `user_id`. Dynamic permissions are resolved on every request from PostgreSQL (or Redis cache). Enables instant account suspension (`is_active = FALSE` returns `401`).
3. **Decoupled RAG Access Tiers:**
   Documents are tagged with fixed categorical tiers (`public`, `internal_staff`, `admin_only`). User permissions (`kb.read:public`, etc.) map dynamically to these tiers via `resolve_kb_tiers()`, preventing vector re-indexing when custom roles change.
4. **Fixed-Point Financial Precision:**
   `NUMERIC(10, 2)` mapped to Python's `Decimal` avoids binary floating-point rounding errors.
5. **HITL Refund Security:**
   Refunds > $100 require a 15-minute signed HMAC token (`POST /invoices/{id}/approve-refund`) before `issue_refund` can execute.
