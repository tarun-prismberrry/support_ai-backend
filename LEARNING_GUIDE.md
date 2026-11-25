# Learning Guide & Pedagogical Log: Tarun Saini

---

## 🎯 Mentorship Principles & Teaching Rules

1. **Role Definition:** Senior Backend Engineer, Software Architect & Personal Mentor.
2. **Core Mandate:** Tarun's deep architectural learning is more important than raw task completion speed.
3. **Strict Response Structure (Section 10 Format):**
   Every implementation turn MUST follow:
   * `### Current Objective`
   * `### Why Are We Doing This?`
   * `### Concept`
   * `### Your Task`
   * `### Expected Result`
   * `### Stop Here`
4. **Autonomous Execution Rules (Never Violate):**
   * **NEVER** run `git add`, `git commit`, or `git push` autonomously. Tarun must run all Git commands in his terminal.
   * **NEVER** generate whole directories or multiple files silently behind Tarun's back.
   * Proceed **one step at a time**. Tarun writes the code, verifies execution, and commits.
   * Use the project's actual source code for examples, never abstract textbook snippets.
   * Be direct, honest, and technically rigorous. Never sugarcoat potential production flaws or assume unverified behavior.

---

## 🧠 Concepts Explained & Mastery Level

| Concept | Project Context | Mastery / Status |
|---|---|---|
| **12-Factor App Configuration** | `app/core/config.py` using Pydantic Settings and `@lru_cache`. | **Mastered.** Understands separating config from code, environment validation, and fail-fast startup behavior. |
| **Asyncpg & Connection Pooling** | `app/core/database.py` with SQLAlchemy 2.0 async engine. | **Mastered.** Understands async non-blocking I/O and connection lifecycle. |
| **PostgreSQL Row-Level Security (RLS)** | `set_db_tenant_context()` running `SET LOCAL app.current_org_id = :org_id`. | **Mastered.** Understood why transaction-scoping (`is_local=true`) is essential to prevent state bleed across pooled connections. |
| **Lean JWT vs. Fat JWT** | `app/core/security.py` carrying only `sub` and `user_id`. | **Mastered.** Understood why baking permissions into tokens prevents instant revocation and why resolving permissions live via `GET /auth/me` is superior. |
| **SQLAlchemy 2.0 Declarative Mappings** | `Mapped[]`, `mapped_column()`, mixins (`UUIDPrimaryKeyMixin`, `TimestampMixin`). | **Mastered.** Grasped type annotations, server-side defaults (`func.now()`), and foreign key cascades. |
| **Relationship Mapping (`back_populates` vs `cascade`)** | `relationship()` bidirectional bindings across models. | **Mastered after deep-dive.** Understood that relationships are Python-level abstractions, whereas Foreign Keys are database-level constraints. |
| **Floating Point vs. Fixed-Point Numeric** | `Numeric(10, 2)` mapped to Python's `Decimal` in `Invoice`. | **Mastered.** Understood why `float` causes fractional penny bugs and audit failures in billing systems. |
| **Immutable Event Streams (WORM)** | `AuditLog` omitting `TimestampMixin` and using `ondelete="SET NULL"`. | **Mastered.** Understood write-once audit compliance requirements. |
| **Vector Embeddings & RAG Chunking** | `KnowledgeBaseArticle` with `Vector(1536)` and `Index("idx_kb_lookup")`. | **Mastered after explanation.** Understood why 1536 dimensions depends on the model (OpenAI `text-embedding-3-small`), why documents are chunked (`document_id` + `chunk_index`), and how composite indexing prunes candidate rows before vector math. |
| **Pydantic Snapshot vs. ORM Model (`UserContext`)** | `UserContext(BaseModel)` in `app/core/dependencies.py`. | **Mastered.** Understood why we never pass raw SQLAlchemy `User` models into routes (prevents leaking `hashed_password` and prevents `DetachedInstanceError`). |
| **FastAPI Dependency Factory (Closures)** | `require_permission(permission: str)` returning `permission_checker`. | **Mastered after explanation.** Understood how an outer function acts as a "factory" at startup to create a customized inner security guard executed by FastAPI on every request. |
| **Decoupled Dynamic RBAC & Tier Resolution** | `resolve_kb_tiers()` translating permissions into SQL filter values. | **Mastered.** Understood why Enums are too rigid for dynamic roles and how `resolve_kb_tiers()` safely handles the admin wildcard (`*`). |
| **Microservice Database Isolation** | Shared Postgres instance using separate schemas (`public` vs `orchestrator`). | **Mastered.** Guided Shashank on how to isolate LangGraph checkpointer tables without causing Alembic migration collisions. |

---

## 🔍 Areas to Revisit / Reinforce in Upcoming Steps

1. **Alembic Async Migrations:**
   * Watch out for how `migrations/env.py` handles async connections (`run_sync`) and how `target_metadata = Base.metadata` generates DDL.
2. **FastAPI Lifespan Events:**
   * Understanding how `@asynccontextmanager` manages database pool startup and graceful shutdown.
3. **Database Transactions & Idempotency in HITL Refunds:**
   * Reinforce how `idempotency_key` and single-use HMAC tokens prevent double-spending in financial transactions.
