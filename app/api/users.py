from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole, AuditLog
from app.api.deps import require_admin, get_current_user

router = APIRouter(prefix="/api/users", tags=["Gerenciamento de Usuários"])

class UserCreate(BaseModel):
    username: str
    email: str
    full_name: Optional[str] = None
    password: str
    role: UserRole = UserRole.OPERATOR

class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: str

@router.get("", response_model=List[dict])
def list_users(
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    users = db.query(User).order_by(User.id.asc()).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "full_name": u.full_name or "",
            "role": u.role.value,
            "is_active": u.is_active,
            "created_at": u.created_at.strftime("%d/%m/%Y %H:%M") if u.created_at else "-"
        }
        for u in users
    ]

@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    # Checar se username ou email já existem
    if db.query(User).filter(User.username == user_in.username).first():
        raise HTTPException(status_code=400, detail="Este nome de usuário já está em uso.")
    if db.query(User).filter(User.email == user_in.email).first():
        raise HTTPException(status_code=400, detail="Este e-mail já está cadastrado.")

    new_user = User(
        username=user_in.username,
        email=user_in.email,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
        is_active=True
    )
    db.add(new_user)
    
    # Auditoria
    log = AuditLog(
        performed_by=admin_user.username,
        action="CREATE_SYSTEM_USER",
        details=f"Criou o usuário '{new_user.username}' com perfil '{new_user.role.value}'.",
        status="SUCCESS"
    )
    db.add(log)
    db.commit()
    db.refresh(new_user)

    return {"message": f"Usuário {new_user.username} cadastrado com sucesso!", "id": new_user.id}

@router.put("/{user_id}")
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")

    if user_in.email and user_in.email != user.email:
        if db.query(User).filter(User.email == user_in.email).first():
            raise HTTPException(status_code=400, detail="E-mail já utilizado por outro usuário.")
        user.email = user_in.email

    if user_in.full_name is not None:
        user.full_name = user_in.full_name
    if user_in.role is not None:
        user.role = user_in.role
    if user_in.is_active is not None:
        # Previne desativar a própria conta de admin
        if user.id == admin_user.id and not user_in.is_active:
            raise HTTPException(status_code=400, detail="Você não pode desativar sua própria conta de administrador.")
        user.is_active = user_in.is_active
    if user_in.password:
        user.hashed_password = get_password_hash(user_in.password)

    log = AuditLog(
        performed_by=admin_user.username,
        action="UPDATE_SYSTEM_USER",
        details=f"Atualizou o usuário '{user.username}'.",
        status="SUCCESS"
    )
    db.add(log)
    db.commit()

    return {"message": f"Usuário {user.username} atualizado com sucesso."}

@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Usuário não encontrado.")
    
    if user.id == admin_user.id:
        raise HTTPException(status_code=400, detail="Você não pode excluir sua própria conta de administrador.")

    deleted_username = user.username
    db.delete(user)

    log = AuditLog(
        performed_by=admin_user.username,
        action="DELETE_SYSTEM_USER",
        details=f"Excluiu o usuário '{deleted_username}'.",
        status="SUCCESS"
    )
    db.add(log)
    db.commit()

    return {"message": f"Usuário {deleted_username} removido com sucesso."}
