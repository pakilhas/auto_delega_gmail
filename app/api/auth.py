from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User, AuditLog
from app.api.deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["Autenticação"])

class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login")
def login(login_data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == login_data.username).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha incorretos."
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta conta está desativada. Contate o administrador."
        )
    
    # Criar token JWT
    access_token = create_access_token(data={"sub": user.username, "role": user.role.value})
    
    # Registrar log de auditoria
    log = AuditLog(
        performed_by=user.username,
        action="USER_LOGIN",
        details=f"Usuário {user.username} realizou login com sucesso.",
        status="SUCCESS"
    )
    db.add(log)
    db.commit()

    # Definir cookie HttpOnly
    res = JSONResponse(content={
        "status": "success",
        "message": "Login realizado com sucesso!",
        "user": {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value
        }
    })
    res.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        max_age=86400, # 24 horas
        samesite="lax"
    )
    return res

@router.post("/logout")
def logout(response: Response):
    res = JSONResponse(content={"status": "success", "message": "Sessão encerrada com sucesso."})
    res.delete_cookie("access_token")
    return res

@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "is_active": current_user.is_active
    }
