# Work Log: Multi-Tenant B2B Customer Support AI Backend

---

## 📌 Latest Status (2026-11-25)
* **Active Git Branch:** `main` (tracked with `origin/main`).
* **Latest Git Commit:** `684e506` (`chore: untrack LEARNING_GUIDE.md and add to .gitignore`).
* **Completed Milestones:**
  1. Relational schema design & contracts locked (v3.0).
  2. Core async database engine, config, and security modules (`app/core/`).
  3. Complete 10-table SQLAlchemy 2.0 models package (`app/models/`).
  4. FastAPI authentication dependency pipeline & RBAC factories (`app/core/dependencies.py`).
  5. Multi-service schema isolation agreement with LangGraph Orchestrator (`public` vs `orchestrator`).
  6. Docker infrastructure setup (`docker-compose.yml`, `docker/init-db.sh` with `pgvector/pgvector:pg16` & `redis:7-alpine`).
  7. Alembic async migrations initialized, generated, and applied (`11 tables live in PostgreSQL`).
* **Current Immediate Task:** Commit migrations & Docker infrastructure, then implement the Synthetic Data Seeder (`app/scripts/seed.py`).

---

## 📅 Session Log: 2026-11-25

### Objective: Docker Infrastructure & Initial Database Migration
* **Files Created:**
  * `docker-compose.yml`: Spins up `pgvector/pgvector:pg16` on `5432` and `redis:7-alpine` on `6379`.
  * `docker/init-db.sh`: Automates extension creation (`uuid-ossp`, `vector`), initializes the `orchestrator` schema, and creates the restricted `orchestrator_user` role.
  * `alembic.ini` & `migrations/env.py`: Configured async migration runner dynamically linked to `app.core.config.get_settings().DATABASE_URL`.
  * `migrations/versions/a60f22bfa6a3_initial_schema_10_tables.py`: Initial DDL migration script covering all 10 business domain tables.
* **Bugs Encountered & Resolved:**
  1. *Alembic autogenerate quirk with `alembic_version`:* When autogenerate ran, it detected existing `alembic_version` and generated `op.drop_table('alembic_version')` inside `upgrade()`, which caused the migration to drop its own tracking table before recording the revision. Removed the redundant drop/create commands from the revision file.
  2. *Missing `pgvector` import in revision script:* Alembic referenced `pgvector.sqlalchemy.vector.VECTOR` on column `embedding` without importing `pgvector.sqlalchemy.vector` at the top of the file. Added the import to the migration header.
* **Tests & Verification:**
  * Ran `docker compose up -d` $\rightarrow$ both containers healthy.
  * Ran `.venv/bin/alembic upgrade head` $\rightarrow$ applied `a60f22bfa6a3_initial_schema_10_tables` cleanly.
  * Inspected PostgreSQL `support_ai_db` tables:
    Verified all 11 tables live: `alembic_version`, `audit_logs`, `customers`, `invoices`, `knowledge_base_articles`, `organizations`, `roles`, `ticket_messages`, `ticket_notes`, `tickets`, `users`.
  * Verified extensions: `uuid-ossp`, `vector`.
  * Verified schemas: `public`, `orchestrator`.

---

## 🎯 Exact Next Steps

1. **Commit Migrations and Docker Infrastructure:**
   ```bash
   git add docker-compose.yml docker/ alembic.ini migrations/ WORK_LOG.md PROJECT_CONTEXT.md
   git commit -m "feat(db): launch Docker infrastructure and apply initial 10-table Alembic migration"
   ```
2. **Implement Synthetic Data Seeder (`app/scripts/seed.py`):**
   * Populate deterministic test identities:
     - Alice (Org A Admin)
     - Bob (Org A Support Agent)
     - Charlie (Org A Customer)
     - Dave (Org B Admin - cross-tenant testing)
   * Seed 1,000+ support tickets, dialogue messages, private notes, and invoices.
   * Seed mock knowledge base vectors for RAG search.
3. **Implement FastAPI App Factory & Routes (`app/main.py`, `app/api/`):**
   * Liveness/readiness probes (`GET /health/live`, `GET /health/ready`).
   * Authentication (`POST /auth/login`, `GET /auth/me`).
   * Tickets, Notes, and Invoices CRUD.
