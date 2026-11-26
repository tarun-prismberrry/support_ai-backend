"""
Synthetic Data Seeder for Multi-Tenant B2B Customer Support AI Backend.

Seeds deterministic identities (CONTRACTS.md Section 1), roles, customers,
1,000+ support tickets, multi-turn dialogue, internal staff notes,
invoices (with HITL refund targets), and multi-chunk vector-embedded KB articles.

Usage:
    .venv/bin/python -m app.scripts.seed
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import random
import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session_factory
from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.billing import Invoice
from app.models.rag import KnowledgeBaseArticle
from app.models.tenant import Organization, Role
from app.models.ticket import Ticket, TicketMessage, TicketNote
from app.models.user import Customer, User

# -----------------------------------------------------------------------------
# Fixed Deterministic Identifiers (CONTRACTS.md Section 1)
# -----------------------------------------------------------------------------
ORG_A_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
ORG_B_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

ALICE_USER_ID = uuid.UUID("aaaaaaa1-1111-1111-1111-111111111111")
BOB_USER_ID = uuid.UUID("bbbbbbb1-1111-1111-1111-111111111111")
CHARLIE_USER_ID = uuid.UUID("ccccccc1-1111-1111-1111-111111111111")
CHARLIE_CUSTOMER_ID = uuid.UUID("ccccccc2-2222-2222-2222-222222222222")

DAVE_USER_ID = uuid.UUID("ddddddd2-2222-2222-2222-222222222222")
DAVE_TICKET_ID = uuid.UUID("ddddddd3-3333-3333-3333-333333333333")

# Org B loginable customer for cross-tenant testing by teammates
EVE_USER_ID = uuid.UUID("eeeeeee1-1111-1111-1111-111111111111")
EVE_CUSTOMER_ID = uuid.UUID("eeeeeee2-2222-2222-2222-222222222222")

DEFAULT_PASSWORD = "Password123!"

# Realistic product & support domain data
PRODUCTS = [
    "Enterprise Cloud Suite",
    "API Gateway Pro",
    "AI Assistant Copilot",
    "Analytics Platform",
    "Database Cluster",
]
CATEGORIES = ["billing", "technical", "account", "product", "security"]
CHANNELS = ["web", "chat", "email", "phone"]
PRIORITIES = ["low", "medium", "high", "urgent"]
STATUSES = ["open", "in_progress", "resolved", "closed"]

# Multi-turn dialogue templates for realistic conversations
CUSTOMER_MESSAGES = [
    "I'm experiencing an issue with {product}. It started showing error code {code} since yesterday.",
    "I tried restarting and clearing cache but the problem persists. Can you please help?",
    "Thank you for looking into this. When can I expect a resolution?",
    "The issue is now resolved. Thanks for the quick turnaround!",
]
AGENT_MESSAGES = [
    "Thank you for reaching out. I'm looking into your {category} issue with {product} now.",
    "I've identified the root cause. This is related to a known issue we're tracking internally.",
    "I've applied the fix on our end. Could you please try again and confirm it's working?",
    "Glad to hear it's resolved! I'm closing this ticket. Please reach out if you need anything else.",
]
NOTE_TEMPLATES = [
    "Customer tier verified: {tier}. SLA response target: {sla_hours}h.",
    "Escalation candidate — recurring {category} issue. Check linked tickets.",
    "Verified against billing records. Eligible for credit if unresolved within SLA.",
    "Knowledge base article KB-{kb_id} referenced for resolution.",
]


def generate_mock_vector(seed_val: int, dim: int = 384) -> list[float]:
    """Generate a deterministic 384-dimensional normalized unit vector."""
    rng = random.Random(seed_val)
    raw = [rng.uniform(-1.0, 1.0) for _ in range(dim)]
    norm = sum(x * x for x in raw) ** 0.5 or 1.0
    return [round(x / norm, 6) for x in raw]


async def seed_database() -> None:
    """Populate database with complete deterministic test fixture."""
    print("🚀 Starting Synthetic Database Seeding...")
    rng = random.Random(42)  # Deterministic RNG — same data every run

    async with async_session_factory() as db:
        # ---------------------------------------------------------------------
        # 1. Cascading Purge (Idempotent — safe to re-run)
        # ---------------------------------------------------------------------
        print("🧹 Purging existing test organizations (cascade deletes all dependent data)...")
        await db.execute(
            delete(Organization).where(Organization.id.in_([ORG_A_ID, ORG_B_ID]))
        )
        await db.commit()

        # ---------------------------------------------------------------------
        # 2. Seed Organizations
        # ---------------------------------------------------------------------
        print("🏢 Seeding Organizations...")
        org_a = Organization(id=ORG_A_ID, name="Organization A", slug="org-a")
        org_b = Organization(id=ORG_B_ID, name="Organization B", slug="org-b")
        db.add_all([org_a, org_b])
        await db.flush()

        # ---------------------------------------------------------------------
        # 3. Seed Roles (CONTRACTS.md Section 4)
        # ---------------------------------------------------------------------
        print("🔑 Seeding Dynamic RBAC Roles...")

        admin_perms = ["*"]
        agent_perms = [
            "ticket.read:org", "ticket.write:org", "ticket.status:update",
            "ticket.note:read", "ticket.note:write",
            "kb.read:public", "kb.read:internal_staff",
        ]
        customer_perms = ["ticket.read:own", "ticket.write:own", "kb.read:public"]

        role_orga_admin = Role(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "role-orga-admin"),
            org_id=ORG_A_ID, name="Org_Admin",
            description="Full administrative privileges", is_system=True,
            permissions=admin_perms,
        )
        role_orga_agent = Role(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "role-orga-agent"),
            org_id=ORG_A_ID, name="Support_Agent",
            description="Ticket triage, notes, and internal KB access", is_system=True,
            permissions=agent_perms,
        )
        role_orga_customer = Role(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "role-orga-customer"),
            org_id=ORG_A_ID, name="End_Customer",
            description="Own tickets and public KB only", is_system=True,
            permissions=customer_perms,
        )
        role_orgb_admin = Role(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "role-orgb-admin"),
            org_id=ORG_B_ID, name="Org_Admin",
            description="Full administrative privileges", is_system=True,
            permissions=admin_perms,
        )
        role_orgb_agent = Role(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "role-orgb-agent"),
            org_id=ORG_B_ID, name="Support_Agent",
            description="Support agent for Organization B", is_system=True,
            permissions=agent_perms,
        )
        role_orgb_customer = Role(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, "role-orgb-customer"),
            org_id=ORG_B_ID, name="End_Customer",
            description="Own tickets and public KB only", is_system=True,
            permissions=customer_perms,
        )

        db.add_all([
            role_orga_admin, role_orga_agent, role_orga_customer,
            role_orgb_admin, role_orgb_agent, role_orgb_customer,
        ])
        await db.flush()

        # ---------------------------------------------------------------------
        # 4. Seed Deterministic Users (Alice, Bob, Charlie, Dave, Eve)
        # ---------------------------------------------------------------------
        print("👥 Seeding Users (Alice, Bob, Charlie, Dave, Eve)...")
        hashed_pw = hash_password(DEFAULT_PASSWORD)

        alice = User(
            id=ALICE_USER_ID, org_id=ORG_A_ID, role_id=role_orga_admin.id,
            email="alice@orga.com", full_name="Alice Admin",
            hashed_password=hashed_pw, is_active=True,
        )
        bob = User(
            id=BOB_USER_ID, org_id=ORG_A_ID, role_id=role_orga_agent.id,
            email="bob@orga.com", full_name="Bob Agent",
            hashed_password=hashed_pw, is_active=True,
        )
        charlie_user = User(
            id=CHARLIE_USER_ID, org_id=ORG_A_ID, role_id=role_orga_customer.id,
            email="charlie@customer.com", full_name="Charlie Customer",
            hashed_password=hashed_pw, is_active=True,
        )
        dave = User(
            id=DAVE_USER_ID, org_id=ORG_B_ID, role_id=role_orgb_admin.id,
            email="dave@orgb.com", full_name="Dave OrgB Admin",
            hashed_password=hashed_pw, is_active=True,
        )
        eve = User(
            id=EVE_USER_ID, org_id=ORG_B_ID, role_id=role_orgb_customer.id,
            email="eve@customer-b.com", full_name="Eve OrgB Customer",
            hashed_password=hashed_pw, is_active=True,
        )

        db.add_all([alice, bob, charlie_user, dave, eve])
        await db.flush()

        # ---------------------------------------------------------------------
        # 5. Seed Customer Profiles
        # ---------------------------------------------------------------------
        print("👤 Seeding Customer Profiles...")

        charlie_profile = Customer(
            id=CHARLIE_CUSTOMER_ID, org_id=ORG_A_ID, user_id=CHARLIE_USER_ID,
            full_name="Charlie Customer", email="charlie@customer.com",
            phone="+1-555-0199", age=34, gender="Non-binary",
            metadata_={"tier": "gold", "segment": "enterprise_smb"},
        )
        eve_profile = Customer(
            id=EVE_CUSTOMER_ID, org_id=ORG_B_ID, user_id=EVE_USER_ID,
            full_name="Eve OrgB Customer", email="eve@customer-b.com",
            phone="+1-555-0200", age=28, gender="Female",
            metadata_={"tier": "silver", "segment": "startup"},
        )
        db.add_all([charlie_profile, eve_profile])

        # 50 synthetic Org A customers
        orga_customers: list[Customer] = [charlie_profile]
        for c_idx in range(1, 51):
            c = Customer(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"orga-cust-{c_idx}"),
                org_id=ORG_A_ID, user_id=None,
                full_name=f"Customer A-{c_idx}",
                email=f"customer{c_idx}@clienta.com",
                phone=f"+1-555-{1000 + c_idx}",
                age=20 + (c_idx % 45),
                gender=rng.choice(["Male", "Female", "Non-binary"]),
                metadata_={"tier": rng.choice(["standard", "gold", "platinum"]), "source": "seeder"},
            )
            orga_customers.append(c)
            db.add(c)

        # 15 synthetic Org B customers
        orgb_customers: list[Customer] = [eve_profile]
        for c_idx in range(1, 16):
            c = Customer(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"orgb-cust-{c_idx}"),
                org_id=ORG_B_ID, user_id=None,
                full_name=f"Customer B-{c_idx}",
                email=f"customer{c_idx}@clientb.com",
                phone=f"+1-556-{1000 + c_idx}",
                age=25 + (c_idx % 40),
                gender=rng.choice(["Male", "Female", "Non-binary"]),
                metadata_={"tier": rng.choice(["standard", "enterprise"]), "source": "seeder"},
            )
            orgb_customers.append(c)
            db.add(c)

        await db.flush()

        # ---------------------------------------------------------------------
        # 6. Seed 1,000+ Support Tickets with Multi-Turn Conversations
        # ---------------------------------------------------------------------
        print("🎫 Seeding 1,050+ Support Tickets with multi-turn dialogue...")
        now = datetime.now(timezone.utc)
        charlie_ticket_id = uuid.uuid5(uuid.NAMESPACE_DNS, "ticket-charlie-refund-issue")

        # -- Charlie's Flagship Ticket (HITL Refund Scenario) --
        charlie_ticket = Ticket(
            id=charlie_ticket_id, org_id=ORG_A_ID, customer_id=CHARLIE_CUSTOMER_ID,
            assigned_agent_id=BOB_USER_ID,
            title="Refund request for AI Assistant Copilot annual subscription",
            description="I was billed $250.00 for the annual license but our team switched to monthly billing.",
            status="open", priority="high", category="billing",
            channel="web", product_name="AI Assistant Copilot", csat_rating=None,
        )
        db.add(charlie_ticket)

        # Charlie's multi-turn conversation (realistic dialogue)
        charlie_msgs = [
            TicketMessage(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "msg-charlie-1"),
                org_id=ORG_A_ID, ticket_id=charlie_ticket_id,
                sender_type="customer", sender_id=CHARLIE_USER_ID,
                body="Hello, I would like to request a refund of $250.00 for my recent annual payment. We switched to monthly billing last week.",
                created_at=now - timedelta(hours=4),
            ),
            TicketMessage(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "msg-charlie-2"),
                org_id=ORG_A_ID, ticket_id=charlie_ticket_id,
                sender_type="support_agent", sender_id=BOB_USER_ID,
                body="Hi Charlie, thank you for reaching out. I can see the annual charge on your account. Since this is over $100, I'll need to get admin approval for the refund. Let me escalate this.",
                created_at=now - timedelta(hours=3, minutes=45),
            ),
            TicketMessage(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "msg-charlie-3"),
                org_id=ORG_A_ID, ticket_id=charlie_ticket_id,
                sender_type="ai_agent", sender_id=None,
                body="I've reviewed the billing records for this account. The annual license was purchased 6 days ago and falls within the 7-day refund window per our Refund Policy SOP.",
                created_at=now - timedelta(hours=3, minutes=30),
            ),
            TicketMessage(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "msg-charlie-4"),
                org_id=ORG_A_ID, ticket_id=charlie_ticket_id,
                sender_type="customer", sender_id=CHARLIE_USER_ID,
                body="Great, please let me know once it's approved. I'd like this resolved today if possible.",
                created_at=now - timedelta(hours=3),
            ),
        ]
        db.add_all(charlie_msgs)

        # Charlie's private staff notes (Bob's internal triage)
        charlie_notes = [
            TicketNote(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "note-charlie-1"),
                org_id=ORG_A_ID, ticket_id=charlie_ticket_id, author_id=BOB_USER_ID,
                note="Verified customer license. Annual purchase 6 days ago — within 7-day refund window. Customer tier: gold.",
                created_at=now - timedelta(hours=3, minutes=40),
            ),
            TicketNote(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "note-charlie-2"),
                org_id=ORG_A_ID, ticket_id=charlie_ticket_id, author_id=BOB_USER_ID,
                note="Escalating to Alice for HITL approval. Amount $250.00 exceeds $100 threshold. Generating approval token.",
                created_at=now - timedelta(hours=3, minutes=35),
            ),
        ]
        db.add_all(charlie_notes)

        # -- Dave's Org B Ticket (Cross-Tenant Isolation Target) --
        dave_ticket = Ticket(
            id=DAVE_TICKET_ID, org_id=ORG_B_ID,
            customer_id=orgb_customers[0].id, assigned_agent_id=None,
            title="Org B Confidential Database Outage",
            description="Org B internal database connectivity interrupted. Emergency priority.",
            status="open", priority="urgent", category="technical",
            channel="chat", product_name="Database Cluster",
        )
        db.add(dave_ticket)

        # -- Bulk Generate 1,050 Tickets with Multi-Turn Dialogue --
        total_tickets = 1050
        print(f"📦 Generating {total_tickets} synthetic tickets in batches...")
        tickets_batch: list[Ticket] = []
        messages_batch: list[TicketMessage] = []
        notes_batch: list[TicketNote] = []

        for i in range(1, total_tickets + 1):
            t_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"ticket-synth-{i}")
            is_org_a = i <= 950
            t_org_id = ORG_A_ID if is_org_a else ORG_B_ID
            cust_pool = orga_customers if is_org_a else orgb_customers
            assigned_agent = BOB_USER_ID if (is_org_a and i % 3 == 0) else None
            status_val = STATUSES[i % len(STATUSES)]
            category_val = CATEGORIES[i % len(CATEGORIES)]
            priority_val = PRIORITIES[i % len(PRIORITIES)]
            channel_val = CHANNELS[i % len(CHANNELS)]
            product_val = PRODUCTS[i % len(PRODUCTS)]

            created_time = now - timedelta(days=rng.randint(1, 30), minutes=rng.randint(1, 1400))
            resolved_time = created_time + timedelta(hours=rng.randint(1, 48)) if status_val in ("resolved", "closed") else None
            first_response = created_time + timedelta(minutes=rng.randint(5, 120)) if status_val != "open" else None
            csat = rng.randint(1, 5) if status_val in ("resolved", "closed") else None

            ticket = Ticket(
                id=t_id, org_id=t_org_id,
                customer_id=cust_pool[i % len(cust_pool)].id,
                assigned_agent_id=assigned_agent,
                title=f"Issue with {product_val}: {category_val} error #{1000 + i}",
                description=f"Customer reports a {priority_val}-priority {category_val} issue with {product_val}. Error code: ERR-{1000 + i}.",
                status=status_val, priority=priority_val, category=category_val,
                channel=channel_val, product_name=product_val,
                resolution=f"Resolved: {category_val} configuration corrected on backend." if resolved_time else None,
                csat_rating=csat,
                first_response_at=first_response, resolved_at=resolved_time,
                created_at=created_time, updated_at=resolved_time or created_time,
            )
            tickets_batch.append(ticket)

            # Multi-turn dialogue: 2–4 messages per ticket
            num_messages = rng.randint(2, 4)
            for m_idx in range(num_messages):
                is_customer_msg = m_idx % 2 == 0
                msg_time = created_time + timedelta(minutes=15 * (m_idx + 1))
                msg = TicketMessage(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"msg-synth-{i}-{m_idx}"),
                    org_id=t_org_id, ticket_id=t_id,
                    sender_type="customer" if is_customer_msg else "support_agent",
                    sender_id=None,
                    body=(
                        CUSTOMER_MESSAGES[m_idx % len(CUSTOMER_MESSAGES)]
                        if is_customer_msg else
                        AGENT_MESSAGES[m_idx % len(AGENT_MESSAGES)]
                    ).format(product=product_val, category=category_val, code=f"ERR-{1000 + i}"),
                    created_at=msg_time,
                )
                messages_batch.append(msg)

            # Internal staff notes on ~20% of Org A tickets
            if i % 5 == 0 and is_org_a:
                tier = rng.choice(["standard", "gold", "platinum"])
                sla_hours = {"standard": 24, "gold": 8, "platinum": 4}[tier]
                note = TicketNote(
                    id=uuid.uuid5(uuid.NAMESPACE_DNS, f"note-synth-{i}"),
                    org_id=ORG_A_ID, ticket_id=t_id, author_id=BOB_USER_ID,
                    note=rng.choice(NOTE_TEMPLATES).format(
                        tier=tier, sla_hours=sla_hours,
                        category=category_val, kb_id=rng.randint(100, 999),
                    ),
                    created_at=created_time + timedelta(minutes=rng.randint(5, 30)),
                )
                notes_batch.append(note)

            # Flush every 250 tickets to cap memory
            if len(tickets_batch) >= 250:
                db.add_all(tickets_batch + messages_batch + notes_batch)
                await db.flush()
                tickets_batch.clear()
                messages_batch.clear()
                notes_batch.clear()

        if tickets_batch:
            db.add_all(tickets_batch + messages_batch + notes_batch)
            await db.flush()

        # ---------------------------------------------------------------------
        # 7. Seed Invoices (Both Orgs — HITL Refund Targets)
        # ---------------------------------------------------------------------
        print("💳 Seeding Invoices & Financial Records...")

        # Charlie's flagship $250 HITL refund target — linked to his ticket
        charlie_invoice_id = uuid.uuid5(uuid.NAMESPACE_DNS, "invoice-charlie-refund-target")
        charlie_invoice = Invoice(
            id=charlie_invoice_id, org_id=ORG_A_ID, customer_id=CHARLIE_CUSTOMER_ID,
            ticket_id=charlie_ticket_id,  # Linked to Charlie's refund ticket
            product_name="AI Assistant Copilot (Annual)",
            amount=Decimal("250.00"), currency="USD",
            status="paid", refunded_amount=Decimal("0.00"),
        )
        db.add(charlie_invoice)

        # Org A invoices across customers (mix of amounts for threshold testing)
        for idx, cust in enumerate(orga_customers[1:]):
            inv = Invoice(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"orga-inv-{idx}"),
                org_id=ORG_A_ID, customer_id=cust.id,
                product_name=rng.choice(PRODUCTS),
                amount=Decimal(f"{rng.randint(29, 999)}.{rng.randint(0, 99):02d}"),
                currency="USD", status="paid", refunded_amount=Decimal("0.00"),
            )
            db.add(inv)

        # Org B invoices — so Dave and teammates can test refund flows on Org B
        eve_invoice_id = uuid.uuid5(uuid.NAMESPACE_DNS, "invoice-eve-orgb-target")
        eve_invoice = Invoice(
            id=eve_invoice_id, org_id=ORG_B_ID, customer_id=EVE_CUSTOMER_ID,
            product_name="Database Cluster (Monthly)",
            amount=Decimal("175.00"), currency="USD",
            status="paid", refunded_amount=Decimal("0.00"),
        )
        db.add(eve_invoice)

        for idx, cust in enumerate(orgb_customers[1:]):
            inv = Invoice(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, f"orgb-inv-{idx}"),
                org_id=ORG_B_ID, customer_id=cust.id,
                product_name=rng.choice(PRODUCTS),
                amount=Decimal(f"{rng.randint(49, 599)}.{rng.randint(0, 99):02d}"),
                currency="USD", status="paid", refunded_amount=Decimal("0.00"),
            )
            db.add(inv)

        await db.flush()

        # ---------------------------------------------------------------------
        # 8. Seed RAG Knowledge Base — Multi-Chunk Documents with Vectors
        # ---------------------------------------------------------------------
        print("🧠 Seeding Knowledge Base Articles (multi-chunk, 384-dim vectors)...")

        kb_articles = [
            # --- Org A: Refund SOP (3 chunks = multi-chunk document) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-refund-sop-0"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-refund-sop"),
                chunk_index=0,
                title="Refund Policy & HITL Approval SOP",
                content=(
                    "Standard Operating Procedure: All refunds up to $100.00 can be processed directly "
                    "by authorized Support Agents with the refund.issue permission. Any refund exceeding "
                    "$100.00 requires explicit Human-In-The-Loop approval from an Org_Admin."
                ),
                access_level="internal_staff",
                embedding=generate_mock_vector(101),
            ),
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-refund-sop-1"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-refund-sop"),
                chunk_index=1,
                title="Refund Policy & HITL Approval SOP",
                content=(
                    "The admin approval generates a signed 15-minute HMAC-SHA256 token that binds the "
                    "invoice ID, refund amount, organization, approver identity, and expiration timestamp. "
                    "This token is single-use and verified cryptographically before execution."
                ),
                access_level="internal_staff",
                embedding=generate_mock_vector(102),
            ),
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-refund-sop-2"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-refund-sop"),
                chunk_index=2,
                title="Refund Policy & HITL Approval SOP",
                content=(
                    "Refund idempotency is enforced at two layers: a fast Redis cache check (TTL 24h) and "
                    "a durable audit_logs table query. Duplicate idempotency keys return the original "
                    "execution result without re-processing the financial transaction."
                ),
                access_level="internal_staff",
                embedding=generate_mock_vector(103),
            ),

            # --- Org A: Security FAQ (2 chunks) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-security-0"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-security-faq"),
                chunk_index=0,
                title="Account Security & Two-Factor Authentication FAQ",
                content=(
                    "To enable two-factor authentication (2FA), navigate to Account Settings > Security. "
                    "Scan the QR code using Google Authenticator or any TOTP-compliant application. "
                    "Store your recovery backup codes securely in a password manager."
                ),
                access_level="public",
                embedding=generate_mock_vector(201),
            ),
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-security-1"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-security-faq"),
                chunk_index=1,
                title="Account Security & Two-Factor Authentication FAQ",
                content=(
                    "If you lose access to your authenticator app, use one of your backup codes to sign in. "
                    "Each backup code can only be used once. Contact support if all codes have been consumed "
                    "and you need account recovery assistance."
                ),
                access_level="public",
                embedding=generate_mock_vector(202),
            ),

            # --- Org A: Admin Disaster Recovery (admin_only tier) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-admin-dr"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-admin-dr"),
                chunk_index=0,
                title="Emergency Admin Disaster Recovery & Credential Rotation",
                content=(
                    "CONFIDENTIAL — Admin eyes only. In the event of an infrastructure compromise: "
                    "1) Purge all active Redis user sessions. 2) Rotate the JWT_SECRET_KEY in all 4 services. "
                    "3) Execute secondary database failover within 5 minutes. 4) Notify SOC team."
                ),
                access_level="admin_only",
                embedding=generate_mock_vector(301),
            ),

            # --- Org A: Product Troubleshooting (public) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orga-troubleshoot"),
                org_id=ORG_A_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-troubleshoot"),
                chunk_index=0,
                title="Common Product Troubleshooting Guide",
                content=(
                    "If you encounter error codes starting with ERR-1xxx, try clearing your browser cache "
                    "and signing out/in. For ERR-2xxx codes, check your API key configuration in Settings > "
                    "Integrations. Contact support if the issue persists after these steps."
                ),
                access_level="public",
                embedding=generate_mock_vector(401),
            ),

            # --- Org B: Onboarding Guide (public) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orgb-onboarding"),
                org_id=ORG_B_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-orgb-onboarding"),
                chunk_index=0,
                title="Organization B Customer Onboarding Guide",
                content=(
                    "Welcome to Organization B. This guide covers our enterprise service level agreements, "
                    "dedicated support channels, and account setup procedures for new customers."
                ),
                access_level="public",
                embedding=generate_mock_vector(501),
            ),

            # --- Org B: Internal Pricing (staff only) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orgb-pricing"),
                org_id=ORG_B_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-orgb-pricing"),
                chunk_index=0,
                title="Organization B Internal Pricing Matrix",
                content=(
                    "Confidential volume discounting tiers for Org B enterprise sales reps. "
                    "Tier 1 (1-50 seats): 10% discount. Tier 2 (51-200 seats): 20% discount. "
                    "Tier 3 (201+ seats): Contact VP Sales for custom pricing."
                ),
                access_level="internal_staff",
                embedding=generate_mock_vector(502),
            ),

            # --- Org B: Admin SOP (admin_only) ---
            KnowledgeBaseArticle(
                id=uuid.uuid5(uuid.NAMESPACE_DNS, "kb-orgb-admin-sop"),
                org_id=ORG_B_ID,
                document_id=uuid.uuid5(uuid.NAMESPACE_DNS, "doc-orgb-admin-sop"),
                chunk_index=0,
                title="Organization B Admin Operations SOP",
                content=(
                    "CONFIDENTIAL — Org B Admin. Quarterly compliance audit procedures and "
                    "emergency data export workflows. Refer to Section 4.2 for GDPR data subject "
                    "access request (DSAR) handling timelines."
                ),
                access_level="admin_only",
                embedding=generate_mock_vector(503),
            ),
        ]
        db.add_all(kb_articles)
        await db.commit()

        # Print summary
        print("✅ Synthetic Database Seeding Completed Successfully!")
        print()
        print("📊 Seeded Data Summary:")
        print("  Organizations:     2 (Org A + Org B)")
        print("  Roles:             6 (Admin, Agent, Customer × 2 orgs)")
        print("  Users:             5 (Alice, Bob, Charlie, Dave, Eve)")
        print("  Customer Profiles: 67 (Charlie + 50 Org A + Eve + 15 Org B)")
        print("  Invoices:          67 (Charlie's $250 target + 50 Org A + Eve's $175 target + 15 Org B)")
        print(f"  Tickets:           {total_tickets + 2} (Charlie's refund + Dave's cross-tenant + {total_tickets} synthetic)")
        print(f"  Messages:          ~{total_tickets * 3 + 4} (multi-turn dialogues)")
        print(f"  Staff Notes:       ~{total_tickets // 5 + 2} (20% of Org A tickets + Charlie's triage)")
        print(f"  KB Articles:       {len(kb_articles)} (multi-chunk, 3 access tiers, both orgs)")
        print()
        print("🔑 Login Credentials (all users):")
        print(f"  Password: {DEFAULT_PASSWORD}")
        print("  Alice:   alice@orga.com     (Org A Admin)")
        print("  Bob:     bob@orga.com       (Org A Agent)")
        print("  Charlie: charlie@customer.com (Org A Customer)")
        print("  Dave:    dave@orgb.com       (Org B Admin)")
        print("  Eve:     eve@customer-b.com  (Org B Customer)")


if __name__ == "__main__":
    asyncio.run(seed_database())
