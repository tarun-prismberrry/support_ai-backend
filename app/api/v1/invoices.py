"""
Invoices & HITL Refund API Routes.
Enforces multi-tenant isolation, idempotency keys, Decimal precision,
and cryptographic HMAC approval tokens for refunds > $100 (CONTRACTS.md Section 6).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import UserContext, get_current_user, require_permission
from app.core.redis import get_redis_client
from app.models.audit import AuditLog
from app.models.billing import Invoice
from app.models.user import Customer
from app.schemas.billing import (
    ApproveRefundRequest,
    ApproveRefundResponse,
    InvoiceResponse,
    RefundRequest,
    RefundResponse,
)

router = APIRouter(prefix="/invoices", tags=["Invoices & Billing"])
settings = get_settings()


@router.get("", response_model=list[InvoiceResponse], status_code=status.HTTP_200_OK)
async def list_invoices(
    customer_id: Optional[uuid.UUID] = Query(None, description="Filter by customer ID (staff only)"),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[Invoice]:
    """
    List invoices for the caller's organization.
    Staff members see all org invoices; customers see only their own.
    """
    is_staff = bool(
        "*" in current_user.permissions
        or "ticket.read:org" in current_user.permissions
        or "refund.issue" in current_user.permissions
    )

    stmt = select(Invoice).where(Invoice.org_id == current_user.org_id)

    if is_staff:
        if customer_id:
            stmt = stmt.where(Invoice.customer_id == customer_id)
    else:
        # Resolve customer profile linked to this user
        cust_stmt = select(Customer.id).where(
            Customer.user_id == current_user.user_id,
            Customer.org_id == current_user.org_id,
        )
        cust_res = await db.execute(cust_stmt)
        resolved_customer_id = cust_res.scalar_one_or_none()
        if not resolved_customer_id:
            return []
        stmt = stmt.where(Invoice.customer_id == resolved_customer_id)

    stmt = stmt.order_by(Invoice.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{invoice_id}", response_model=InvoiceResponse, status_code=status.HTTP_200_OK)
async def get_invoice_details(
    invoice_id: uuid.UUID,
    current_user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Invoice:
    """
    Retrieve full details for a single invoice.
    Enforces multi-tenant ownership and customer profile boundary.
    """
    is_staff = bool(
        "*" in current_user.permissions
        or "ticket.read:org" in current_user.permissions
        or "refund.issue" in current_user.permissions
    )

    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.org_id == current_user.org_id,
    )

    if not is_staff:
        cust_stmt = select(Customer.id).where(
            Customer.user_id == current_user.user_id,
            Customer.org_id == current_user.org_id,
        )
        cust_res = await db.execute(cust_stmt)
        resolved_customer_id = cust_res.scalar_one_or_none()
        if not resolved_customer_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
        stmt = stmt.where(Invoice.customer_id == resolved_customer_id)

    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    return invoice


@router.post(
    "/{invoice_id}/approve-refund",
    response_model=ApproveRefundResponse,
    status_code=status.HTTP_200_OK,
)
async def approve_refund(
    invoice_id: uuid.UUID,
    payload: ApproveRefundRequest,
    current_user: UserContext = Depends(require_permission("refund.issue")),
    db: AsyncSession = Depends(get_db),
) -> ApproveRefundResponse:
    """
    HITL Pre-Approval: Issue a signed, single-use HMAC approval token
    for refund amounts exceeding $100.00. Valid for 15 minutes.
    """
    stmt = select(Invoice).where(
        Invoice.id == invoice_id,
        Invoice.org_id == current_user.org_id,
    )
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    remaining_balance = invoice.amount - invoice.refunded_amount
    if payload.amount > remaining_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Approval amount {payload.amount} exceeds remaining balance {remaining_balance}",
        )

    # Generate 15-minute expiration timestamp
    expires_at = int(time.time()) + 900

    # Cryptographic HMAC-SHA256 signature binding invoice, amount, org, approver, and expiry
    sign_payload = f"{invoice.id}:{payload.amount}:{current_user.org_id}:{current_user.user_id}:{expires_at}"
    signature = hmac.new(
        settings.JWT_SECRET_KEY.encode("utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    approval_token = f"{expires_at}.{current_user.user_id}.{signature}"

    # Record approval in audit log
    audit = AuditLog(
        id=uuid.uuid4(),
        org_id=current_user.org_id,
        actor_id=current_user.user_id,
        action="refund.approve",
        resource_type="invoices",
        resource_id=invoice.id,
        details={
            "amount": str(payload.amount),
            "expires_at": expires_at,
            "approval_signature": signature,
        },
    )
    db.add(audit)
    await db.commit()

    return ApproveRefundResponse(
        invoice_id=invoice.id,
        amount=payload.amount,
        approval_token=approval_token,
        expires_at=expires_at,
    )


@router.post(
    "/{invoice_id}/refund",
    response_model=RefundResponse,
    status_code=status.HTTP_200_OK,
)
async def issue_refund(
    invoice_id: uuid.UUID,
    payload: RefundRequest,
    current_user: UserContext = Depends(require_permission("refund.issue")),
    db: AsyncSession = Depends(get_db),
) -> RefundResponse:
    """
    Execute refund with strict defense-in-depth:
    1. Idempotency Check FIRST (cached replay returned if already executed).
    2. Permission: Caller must possess 'refund.issue'.
    3. HITL Check: If amount > 100.00, verify approval_token signature, expiry, and single-use.
    4. Balance Check: amount <= remaining unrefunded balance.
    5. Atomic Transaction: update invoice, mark approval consumed, log audit event.
    """
    # 1. Idempotency Check: Fast Redis check + Durable PostgreSQL check
    redis_key = f"idempotency:refund:{current_user.org_id}:{payload.idempotency_key}"
    try:
        redis_client = get_redis_client()
        cached_bytes = await redis_client.get(redis_key)
        if cached_bytes:
            data = json.loads(cached_bytes.decode("utf-8") if isinstance(cached_bytes, bytes) else cached_bytes)
            return RefundResponse(
                invoice_id=uuid.UUID(data["invoice_id"]),
                amount=Decimal(data["amount"]),
                status=data["status"],
                refunded_amount=Decimal(data["refunded_amount"]),
                remaining_balance=Decimal(data["remaining_balance"]),
                idempotency_key=payload.idempotency_key,
                audit_log_id=uuid.UUID(data["audit_log_id"]),
                message="Refund operation previously processed (idempotent replay from cache)",
            )
    except Exception:
        pass  # Non-blocking; continue to DB idempotency check

    existing_audit_stmt = select(AuditLog).where(
        AuditLog.org_id == current_user.org_id,
        AuditLog.action == "refund.issue",
        AuditLog.details["idempotency_key"].astext == payload.idempotency_key,
    )
    existing_audit = (await db.execute(existing_audit_stmt)).scalar_one_or_none()
    if existing_audit:
        details = existing_audit.details or {}
        return RefundResponse(
            invoice_id=existing_audit.resource_id or invoice_id,
            amount=Decimal(details.get("amount", str(payload.amount))),
            status=details.get("new_status", "refunded"),
            refunded_amount=Decimal(details.get("new_refunded_amount", "0.00")),
            remaining_balance=Decimal(details.get("remaining_balance", "0.00")),
            idempotency_key=payload.idempotency_key,
            audit_log_id=existing_audit.id,
            message="Refund operation previously processed (idempotent replay)",
        )

    # 2. Fetch and lock invoice with SELECT ... FOR UPDATE to prevent race conditions
    stmt = (
        select(Invoice)
        .where(
            Invoice.id == invoice_id,
            Invoice.org_id == current_user.org_id,
        )
        .with_for_update()
    )
    res = await db.execute(stmt)
    invoice = res.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")

    # 3. Balance verification
    remaining_balance = invoice.amount - invoice.refunded_amount
    if payload.amount <= Decimal("0.00"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Refund amount must be strictly greater than zero",
        )
    if payload.amount > remaining_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Refund amount {payload.amount} exceeds remaining unrefunded balance {remaining_balance}",
        )

    # 4. HITL Approval Token verification for amounts > $100.00
    approval_signature: Optional[str] = None
    if payload.amount > Decimal("100.00"):
        if not payload.approval_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "REQUIRES_APPROVAL",
                    "message": f"Refund amount ${payload.amount} exceeds threshold $100.00 and requires an admin approval token",
                },
            )

        parts = payload.approval_token.split(".")
        if len(parts) != 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid approval token format",
            )

        token_expires_at_str, approver_id_str, signature = parts
        try:
            token_expires_at = int(token_expires_at_str)
            approver_uuid = uuid.UUID(approver_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Malformed parameters in approval token",
            )

        # Check expiry (< 15 min TTL)
        if int(time.time()) > token_expires_at:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approval token has expired",
            )

        # Cryptographic signature validation against secret key and invoice payload
        expected_sign_payload = (
            f"{invoice.id}:{payload.amount}:{current_user.org_id}:{approver_uuid}:{token_expires_at}"
        )
        expected_sig = hmac.new(
            settings.JWT_SECRET_KEY.encode("utf-8"),
            expected_sign_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_sig):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid or tampered approval token signature",
            )

        # Replay Protection: Ensure token signature has not been consumed yet
        consumed_stmt = select(AuditLog.id).where(
            AuditLog.org_id == current_user.org_id,
            AuditLog.action == "refund.issue",
            AuditLog.details["approval_signature"].astext == signature,
        )
        consumed_res = await db.execute(consumed_stmt)
        if consumed_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Approval token has already been consumed",
            )

        approval_signature = signature

    # 5. Atomic State Transition
    invoice.refunded_amount += payload.amount
    new_remaining = invoice.amount - invoice.refunded_amount
    if invoice.refunded_amount >= invoice.amount:
        invoice.status = "refunded"
    else:
        invoice.status = "partially_refunded"

    audit_id = uuid.uuid4()
    audit_entry = AuditLog(
        id=audit_id,
        org_id=current_user.org_id,
        actor_id=current_user.user_id,
        action="refund.issue",
        resource_type="invoices",
        resource_id=invoice.id,
        details={
            "amount": str(payload.amount),
            "reason": payload.reason,
            "idempotency_key": payload.idempotency_key,
            "approval_signature": approval_signature,
            "new_refunded_amount": str(invoice.refunded_amount),
            "new_status": invoice.status,
            "remaining_balance": str(new_remaining),
        },
    )
    db.add(audit_entry)
    await db.commit()
    await db.refresh(invoice)

    # Cache idempotency record in Redis for fast future replay
    try:
        redis_client = get_redis_client()
        await redis_client.set(
            redis_key,
            json.dumps({
                "invoice_id": str(invoice.id),
                "amount": str(payload.amount),
                "status": invoice.status,
                "refunded_amount": str(invoice.refunded_amount),
                "remaining_balance": str(new_remaining),
                "idempotency_key": payload.idempotency_key,
                "audit_log_id": str(audit_id),
            }),
            ex=86400,
        )
    except Exception:
        pass

    return RefundResponse(
        invoice_id=invoice.id,
        amount=payload.amount,
        status=invoice.status,
        refunded_amount=invoice.refunded_amount,
        remaining_balance=new_remaining,
        idempotency_key=payload.idempotency_key,
        audit_log_id=audit_id,
        message="Refund executed successfully",
    )
