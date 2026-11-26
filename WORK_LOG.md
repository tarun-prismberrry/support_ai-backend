# Work Log: Multi-Tenant B2B Customer Support AI Backend

---

## 📌 Latest Status (2026-11-26)
* **Active Git Branch:** `main` (tracked with `origin/main`).
* **Latest Git Commit:** `03dca60` (`feat(auth): implement redis user session cache-aside pattern with 300s ttl and instant invalidation`).
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
  10. Invoices & HITL refund workflow (`/invoices`, `/invoices/{id}`, `/invoices/{id}/approve-refund`, `/invoices/{id}/refund`).
  11. Seed Upgrade & Runtime Bug Fixes (`app/scripts/seed.py`, `app/schemas/ticket.py`, `app/core/dependencies.py`, `app/api/v1/tickets.py`).
  12. Redis User Session Cache (Cache-Aside Pattern in `app/core/dependencies.py`, `app/core/config.py`).
  13. Automated Pytest Integration Test Suite (`tests/conftest.py`, `tests/test_health.py`, `tests/test_auth.py`, `tests/test_tickets.py`, `tests/test_notes.py`, `tests/test_invoices.py`).
  14. PostgreSQL Row-Level Security (RLS) DDL Migration (`migrations/versions/b71e33cfa5d2_enable_rls_tenant_policies.py`) & Verification Suite (`tests/test_rls.py`).
* **Current Immediate Task:** Apply Alembic migration `b71e33cfa5d2`, run full pytest suite (including 4 new RLS tests = 24 tests total), and commit.

---

## 📅 Session Log: 2026-11-26

### Objective: Automated Pytest Integration Test Suite (`tests/`)
* **Test Architecture & Scope:**
  * `tests/conftest.py`: Async HTTP client (`AsyncClient` with `ASGITransport`), session-scoped event loop, Redis flush fixture, and deterministic persona headers (`alice_headers`, `bob_headers`, `charlie_headers`, `dave_headers`, `eve_headers`).
  * `tests/test_health.py`: Liveness (`/health/live`) and readiness (`/health/ready`) probes verifying PostgreSQL + Redis connectivity.
  * `tests/test_auth.py`: Login success, 401 on bad credentials, `/auth/me` persona resolution, and Redis user session cache-aside lifecycle (miss, hit, 300s TTL, and instant invalidation).
  * `tests/test_tickets.py`: Customer sees own tickets, agent sees org tickets, cross-tenant isolation (404 on cross-org ticket), ticket creation, state machine transitions (`open` -> `in_progress`), and dialogue history.
  * `tests/test_notes.py`: Internal staff whispers (agents read/write, customers strictly 403 Forbidden).
  * `tests/test_invoices.py`: Invoices listing, cross-tenant invoice isolation, HITL refund requirement (> $100 requires HMAC approval token), end-to-end HITL approval and refund execution, and single-use idempotency replay.
* **Verification:**
  * **20 / 20 tests passing 100% green** in under 1 second.

### Objective: Bug Fixes & Industry-Grade Synthetic Seed Upgrade
* **All 6 Codebase Review Issues Resolved:**
  1. `app/schemas/ticket.py` (BUG 1): Deleted duplicate `TicketCreate` declaration; merged `channel` and `customer_id` into a single schema.
  2. `app/core/dependencies.py` (BUG 2): Added explicit `user_id: uuid.UUID` to `UserContext` dataclass to fix runtime `AttributeError` in `invoices.py`.
  3. `app/api/v1/tickets.py` (BUG 3): Added missing `org_id=current_user.org_id` to `TicketMessage` constructor to satisfy `nullable=False` DB constraint.
  4. `app/core/database.py` (BUG 4): Added automatic `await session.commit()` in `get_db()` post-yield as an automatic safety net for all route transactions.
  5. `app/core/redis.py`, `app/api/v1/health.py`, `app/api/v1/invoices.py`, `app/main.py` (BUG 5): Created shared asynchronous Redis `ConnectionPool` singleton and graceful lifespan shutdown to eliminate connection churn.
  6. `app/__init__.py`, `app/core/__init__.py`, `app/api/__init__.py`, `app/api/v1/__init__.py`, `app/schemas/__init__.py`, `app/scripts/__init__.py` (BUG 6): Added package marker files for clean module discovery.
  * `app/scripts/seed.py`: Upgraded to enterprise cross-team testing standard:
    * **Eve** (`eeeeeee1-...` / `eeeeeee2-...`): Loginable Org B Customer with `Password123!`.
    * **Org B Invoices**: Seeded target $175 invoice for Eve + 15 additional invoices for Pulkit's MCP refund tests.
    * **Ticket-Invoice Linkage**: Charlie's $250 invoice explicitly linked via `ticket_id=charlie_ticket_id`.
    * **Multi-Turn Conversations**: 2–4 turn dialogues across realistic customer/agent exchanges.
    * **Multi-Chunk RAG Articles**: Refund SOP broken down into chunk 0, 1, 2 with distinct embeddings for Akshit's RAG ranker.
