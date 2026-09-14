from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User, ScheduledDelegation, ScheduledDelegationStatus, AuditLog
from app.api.deps import get_current_user, require_operator
from app.services.google_workspace import GoogleWorkspaceService
from app.services.email_parser import EmailParserService

router = APIRouter(prefix="/api/scheduled", tags=["Delegações Agendadas & Automação"])

class ManualScheduleCreate(BaseModel):
    delegator_email: str
    delegatee_email: str
    delegator_name: Optional[str] = None
    delegatee_name: Optional[str] = None
    period_reason: str = "Férias"
    start_time: str # "DD/MM/YYYY HH:MM" ou ISO
    end_time: str # "DD/MM/YYYY HH:MM" ou ISO
    notes: Optional[str] = None

@router.get("", response_model=List[dict])
def list_scheduled_delegations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    items = db.query(ScheduledDelegation).order_by(ScheduledDelegation.id.desc()).all()
    return [
        {
            "id": item.id,
            "delegator_name": item.delegator_name or item.delegator_email,
            "delegator_email": item.delegator_email,
            "delegatee_name": item.delegatee_name or item.delegatee_email,
            "delegatee_email": item.delegatee_email,
            "period_reason": item.period_reason,
            "start_time": item.start_time.strftime("%d/%m/%Y %H:%M") if item.start_time else "-",
            "end_time": item.end_time.strftime("%d/%m/%Y %H:%M") if item.end_time else "-",
            "status": item.status.value,
            "spreadsheet_url": item.spreadsheet_url,
            "applied_at": item.applied_at.strftime("%d/%m/%Y %H:%M") if item.applied_at else "-",
            "revoked_at": item.revoked_at.strftime("%d/%m/%Y %H:%M") if item.revoked_at else "-",
            "created_at": item.created_at.strftime("%d/%m/%Y %H:%M") if item.created_at else "-"
        }
        for item in items
    ]

@router.post("/trigger-email-check")
def trigger_email_check(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """Força uma verificação imediata de novos e-mails de delegação na caixa suporte."""
    new_requests = EmailParserService.read_unread_delegation_emails()
    count = 0
    now = datetime.now()

    for req in new_requests:
        existing = db.query(ScheduledDelegation).filter(
            ScheduledDelegation.source_message_id == req['message_id']
        ).first()

        if not existing:
            new_item = ScheduledDelegation(
                source_message_id=req['message_id'],
                delegator_name=req.get('delegator_name'),
                delegator_email=req['delegator_email'],
                delegatee_name=req.get('delegatee_name'),
                delegatee_email=req['delegatee_email'],
                period_reason=req.get('period_reason', 'Férias'),
                start_time=req['start_time'],
                end_time=req['end_time'],
                spreadsheet_url=req.get('spreadsheet_url'),
                status=ScheduledDelegationStatus.PENDING_START
            )
            # Se o início já passou ou é agora, ativa imediatamente
            if new_item.start_time <= now <= new_item.end_time:
                try:
                    GoogleWorkspaceService.add_delegate(new_item.delegator_email, new_item.delegatee_email)
                    new_item.status = ScheduledDelegationStatus.ACTIVE
                    new_item.applied_at = now
                except Exception as e:
                    new_item.status = ScheduledDelegationStatus.FAILED

            db.add(new_item)
            count += 1

    db.commit()
    return {"status": "success", "message": f"{count} novas solicitações de delegação importadas do e-mail!"}

@router.post("/{item_id}/apply-now")
def apply_scheduled_now(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    item = db.query(ScheduledDelegation).filter(ScheduledDelegation.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    try:
        GoogleWorkspaceService.add_delegate(item.delegator_email, item.delegatee_email)
        item.status = ScheduledDelegationStatus.ACTIVE
        item.applied_at = datetime.now()
        
        log = AuditLog(
            performed_by=current_user.username,
            action="MANUAL_TRIGGER_APPLIED",
            delegator_email=item.delegator_email,
            delegatee_email=item.delegatee_email,
            details=f"Delegação ativada manualmente antes do prazo.",
            status="SUCCESS"
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Delegação ativada com sucesso no Gmail!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/{item_id}/revoke-now")
def revoke_scheduled_now(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    item = db.query(ScheduledDelegation).filter(ScheduledDelegation.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    try:
        GoogleWorkspaceService.remove_delegate(item.delegator_email, item.delegatee_email)
        item.status = ScheduledDelegationStatus.EXPIRED
        item.revoked_at = datetime.now()

        log = AuditLog(
            performed_by=current_user.username,
            action="MANUAL_TRIGGER_REVOKED",
            delegator_email=item.delegator_email,
            delegatee_email=item.delegatee_email,
            details=f"Delegação revogada manualmente.",
            status="SUCCESS"
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Delegação revogada com sucesso no Gmail!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
