import os
from fastapi import FastAPI, Request, Depends, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

import asyncio
from app.core.config import settings
from app.core.database import engine, Base, SessionLocal, get_db
from app.core.security import get_password_hash
from app.models.user import User, UserRole, AuditLog, ScheduledDelegation
from app.api.deps import get_current_user_optional, require_admin, get_current_user
from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.delegations import router as delegations_router
from app.api.scheduled import router as scheduled_router
from app.api.webhook import router as webhook_router
from app.services.scheduler import run_delegation_scheduler_loop

# Criar tabelas no banco de dados
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Delega ATL - Gestor de Delegações Google Workspace")

# Montar arquivos estáticos
static_dir = os.path.join(os.path.dirname(__file__), "static")
templates_dir = os.path.join(os.path.dirname(__file__), "templates")

app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=templates_dir)

# Inicialização: Garantir que o usuário administrador padrão exista e iniciar o scheduler
@app.on_event("startup")
async def startup_event():
    db = SessionLocal()
    try:
        admin_user = db.query(User).filter(User.username == settings.INITIAL_ADMIN_USERNAME).first()
        if not admin_user:
            new_admin = User(
                username=settings.INITIAL_ADMIN_USERNAME,
                email=settings.INITIAL_ADMIN_EMAIL,
                full_name=settings.INITIAL_ADMIN_FULL_NAME,
                hashed_password=get_password_hash(settings.INITIAL_ADMIN_PASSWORD),
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(new_admin)
            
            log = AuditLog(
                performed_by="SYSTEM",
                action="INITIALIZE_ADMIN",
                details=f"Administrador padrão '{settings.INITIAL_ADMIN_USERNAME}' inicializado no banco.",
                status="SUCCESS"
            )
            db.add(log)
            db.commit()
            print(f"[*] Administrador '{settings.INITIAL_ADMIN_USERNAME}' criado com sucesso.")
    finally:
        db.close()

    # Iniciar o loop de automação em segundo plano
    asyncio.create_task(run_delegation_scheduler_loop())

# Incluir Routers da API
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(delegations_router)
app.include_router(scheduled_router)
app.include_router(webhook_router)

# Rotas de Frontend (HTML)
@app.get("/", response_class=HTMLResponse)
def root(request: Request, current_user: User = Depends(get_current_user_optional)):
    if current_user:
        return RedirectResponse(url="/delegations")
    return RedirectResponse(url="/login")

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    if current_user:
        return RedirectResponse(url="/delegations")
    return templates.TemplateResponse("login.html", {"request": request, "current_user": None})

@app.get("/delegations", response_class=HTMLResponse)
def delegations_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("delegations.html", {
        "request": request,
        "current_user": current_user,
        "active_page": "delegations"
    })

@app.get("/scheduled", response_class=HTMLResponse)
def scheduled_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("scheduled.html", {
        "request": request,
        "current_user": current_user,
        "active_page": "scheduled"
    })

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    if not current_user:
        return RedirectResponse(url="/login")
    if current_user.role != UserRole.ADMIN:
        return RedirectResponse(url="/delegations")
    return templates.TemplateResponse("users.html", {
        "request": request,
        "current_user": current_user,
        "active_page": "users"
    })

@app.get("/audit-logs", response_class=HTMLResponse)
def audit_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("audit.html", {
        "request": request,
        "current_user": current_user,
        "active_page": "audit"
    })

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, current_user: User = Depends(get_current_user_optional)):
    if not current_user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_user": current_user,
        "active_page": "settings"
    })
