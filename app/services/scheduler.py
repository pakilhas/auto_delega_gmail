import asyncio
from app.core.database import SessionLocal
from app.core.timezone import get_now_brasilia
from app.models.user import ScheduledDelegation, ScheduledDelegationStatus, AuditLog
from app.services.google_workspace import GoogleWorkspaceService

async def run_delegation_scheduler_loop():
    """
    Loop em background que:
    1. Ativa delegações recebidas do Hermes cuja data/hora de início já chegou.
    2. Revoga delegações cuja data/hora de término expirou.
    """
    print("[*] Scheduler de Ativação e Revogação Automática (Hermes) iniciado...")
    while True:
        try:
            db = SessionLocal()
            now = get_now_brasilia()

            # 2. Ativar delegações que já atingiram o horário de início
            pending_to_start = db.query(ScheduledDelegation).filter(
                ScheduledDelegation.status == ScheduledDelegationStatus.PENDING_START,
                ScheduledDelegation.start_time <= now
            ).all()

            for item in pending_to_start:
                try:
                    GoogleWorkspaceService.add_delegate(item.delegator_email, item.delegatee_email)
                    item.status = ScheduledDelegationStatus.ACTIVE
                    item.applied_at = now
                    
                    log = AuditLog(
                        performed_by="HERMES_AUTO_WORKER",
                        action="AUTO_DELEGATION_APPLIED",
                        delegator_email=item.delegator_email,
                        delegatee_email=item.delegatee_email,
                        details=f"Delegação ativada automaticamente no Gmail no início do período ({item.period_reason}).",
                        status="SUCCESS"
                    )
                    db.add(log)
                    db.commit()
                    print(f"[✓] Delegação ATIVADA automaticamente: {item.delegatee_email} acessa {item.delegator_email}")
                except Exception as err:
                    item.status = ScheduledDelegationStatus.FAILED
                    log = AuditLog(
                        performed_by="HERMES_AUTO_WORKER",
                        action="AUTO_DELEGATION_APPLIED",
                        delegator_email=item.delegator_email,
                        delegatee_email=item.delegatee_email,
                        details=f"Falha ao ativar delegação automática: {str(err)}",
                        status="FAILED"
                    )
                    db.add(log)
                    db.commit()

            # 3. Revogar delegações que já atingiram a data/hora de fim
            active_to_expire = db.query(ScheduledDelegation).filter(
                ScheduledDelegation.status == ScheduledDelegationStatus.ACTIVE,
                ScheduledDelegation.end_time <= now
            ).all()

            for item in active_to_expire:
                try:
                    GoogleWorkspaceService.remove_delegate(item.delegator_email, item.delegatee_email)
                    item.status = ScheduledDelegationStatus.EXPIRED
                    item.revoked_at = now

                    log = AuditLog(
                        performed_by="HERMES_AUTO_WORKER",
                        action="AUTO_DELEGATION_REVOKED",
                        delegator_email=item.delegator_email,
                        delegatee_email=item.delegatee_email,
                        details=f"Delegação revogada automaticamente no Gmail no término do período.",
                        status="SUCCESS"
                    )
                    db.add(log)
                    db.commit()
                    print(f"[✓] Delegação REVOGADA automaticamente: {item.delegatee_email} não acessa mais {item.delegator_email}")
                except Exception as err:
                    err_msg = str(err)
                    print(f"[!] Falha ao revogar delegação expirada {item.id}: {err_msg}")
                    # Se o erro for de delegado inexistente/inválido ou não encontrado, marca como expirado para evitar loop infinito
                    if "invalid delegate" in err_msg.lower() or "not found" in err_msg.lower() or "404" in err_msg:
                        item.status = ScheduledDelegationStatus.EXPIRED
                        item.revoked_at = now
                        log = AuditLog(
                            performed_by="HERMES_AUTO_WORKER",
                            action="AUTO_DELEGATION_REVOKED",
                            delegator_email=item.delegator_email,
                            delegatee_email=item.delegatee_email,
                            details=f"Delegação finalizada (já não existia no Gmail: {err_msg}).",
                            status="SUCCESS"
                        )
                        db.add(log)
                        db.commit()

            db.close()
        except Exception as e:
            print(f"[!] Erro no loop de agendamento: {e}")

        # Aguardar 60 segundos antes da próxima checagem
        await asyncio.sleep(60)