* **Deterministic Identities Seeded:**
  * Alice (`aaaaaaa1-...`): Org A Admin (`*` wildcard permission).
  * Bob (`bbbbbbb1-...`): Org A Support Agent (`ticket.*`, `ticket.note:*`, internal KB tiers).
  * Charlie (`ccccccc1-...` / Customer `ccccccc2-...`): Org A Customer with $250 refund test invoice.
  * Dave (`ddddddd2-...`): Org B Admin for cross-tenant isolation testing.
  * Eve (`eeeeeee1-...` / Customer `eeeeeee2-...`): Org B Customer for cross-tenant customer flow testing.

---

## 📅 Session 7 — Milestone 13 & 14: Pytest Test Suite & PostgreSQL Row-Level Security (RLS)

### ✅ What Got Done:
* **Milestone 13: 20 Pytest Domain Integration Tests** (`tests/`):
  * `test_health.py`: Liveness and readiness endpoints checking DB/Redis availability.
  * `test_auth.py`: JWT login, claims, `/auth/me` persona inspection, and Redis session cache-aside validation.
  * `test_tickets.py`: Tenant isolation, customer vs agent ticket access, state machine transitions, and multi-turn ticket dialogue history.
  * `test_notes.py`: Staff-only internal notes vs customer 403 boundary enforcement.
  * `test_invoices.py`: Cross-tenant invoice isolation, HITL refund escalation threshold ($100), and end-to-end refund workflow.
* **Milestone 14: PostgreSQL Kernel-Level Row-Level Security (RLS)**:
  * Synchronized RAG embedding vector dimension to **384** (`all-MiniLM-L6-v2`) across `CONTRACTS.md`, `app/models/rag.py`, initial migration, and `seed.py`.
  * Generated and applied Alembic migration `b71e33cfa5d2` (`enable_rls_tenant_policies`):
    * Enabled and forced RLS on 7 business tables (`customers`, `tickets`, `ticket_messages`, `ticket_notes`, `invoices`, `audit_logs`, `knowledge_base_articles`) and `roles`.
    * Defined `tenant_isolation_policy` binding queries to `current_setting('app.current_org_id', true)::uuid`.
    * Provisioned `app_user` with public schema table grants.
  * Created `tests/test_rls.py` verifying raw database-level query interception without application WHERE clauses:
    * Switching role to `app_user` to prove non-superuser RLS enforcement (as `postgres` superuser bypasses RLS by PostgreSQL design).
    * Validated Org A isolation (953 tickets), Org B isolation (101 tickets), unauthenticated zero-row return, and cross-tenant `WITH CHECK` insert rejection.
* **Full Test Suite Status**: 24/24 tests PASSED (100% green).

---

## 🎯 Exact Next Steps

1. **User Terminal: Commit Milestone 14:**
   ```bash
   git add docs/CONTRACTS.md docker/init-db.sh migrations/ versions/ tests/ WORK_LOG.md
   git commit -m "feat(db): enable postgresql row-level security policies with verified rls test suite"
   ```
2. **Milestone 15: Microservice Handoff Package & Production Containerization:**
   * Multi-stage production `Dockerfile` for FastAPI + Uvicorn.
   * Integration handoff docs and verification runbooks for Akshit (RAG), Pulkit (MCP), and Shashank (LangGraph).
