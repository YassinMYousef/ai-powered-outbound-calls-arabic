"""CRM customer records and follow-up flagging.

Module: Backend/Data (the Customer model) + Telephony (flagging feeds the
call queue) — Person B's Sprint 4 task. The requirements doc's architecture
diagram has a "[CRM / Inbound Call Records]" box with no real external system
behind it in this project; this router is that source of truth.

TODO(auth): guard with data/auth.require_role once OAuth2/RBAC lands — same
gap already noted in api/calls.py, api/chat.py, api/kb.py.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.data.models import CallLog, Customer

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateCustomerRequest(BaseModel):
    name: str = Field(min_length=1)
    phone: str = Field(min_length=1)  # E.164, e.g. "+201091894094"
    notes: str | None = None


class FlagForFollowUpRequest(BaseModel):
    ticket_id: str | None = None  # ties the follow-up back to the prior inbound call


def _customer_dict(customer: Customer) -> dict:
    return {
        "id": customer.id,
        "name": customer.name,
        "phone": customer.phone,
        "notes": customer.notes,
        "created_at": customer.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_customer(body: CreateCustomerRequest, db: Session = Depends(get_db)) -> dict:
    """Add a customer to the CRM."""
    existing = db.execute(select(Customer).where(Customer.phone == body.phone)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="a customer with this phone already exists")

    customer = Customer(name=body.name, phone=body.phone, notes=body.notes)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _customer_dict(customer)


@router.get("")
def list_customers(db: Session = Depends(get_db)) -> list[dict]:
    """List CRM customers, newest first."""
    customers = (
        db.execute(select(Customer).order_by(Customer.created_at.desc(), Customer.id.desc()))
        .scalars()
        .all()
    )
    return [_customer_dict(c) for c in customers]


@router.get("/{customer_id}")
def get_customer(customer_id: int, db: Session = Depends(get_db)) -> dict:
    """One customer plus their outbound-call history."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")

    calls = (
        db.execute(select(CallLog).where(CallLog.customer_id == customer_id).order_by(CallLog.created_at.desc()))
        .scalars()
        .all()
    )
    return {
        **_customer_dict(customer),
        "call_history": [
            {
                "id": call.id,
                "ticket_id": call.ticket_id,
                "status": call.status,
                "outcome": call.outcome,
                "created_at": call.created_at.isoformat(),
            }
            for call in calls
        ],
    }


@router.delete("/{customer_id}", status_code=204)
def delete_customer(customer_id: int, db: Session = Depends(get_db)) -> None:
    """Remove a customer from the CRM.

    Their past CallLog rows are kept (CallLog.customer_id is ON DELETE SET
    NULL) — deleting the customer record doesn't erase call history.
    """
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")
    db.delete(customer)
    db.commit()


@router.post("/{customer_id}/flag", status_code=201)
def flag_for_follow_up(customer_id: int, body: FlagForFollowUpRequest, db: Session = Depends(get_db)) -> dict:
    """Flag a customer for an outbound follow-up call.

    Creates a queued CallLog row linked to this customer — the flag IS the
    queue entry, no separate "convert to queued" step. This does NOT dial;
    it lands at status="queued" exactly like any other row and is picked up
    by POST /api/calls/schedule (or the future nightly scheduler), same as
    workers/tasks.py::schedule_follow_up_batch already does for any queued
    row, regardless of how it got there.
    """
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="customer not found")

    call = CallLog(
        customer_id=customer.id,
        customer_phone=customer.phone,
        ticket_id=body.ticket_id,
        status="queued",
    )
    db.add(call)
    db.commit()
    db.refresh(call)
    return {
        "id": call.id,
        "customer_id": customer.id,
        "customer_phone": call.customer_phone,
        "ticket_id": call.ticket_id,
        "status": call.status,
    }
