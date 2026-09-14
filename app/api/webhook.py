from typing import Optional
from fastapi import APIRouter, HTTPException, status, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.core.timezone import get_now_brasilia
from app.models.user import ScheduledDelegation, ScheduledDelegationStatus, AuditLog
from app.services.google_workspace import GoogleWorkspaceService
from app.services.email_parser import EmailParserService

router = APIRouter(prefix="/api/webhook", tags=["Webhook Hermes"])

class HermesDelegationWebhook(BaseModel):
    delegator_name: Optional[str] = None # ex: "EMILY WEISS" ou e-mail
    delegator_email: Optional[str] = None # ex: "emily.weiss@atl.com.br"
    delegatee_name: Optional[str] = None # ex: "LIA ISABEL" ou e-mail
    delegatee_email: Optional[str] = None # ex: "lia.isabel@atl.com.br"
    start_time: Optional[str] = None # "DD/MM/YYYY HH:MM" ou ISO
    end_time: Optional[str] = None # "DD/MM/YYYY HH:MM" ou ISO
    period_reason: Optional[str] = "Férias"
    notes: Optional[str] = None
    spreadsheet_url: Optional[str] = None
    raw_email_body: Optional[str] = None

def parse_date_str(d_str: str) -> datetime:
    d_str = d_str.strip()
    for fmt in ("%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(d_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Formato de data inválido: {d_str}. Use DD/MM/YYYY HH:MM")

@router.post("/hermes")
def receive_hermes_delegation(payload: HermesDelegationWebhook, db: Session = Depends(get_db)):
    """
    Endpoint de Webhook para o Hermes enviar solicitações de delegação diretamente via HTTP POST.
    URL: http://localhost:3000/api/webhook/hermes ou http://192.168.100.29:3000/api/webhook/hermes
    """
    domain_users = GoogleWorkspaceService.list_domain_users()

    # Se enviou texto bruto de e-mail, faz o parse automático
    if payload.raw_email_body:
        parsed = EmailParserService.parse_delegation_email_body(payload.raw_email_body, domain_users)
        if not parsed:
            raise HTTPException(status_code=400, detail="Não foi possível extrair os dados do corpo do e-mail fornecido.")
        delegator_name = parsed["delegator_name"]
        delegator_email = parsed["delegator_email"]
        delegatee_name = parsed["delegatee_name"]
        delegatee_email = parsed["delegatee_email"]
        start_dt = parsed["start_time"]
        end_dt = parsed["end_time"]
        period_reason = parsed.get("period_reason", "Férias")
        spreadsheet_url = parsed.get("spreadsheet_url")
    else:
        # Resolver e-mail do delegante
        delegator_email = payload.delegator_email
        if not delegator_email and payload.delegator_name:
            delegator_email = EmailParserService.find_email_by_name(payload.delegator_name, domain_users)
        
        # Resolver e-mail do delegatário
        delegatee_email = payload.delegatee_email
        if not delegatee_email and payload.delegatee_name:
            delegatee_email = EmailParserService.find_email_by_name(payload.delegatee_name, domain_users)

        if not delegator_email or not delegatee_email:
            raise HTTPException(
                status_code=400,
                detail=f"Não foi possível localizar os e-mails para delegante ({payload.delegator_name or payload.delegator_email}) ou delegatário ({payload.delegatee_name or payload.delegatee_email}) no Google Workspace."
            )

        try:
            start_dt = parse_date_str(payload.start_time)
            end_dt = parse_date_str(payload.end_time)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))

        delegator_name = payload.delegator_name or delegator_email
        delegatee_name = payload.delegatee_name or delegatee_email
        period_reason = payload.period_reason or "Férias"
        spreadsheet_url = payload.spreadsheet_url

    now = get_now_brasilia()
    initial_status = ScheduledDelegationStatus.PENDING_START

    # Criar registro de delegação agendada
    new_scheduled = ScheduledDelegation(
        delegator_name=delegator_name,
        delegator_email=delegator_email,
        delegatee_name=delegatee_name,
        delegatee_email=delegatee_email,
        period_reason=period_reason,
        start_time=start_dt,
        end_time=end_dt,
        spreadsheet_url=spreadsheet_url,
        notes=payload.notes,
        status=initial_status,
        created_at=now
    )

    # Se a data de início já tiver chegado, aplica agora no Gmail
    if start_dt <= now <= end_dt:
        try:
            GoogleWorkspaceService.add_delegate(delegator_email, delegatee_email)
            new_scheduled.status = ScheduledDelegationStatus.ACTIVE
            new_scheduled.applied_at = now
        except Exception as e:
            new_scheduled.status = ScheduledDelegationStatus.FAILED

    db.add(new_scheduled)

    # Log de Auditoria
    log = AuditLog(
        performed_by="HERMES_WEBHOOK",
        action="HERMES_WEBHOOK_RECEIVED",
        delegator_email=delegator_email,
        delegatee_email=delegatee_email,
        details=f"Recebido via Webhook Hermes ({period_reason}). Início: {start_dt.strftime('%d/%m/%Y %H:%M')}, Fim: {end_dt.strftime('%d/%m/%Y %H:%M')}",
        status="SUCCESS"
    )
    db.add(log)
    db.commit()
    db.refresh(new_scheduled)

    return {
        "status": "success",
        "message": f"Solicitação de delegação registrada com sucesso!",
        "scheduled_id": new_scheduled.id,
        "delegator": delegator_email,
        "delegatee": delegatee_email,
        "current_status": new_scheduled.status.value
    }
