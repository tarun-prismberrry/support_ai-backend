# Work Log: Multi-Tenant B2B Customer Support AI Backend

---

## 📌 Latest Status (2026-11-25)
* **Active Git Branch:** `main` (tracked with `origin/main`).
* **Latest Git Commit:** `200ad4d` (`feat(auth): implement /auth/login, /auth/me, and global contract error handling`).
* **Completed Milestones:**
  1. Relational schema design & contracts locked (v3.0).
  2. Core async database engine, config, and security modules (`app/core/`).
  3. Complete 10-table SQLAlchemy 2.0 models package (`app/models/`).
  4. FastAPI authentication dependency pipeline & RBAC factories (`app/core/dependencies.py`).
  5. Multi-service schema isolation agreement with LangGraph Orchestrator (`public` vs `orchestrator`).
  6. Docker infrastructure setup (`docker-compose.yml`, `docker/init-db.sh` with `pgvector/pgvector:pg16` & `redis:7-alpine`).
  7. Alembic async migrations initialized, generated, and applied (`11 tables live in PostgreSQL`).
  8. Health probes & auth routes (`/health/live`, `/health/ready`, `/auth/login`, `/auth/me`).
  9. Tickets & internal notes endpoints (`/tickets`, `/tickets/{id}/messages`, `/tickets/{id}/notes`, `/tickets/{id}/status`).
* **Current Immediate Task:** Verify and commit ticket routes, then implement Billing & HITL Refund routes (`app/schemas/billing.py`, `app/api/v1/invoices.py`).

---

## 📅 Session Log: 2026-11-25

### Objective: Support Tickets & Internal Notes Implementation
* **Files Created & Modified:**
  * `app/schemas/ticket.py`: Pydantic schemas for ticket creation, status update, response, dialogue messages, and notes.
  * `app/api/v1/tickets.py`: Full CRUD for tickets, public messages, and lifecycle state transitions.
  * `app/api/v1/notes.py`: Internal staff whispers route guarded strictly by `ticket.note:read` and `ticket.note:write`.
  * `app/main.py`: Registered tickets and notes routers into application factory.
* **Security & Multi-Tenant Validations:**
  * Auto-binding customer ID for customers on `POST /tickets`.
  * Status transition state machine validation (e.g. invalid jumps rejected with `400 BAD REQUEST`).
  * Customer status update restriction (customers can only move `resolved` $\rightarrow$ `closed`).
  * Strict customer denial on `/tickets/{id}/notes` (`ticket.note:read` requirement).
  * Global error envelope compliance (`{"error": {"code": "...", "message": "...", "details": ...}}`).

---

## 🎯 Exact Next Steps

1. **Commit Tickets & Notes Implementation:**
   ```bash
   git add app/schemas/ticket.py app/api/v1/tickets.py app/api/v1/notes.py app/main.py WORK_LOG.md
   git commit -m "feat(tickets): implement tickets, public messages, and internal notes routes with RBAC guards"
   ```
2. **Implement Billing & HITL Refund Routes (`app/schemas/billing.py`, `app/api/v1/invoices.py`):**
   * `GET /invoices`: Org-scoped invoice search and listing.
   * `GET /invoices/{id}`: Detailed invoice query.
   * `POST /invoices/{id}/approve-refund`: Admin pre-approval producing signed HMAC token (15-min expiry).
   * `POST /invoices/{id}/refund`: Execution endpoint enforcing idempotency key, balance check, threshold validation, and audit logging.
3. **Implement Synthetic Data Seeder (`app/scripts/seed.py`):**
   * Deterministic test users (Alice, Bob, Charlie, Dave).
   * 1,000+ support tickets, dialogue messages, notes, and invoices.
   * Vector embeddings for RAG articles.
4. **Pytest Integration Test Suite (`tests/`):**
   * Test cross-tenant negative matrix (CONTRACTS.md Section 8).
   * Test staff privilege escalation denial.
   * Test customer reading notes (`403 FORBIDDEN`).
   * Test unapproved refund > $100 (`403 FORBIDDEN`).
