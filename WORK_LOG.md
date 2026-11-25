# Work Log: Multi-Tenant B2B Customer Support AI Backend

---

## 📌 Latest Status (2026-11-25)
* **Active Git Branch:** `main` (tracked with `origin/main`).
* **Latest Git Commit:** `f3400ba` (`docs: added service architecture and setup documentation`).
* **Completed Milestones:**
  1. Relational schema design & contracts locked (v3.0).
  2. Core async database engine, config, and security modules (`app/core/`).
  3. Complete 10-table SQLAlchemy 2.0 models package (`app/models/`).
  4. FastAPI authentication dependency pipeline & RBAC factories (`app/core/dependencies.py`).
  5. Multi-service schema isolation agreement with LangGraph Orchestrator (`public` vs `orchestrator`).
* **Current Immediate Task:** Commit `app/core/dependencies.py`, then initialize Alembic async migrations.

---

## 📅 Session Log: 2026-11-24 & 2026-11-25

### Objective 1: Implement Financial, Audit, and Vector Models
* **Files Created:**
  * `app/models/billing.py` (`Invoice` with `Numeric(10, 2)` and refund tracking).
  * `app/models/audit.py` (`AuditLog` WORM immutable event stream without `updated_at`).
  * `app/models/rag.py` (`KnowledgeBaseArticle` with `Vector(1536)` and `idx_kb_lookup`).
  * `app/models/__init__.py` (Unified models exporter with `__all__`).
* **Tests & Verification:**
  * Imported all 10 models and executed `configure_mappers()`.
  * Verified all 10 tables registered in `Base.metadata.tables`:
    `audit_logs`, `customers`, `invoices`, `knowledge_base_articles`, `organizations`, `roles`, `ticket_messages`, `ticket_notes`, `tickets`, `users`.
* **Git Commit:** `a9a23ad feat(models): define complete 10-table SQLAlchemy 2.0 relational schema`.

---

### Objective 2: Service Architecture Documentation
* **Files Created:**
  * `README.md` (Production-grade overview, quickstart, directory layout, multi-tenant security matrix).
* **Git Commit:** `f3400ba docs: added service architecture and setup documentation`.

---

### Objective 3: FastAPI Authentication & Dynamic RBAC Pipeline
* **Files Created:**
  * `app/core/dependencies.py`
* **Implementation Details:**
  * `UserContext(BaseModel)`: Pure Pydantic data container holding resolved identity snapshot (`id`, `org_id`, `role`, `permissions`, `authorized_kb_tiers`). Prevents leaking `hashed_password` or causing `DetachedInstanceError`.
  * `get_current_user`: Defense-in-depth security gate evaluating 7 sequential checks:
    1. HTTP Bearer presence.
    2. JWT cryptographic decode (pinned `HS256`, expiration, audience).
    3. User ID claim extraction.
    4. UUID format validation.
    5. Database user lookup (with `selectinload(User.role)` and `selectinload(User.customer)`).
    6. `is_active == True` instant revocation check.
    7. Role assignment verification.
    8. Sets PostgreSQL RLS tenant context via `set_db_tenant_context()`.
  * `require_permission(permission: str)`: Higher-order dependency factory returning a customized closure function that enforces permissions before route handler execution.
  * `resolve_kb_tiers(permissions)`: Maps user permissions to RAG access tiers (`public`, `internal_staff`, `admin_only`), properly expanding admin wildcard `*`.
* **Tests & Verification:**
  * Tested wildcard `*` resolving to all 3 tiers.
  * Tested agent permissions resolving to `['public', 'internal_staff']`.
  * Tested customer permissions resolving to `['public']`.
  * Tested simulated request authorization against `require_permission('refund.issue')`.
  * All tests passed with 0 errors.

---

### Objective 4: Cross-Service Database Alignment (LangGraph Integration)
* **Discussion with Shashank Pathania (Orchestrator Engineer):**
  * Shashank requested clarification on checkpoint and state persistence.
  * **Agreed Decision:** Single PostgreSQL 16 container (`support_ai_db`).
  * Backend owns `public` schema for 10 core tables.
  * Orchestrator owns `orchestrator` schema for LangGraph `checkpoints`.
  * Backend's Alembic explicitly sets `version_table_schema = "public"` to guarantee isolation.

---

## 🐛 Resolved Bugs & Historical Issues

1. **`fatal: not a git repository`:** Fixed by running `git init` and creating `main` branch.
2. **`ModuleNotFoundError: No module named 'greenlet'`:** Async SQLAlchemy requires greenlet. Fixed by adding `sqlalchemy[asyncio]>=2.0.28` and installing via `uv pip install -e ".[dev]"`.
3. **Execution Environment:** Commands run outside `.venv` failed. Standardized execution via `.venv/bin/python`.

---

## 🎯 Exact Next Steps

1. **Commit Dependencies Module:**
   ```bash
   git add app/core/dependencies.py README.md
   git commit -m "feat(auth): implement FastAPI authentication dependencies and RBAC permission guards"
   ```
2. **Initialize Alembic Migrations:**
   * Run `.venv/bin/alembic init -t async migrations`.
   * Configure `migrations/env.py` to import `Base.metadata`, use sync connection URL, and set `version_table_schema = "public"`.
   * Generate initial revision: `.venv/bin/alembic revision --autogenerate -m "initial_schema"`.
3. **Build Application Entrypoint (`app/main.py`):**
   * Setup FastAPI factory with lifespan management and global standard error envelope formatting.
4. **Implement Health & Auth API Endpoints:**
   * `/health/live`, `/health/ready` (checking DB pool & Redis).
   * `/auth/login`, `/auth/me` (returning `UserContext`).
