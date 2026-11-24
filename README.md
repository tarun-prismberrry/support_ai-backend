# 🛡️ Agentic Support Backend & Database

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%20(Async)-red.svg)](https://www.sqlalchemy.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Architecture](https://img.shields.io/badge/Multi--Tenancy-Shared%20DB%20%2B%20RLS-orange.svg)]()

Production-grade, multi-tenant B2B Customer Support AI backend service. Provides core relational persistence, PostgreSQL Row-Level Security (RLS), dynamic Role-Based Access Control (RBAC), and high-performance async APIs for MCP Tools, RAG Knowledge Retrieval, and LangGraph Agent Orchestration.

---

## 📌 Architectural Highlights

* **Multi-Tenant Data Isolation:** Shared Database + Shared Schema pattern backed by native PostgreSQL **Row-Level Security (RLS)** (`SET LOCAL app.current_org_id = ...`) to guarantee zero cross-tenant data leaks.
* **Dynamic RBAC & Lean JWTs:** Stateless tokens carrying only identity claims (`sub`, `user_id`). Permissions are stored in dynamic JSONB roles and cached in Redis with instant zero-lag revocation.
* **HITL Financial Safety:** Defense-in-depth refund execution requiring signed HMAC approval tokens for amounts $> \$100.00$.
* **Integrated Vector Storage:** Native 1536-dimensional embeddings stored via `pgvector` for semantic knowledge base retrieval.
* **Asynchronous High Concurrency:** Built with modern Python `asyncio`, `asyncpg`, and SQLAlchemy 2.0 type-annotated Declarative Mappings.

---

## 📂 Project Structure

```text
agentic-backend/
├── app/
│   ├── api/                  # API router controllers
│   │   └── v1/               # Version 1 REST endpoints
│   ├── core/                 # Core engine infrastructure
│   │   ├── config.py         # 12-Factor Pydantic settings & validation
│   │   ├── database.py       # Async SQLAlchemy engine & session factory
│   │   ├── dependencies.py   # FastAPI auth & tenant context injection
│   │   └── security.py       # bcrypt hashing & Lean JWT encode/decode
│   ├── models/               # SQLAlchemy 2.0 Relational Models (10 tables)
│   │   ├── audit.py          # WORM immutable audit logs
│   │   ├── base.py           # UUID primary key & timestamp mixins
│   │   ├── billing.py        # Invoices & financial refund tracking
│   │   ├── rag.py            # Knowledge base articles & 1536-dim vectors
│   │   ├── tenant.py         # Organizations & dynamic RBAC Roles
│   │   ├── ticket.py         # Tickets, public dialogue & staff whispers
│   │   └── user.py           # User credentials & customer profiles
│   ├── schemas/              # Pydantic v2 request/response schemas
│   └── main.py               # Application factory & lifespan handlers
├── docs/                     # Architecture & Integration Contracts
│   ├── CONTRACTS.md          # Multi-service locked contracts (v3.0)
│   ├── er_diagram.md         # Mermaid interactive relational ER diagram
│   └── er_diagram.svg        # Vector graphic schema visualizer
├── .env.example              # 12-Factor environment configuration template
├── pyproject.toml            # Hatchling build & dependency manifest
└── README.md                 # Primary service documentation
```

---

## 🚀 Quickstart Guide

### 1. Prerequisites
* Python 3.10+ (or Python 3.12)
* PostgreSQL 16+ with `pgvector` extension enabled
* `uv` or `pip` package manager

### 2. Environment Setup
```bash
# Clone the repository
git clone https://github.com/<your-org>/agentic-backend.git
cd agentic-backend

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies in editable mode
pip install -e ".[dev]"

# Configure local environment variables
cp .env.example .env
```

### 3. Database Initialization & Migrations
```bash
# Run database migrations
alembic upgrade head

# Seed synthetic test data (Orgs, Users, Invoices, Kaggle Tickets)
python -m app.scripts.seed
```

### 4. Running the Development Server
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
* **Swagger UI Documentation:** `http://localhost:8000/docs`
* **Liveness Probe:** `http://localhost:8000/health/live`
* **Readiness Probe:** `http://localhost:8000/health/ready`

---

## 🔐 Multi-Tenant Security & Identity Model

### Fixed Test Identities (Development & Testing)
| Persona | User ID (UUID) | Tenant (`org_id`) | Role | Purpose |
|---|---|---|---|---|
| **Alice** | `a0000000-0000-0000-0000-000000000001` | Org A (`11111111-...`) | `Org_Admin` | High-privilege admin, refund approver |
| **Bob** | `a0000000-0000-0000-0000-000000000002` | Org A (`11111111-...`) | `Support_Agent` | Front-line agent, ticket & note writer |
| **Charlie** | `a0000000-0000-0000-0000-000000000003` | Org A (`11111111-...`) | `End_Customer` | Ticket creator, public dialogue reader |
| **Dave** | `b0000000-0000-0000-0000-000000000004` | Org B (`22222222-...`) | `Org_Admin` | Cross-tenant negative isolation test target |

For full cryptographic token specifications and permission mappings, refer to [docs/CONTRACTS.md](docs/CONTRACTS.md).

---

## 📊 Relational Database Schema (10 Tables)

The database schema is organized into 5 relational domains:
1. **Multi-Tenancy & RBAC:** `organizations`, `roles`
2. **Identity & CRM:** `users`, `customers`
3. **Support Operations:** `tickets`, `ticket_messages`, `ticket_notes`
4. **Billing & Compliance:** `invoices`, `audit_logs`
5. **AI Knowledge Base:** `knowledge_base_articles` (with `VECTOR(1536)`)

View the visual schema in [docs/er_diagram.svg](docs/er_diagram.svg) or inspect the Mermaid source in [docs/er_diagram.md](docs/er_diagram.md).

---

## 🧪 Testing

Execute the comprehensive test suite verifying tenant isolation, RBAC denial rules, and HITL refund checks:

```bash
pytest -v
```

---

## 📜 Team Contracts & Microservice Interfaces

This backend service acts as the source of truth for three integrating microservices:
* **MCP Tools Service (Pulkit Singla):** Tool definitions, input/output schemas, and permission guards.
* **RAG Knowledge Base (Akshit Chandel):** Metadata-filtered chunk retrieval via `retrieve_kb`.
* **LangGraph Orchestrator (Shashank Pathania):** HITL refund approval workflows and identity context resolution (`GET /auth/me`).

Detailed integration contracts are strictly documented in **[docs/CONTRACTS.md](docs/CONTRACTS.md)**.