"""Agent roster management — a manager adds/removes agents.

Module: Backend/Data (the Agent model). Not an auth system — see
data/auth.py — this is a roster, not login accounts.

TODO(auth): guard with data/auth.require_role (quality_manager only) once
OAuth2/RBAC lands, same gap already noted in api/calls.py, api/customers.py,
api/chat.py, api/kb.py.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.data.db import get_db
from app.data.models import Agent

logger = logging.getLogger(__name__)
router = APIRouter()


class CreateAgentRequest(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)


def _agent_dict(agent: Agent) -> dict:
    return {
        "id": agent.id,
        "name": agent.name,
        "email": agent.email,
        "created_at": agent.created_at.isoformat(),
    }


@router.post("", status_code=201)
def create_agent(body: CreateAgentRequest, db: Session = Depends(get_db)) -> dict:
    """Add an agent to the roster."""
    existing = db.execute(select(Agent).where(Agent.email == body.email)).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="an agent with this email already exists")

    agent = Agent(name=body.name, email=body.email)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return _agent_dict(agent)


@router.get("")
def list_agents(db: Session = Depends(get_db)) -> list[dict]:
    """List agents, newest first."""
    agents = db.execute(select(Agent).order_by(Agent.created_at.desc(), Agent.id.desc())).scalars().all()
    return [_agent_dict(a) for a in agents]


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: int, db: Session = Depends(get_db)) -> None:
    """Remove an agent from the roster."""
    agent = db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="agent not found")
    db.delete(agent)
    db.commit()
