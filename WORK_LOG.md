# Work Log: Multi-Tenant B2B Customer Support AI Backend

---

## 📌 Latest Status (2026-11-26)
* **Active Git Branch:** `main` (tracked with `origin/main`).
* **Latest Git Commit:** `a36b875` (`feat(billing): implement invoices and HITL refund workflow with HMAC verification and idempotency`).
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
* **Current Immediate Task:** Start Docker containers, run the upgraded seeder in PostgreSQL, inspect counts, and commit. Then proceed to the Pytest Integration Test Suite (`tests/`).

---

## 📅 Session Log: 2026-11-26

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

## 🎯 Exact Next Steps

1. **Start Docker Infrastructure (User Terminal):**
   ```bash
   docker compose up -d
   ```
2. **Execute Upgraded Seeder & Verify Live DB:**
   ```bash
   .venv/bin/python -m app.scripts.seed
   ```
3. **Commit Bug Fixes, Upgraded Seeder & Work Log:**
   ```bash
   git add app/core/dependencies.py app/schemas/ticket.py app/api/v1/tickets.py app/scripts/ app/__init__.py app/core/__init__.py app/api/__init__.py app/api/v1/__init__.py app/schemas/__init__.py WORK_LOG.md
   git commit -m "fix: resolve 3 runtime bugs, add package markers, and upgrade seed data for cross-team testing"
   ```
4. **Implement Pytest Integration Test Suite (`tests/`):**
   * Multi-tenant negative isolation matrix (CONTRACTS.md Section 8).
   * HITL refund token approval, tampering rejection, and single-use verification.
   * Customer vs staff RBAC boundary tests.
