from datetime import datetime
from zoneinfo import ZoneInfo

# Fuso horário oficial de Brasília (UTC-3)
TZ_BRASILIA = ZoneInfo("America/Sao_Paulo")

def get_now_brasilia() -> datetime:
    """Retorna o datetime atual no fuso horário de Brasília (sem tzinfo para SQLite)."""
    return datetime.now(TZ_BRASILIA).replace(tzinfo=None)

def format_datetime_brasilia(dt: datetime, fmt: str = "%d/%m/%Y %H:%M") -> str:
    """Formata qualquer datetime para string no padrão brasileiro."""
    if not dt:
        return "-"
    return dt.strftime(fmt)
