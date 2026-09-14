import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, Text
from app.core.database import Base
from app.core.timezone import get_now_brasilia

class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"

class ScheduledDelegationStatus(str, enum.Enum):
    PENDING_START = "pending_start"  # Aguardando chegar a data/hora de início
    ACTIVE = "active"                # Delegação aplicada no Gmail
    EXPIRED = "expired"              # Data de fim atingida e delegação removida
    CANCELLED = "cancelled"          # Cancelado manualmente pelo admin
    FAILED = "failed"                # Erro ao aplicar

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.OPERATOR, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=get_now_brasilia)
    updated_at = Column(DateTime, default=get_now_brasilia, onupdate=get_now_brasilia)

class ScheduledDelegation(Base):
    __tablename__ = "scheduled_delegations"

    id = Column(Integer, primary_key=True, index=True)
    source_message_id = Column(String(100), unique=True, index=True, nullable=True) # ID do e-mail do Gmail
    delegator_name = Column(String(100), nullable=True) # ex: EMILY WEISS
    delegator_email = Column(String(100), nullable=False) # ex: emily.weiss@atl.com.br
    delegatee_name = Column(String(100), nullable=True) # ex: LIA ISABEL
    delegatee_email = Column(String(100), nullable=False) # ex: lia.isabel@atl.com.br
    period_reason = Column(String(100), default="Férias")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(Enum(ScheduledDelegationStatus), default=ScheduledDelegationStatus.PENDING_START)
    notes = Column(Text, nullable=True)
    spreadsheet_url = Column(Text, nullable=True)
    applied_at = Column(DateTime, nullable=True)
    revoked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=get_now_brasilia)

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    performed_by = Column(String(50), nullable=False) # username ou "HERMES_AUTO_WORKER"
    action = Column(String(50), nullable=False)
    delegator_email = Column(String(100), nullable=True)
    delegatee_email = Column(String(100), nullable=True)
    details = Column(Text, nullable=True)
    status = Column(String(20), default="SUCCESS") # SUCCESS, FAILED
    created_at = Column(DateTime, default=get_now_brasilia)
