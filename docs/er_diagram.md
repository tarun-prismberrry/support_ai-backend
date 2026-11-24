# Multi-Tenant B2B Customer Support AI — Relational Database Schema (Dynamic RBAC)

This document contains the official Entity-Relationship diagram showing the 10 core tables, dynamic RBAC via the `ROLES` table, all fields (including Kaggle support mappings), and explicit foreign key relationships with cardinality.

## Interactive Mermaid Entity-Relationship Diagram

```mermaid
erDiagram
    ORGANIZATIONS ||--o{ ROLES : "defines roles"
    ORGANIZATIONS ||--o{ USERS : "has staff"
    ORGANIZATIONS ||--o{ CUSTOMERS : "has customers"
    ORGANIZATIONS ||--o{ TICKETS : "owns"
    ORGANIZATIONS ||--o{ TICKET_MESSAGES : "scopes"
    ORGANIZATIONS ||--o{ TICKET_NOTES : "scopes"
    ORGANIZATIONS ||--o{ INVOICES : "issues"
    ORGANIZATIONS ||--o{ AUDIT_LOGS : "records"
    ORGANIZATIONS ||--o{ KNOWLEDGE_BASE_ARTICLES : "owns KB"

    ROLES ||--o{ USERS : "assigned to"

    CUSTOMERS ||--o{ TICKETS : "submits"
    CUSTOMERS ||--o{ INVOICES : "billed to"

    USERS ||--o{ TICKETS : "assigned to"
    USERS ||--o{ TICKET_NOTES : "authors"
    USERS ||--o{ AUDIT_LOGS : "performs"

    TICKETS ||--o{ TICKET_MESSAGES : "contains conversation"
    TICKETS ||--o{ TICKET_NOTES : "contains private staff notes"
    TICKETS ||--o{ INVOICES : "associated refund or bill"

    ORGANIZATIONS {
        uuid id PK
        string name "Org A, Org B"
        string slug UK "org-a, org-b"
        timestamptz created_at
    }

    ROLES {
        uuid id PK
        uuid org_id FK "organizations.id"
        string name "super-admin, Org_Admin, Agent..."
        text description
        boolean is_system "protected default role"
        jsonb permissions "['*'] or action list"
        timestamptz created_at
        timestamptz updated_at
    }

    USERS {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid role_id FK "roles.id (dynamic role)"
        string email UK
        string hashed_password
        string full_name
        timestamptz created_at
        timestamptz updated_at
    }

    CUSTOMERS {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid user_id FK "users.id (nullable)"
        string full_name
        string email
        string phone
        int age "nullable (Kaggle)"
        string gender "nullable (Kaggle)"
        jsonb metadata "extensible attributes"
        timestamptz created_at
    }

    TICKETS {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid customer_id FK "customers.id"
        uuid assigned_agent_id FK "users.id (nullable)"
        string title "Ticket Subject"
        text description
        string status "open | in_progress | resolved | closed"
        string priority "low | medium | high | urgent"
        string category "billing | technical | general"
        string channel "chat | email | web | phone"
        string product_name "product context"
        text resolution "solution summary"
        int csat_rating "1-5 satisfaction rating"
        timestamptz first_response_at "live SLA metric"
        timestamptz resolved_at "live SLA metric"
        timestamptz created_at
        timestamptz updated_at
    }

    TICKET_MESSAGES {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid ticket_id FK "tickets.id"
        string sender_type "customer | support_agent | ai_agent | system"
        uuid sender_id FK "nullable for AI"
        text body "visible dialogue turn"
        timestamptz created_at
    }

    TICKET_NOTES {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid ticket_id FK "tickets.id"
        uuid author_id FK "users.id (staff)"
        text note "staff-only private whisper"
        timestamptz created_at
    }

    INVOICES {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid customer_id FK "customers.id"
        uuid ticket_id FK "tickets.id (nullable)"
        string product_name "Product Purchased"
        decimal amount "financial balance"
        string currency "USD"
        string status "paid | pending | refunded"
        decimal refunded_amount "default 0.00"
        timestamptz created_at "Date of Purchase"
        timestamptz updated_at
    }

    AUDIT_LOGS {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid actor_id FK "users.id"
        string action "ticket.create | role.create | role.edit"
        string resource_type "tickets | roles | invoices"
        uuid resource_id
        jsonb details "payload / changes"
        timestamptz created_at
    }

    KNOWLEDGE_BASE_ARTICLES {
        uuid id PK
        uuid org_id FK "organizations.id"
        uuid document_id "source document group"
        int chunk_index "0, 1, 2..."
        string title
        text content
        string access_level "public | internal_staff | admin_only"
        vector embedding "1536-dim vector for pgvector"
        timestamptz created_at
    }
```

## Vector Graphic Export

The visual vector graphic with direct entity-connector lines, cardinality indicators (`1:N`), and the new `ROLES` entity is available in [docs/er_diagram.svg](file:///home/tarun/Desktop/agentic-backend/docs/er_diagram.svg).
