from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.models.user import User, AuditLog
from app.api.deps import get_current_user, require_operator
from app.services.google_workspace import GoogleWorkspaceService

router = APIRouter(prefix="/api/delegations", tags=["Delegações Gmail"])

class DelegationCreate(BaseModel):
    delegator_email: str # Conta que terá seu e-mail acessado
    delegatee_email: str # Conta da pessoa que vai receber o acesso

class DelegationDelete(BaseModel):
    delegator_email: str
    delegatee_email: str

@router.get("/status-google")
def get_google_status(current_user: User = Depends(get_current_user)):
    """Retorna o status da configuração da Conta de Serviço do Google."""
    return GoogleWorkspaceService.is_configured()

@router.get("/domain-users")
def get_domain_users(
    query: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Retorna a lista de usuários do Google Workspace para autocomplete."""
    try:
        users = GoogleWorkspaceService.list_domain_users(query=query)
        return users
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list")
def list_delegates_for_account(
    account_email: str,
    current_user: User = Depends(get_current_user)
):
    """Lista todos os delegados de uma conta específica."""
    try:
        delegates = GoogleWorkspaceService.list_delegates(account_email)
        return {
            "delegator_email": account_email,
            "delegates": delegates
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/create")
def create_delegation(
    payload: DelegationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """Cria uma nova delegação no Gmail."""
    if payload.delegator_email.strip().lower() == payload.delegatee_email.strip().lower():
        raise HTTPException(
            status_code=400,
            detail="A conta delegada e a conta que recebe delegação não podem ser iguais."
        )

    try:
        result = GoogleWorkspaceService.add_delegate(
            delegator_email=payload.delegator_email.strip().lower(),
            delegatee_email=payload.delegatee_email.strip().lower()
        )

        # Gravar log de auditoria
        log = AuditLog(
            performed_by=current_user.username,
            action="CREATE_DELEGATION",
            delegator_email=payload.delegator_email,
            delegatee_email=payload.delegatee_email,
            details=f"Delegação concedida: {payload.delegatee_email} agora acessa {payload.delegator_email}",
            status="SUCCESS"
        )
        db.add(log)
        db.commit()

        return {
            "status": "success",
            "message": f"Delegação criada com sucesso! {payload.delegatee_email} agora pode acessar a caixa de {payload.delegator_email}.",
            "data": result
        }
    except Exception as e:
        # Gravar falha no log
        log = AuditLog(
            performed_by=current_user.username,
            action="CREATE_DELEGATION",
            delegator_email=payload.delegator_email,
            delegatee_email=payload.delegatee_email,
            details=f"Falha ao criar delegação: {str(e)}",
            status="FAILED"
        )
        db.add(log)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/delete")
def delete_delegation(
    payload: DelegationDelete,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator)
):
    """Revoga uma delegação existente."""
    try:
        GoogleWorkspaceService.remove_delegate(
            delegator_email=payload.delegator_email.strip().lower(),
            delegatee_email=payload.delegatee_email.strip().lower()
        )

        # Gravar log de auditoria
        log = AuditLog(
            performed_by=current_user.username,
            action="DELETE_DELEGATION",
            delegator_email=payload.delegator_email,
            delegatee_email=payload.delegatee_email,
            details=f"Delegação revogada: {payload.delegatee_email} não acessa mais {payload.delegator_email}",
            status="SUCCESS"
        )
        db.add(log)
        db.commit()

        return {
            "status": "success",
            "message": f"Delegação revogada com sucesso! Acesso de {payload.delegatee_email} a {payload.delegator_email} foi removido."
        }
    except Exception as e:
        log = AuditLog(
            performed_by=current_user.username,
            action="DELETE_DELEGATION",
            delegator_email=payload.delegator_email,
            delegatee_email=payload.delegatee_email,
            details=f"Falha ao revogar delegação: {str(e)}",
            status="FAILED"
        )
        db.add(log)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retorna os registros recentes de auditoria."""
    logs = db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
    return [
        {
            "id": l.id,
            "performed_by": l.performed_by,
            "action": l.action,
            "delegator_email": l.delegator_email,
            "delegatee_email": l.delegatee_email,
            "details": l.details,
            "status": l.status,
            "created_at": l.created_at.strftime("%d/%m/%Y %H:%M:%S") if l.created_at else "-"
        }
        for l in logs
    ]
