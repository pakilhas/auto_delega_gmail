import re
import base64
from datetime import datetime
from typing import Optional, Dict, Any, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.services.google_workspace import GoogleWorkspaceService
from app.core.config import settings

class EmailParserService:
    @staticmethod
    def normalize_name(text: str) -> str:
        """Limpa e normaliza o nome para busca no diretório."""
        return re.sub(r'\s+', ' ', text.strip().lower())

    @staticmethod
    def find_email_by_name(name_query: str, domain_users: List[Dict[str, str]]) -> Optional[str]:
        """
        Tenta encontrar o e-mail exato de um usuário comparando nomes.
        Suporta formatos como 'EMILY WEISS' ou 'emily.weiss@atl.com.br'.
        """
        clean_query = name_query.strip().lower()
        
        # Se já for um e-mail válido com @
        if "@" in clean_query:
            for u in domain_users:
                if u["email"].lower() == clean_query:
                    return u["email"]
            return clean_query

        # Busca por correspondência exata no nome
        for u in domain_users:
            uname = u.get("name", "").lower()
            if clean_query in uname or uname.startswith(clean_query):
                return u["email"]

        # Busca por partes do nome (primeiro e último nome)
        parts = clean_query.split()
        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            for u in domain_users:
                uname = u.get("name", "").lower()
                uemail = u.get("email", "").lower()
                if (first in uname and last in uname) or (f"{first}.{last}" in uemail):
                    return u["email"]

        return None

    @staticmethod
    def parse_delegation_email_body(body_text: str, domain_users: List[Dict[str, str]]) -> Optional[Dict[str, Any]]:
        """
        Extrai os campos estruturados do corpo do e-mail do Hermes/Suporte.
        Exemplo:
        De: EMILY WEISS
        Para: LIA ISABEL
        Início: 08/09/2026 17:00
        Fim: 24/09/2026 08:00
        """
        # Checar se é um e-mail de delegação
        if "DELEGAÇÃO" not in body_text.upper() and "DELEGACAO" not in body_text.upper():
            return None

        # Regex para extrair campos
        de_match = re.search(r'De:\s*([^\r\n]+)', body_text, re.IGNORECASE)
        para_match = re.search(r'Para:\s*([^\r\n]+)', body_text, re.IGNORECASE)
        inicio_match = re.search(r'In[íi]cio:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', body_text, re.IGNORECASE)
        fim_match = re.search(r'Fim:\s*(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})', body_text, re.IGNORECASE)
        periodo_match = re.search(r'Periodo:\s*([^\r\n]+)', body_text, re.IGNORECASE)
        planilha_match = re.search(r'https://docs\.google\.com/spreadsheets/[^\s\)\"\'>]+', body_text)

        if not (de_match and para_match and inicio_match and fim_match):
            return None

        delegator_raw_name = de_match.group(1).strip()
        delegatee_raw_name = para_match.group(1).strip()

        start_str = inicio_match.group(1).strip()
        end_str = fim_match.group(1).strip()

        try:
            start_dt = datetime.strptime(start_str, "%d/%m/%Y %H:%M")
            end_dt = datetime.strptime(end_str, "%d/%m/%Y %H:%M")
        except Exception:
            return None

        # Resolver e-mails no Workspace
        delegator_email = EmailParserService.find_email_by_name(delegator_raw_name, domain_users)
        delegatee_email = EmailParserService.find_email_by_name(delegatee_raw_name, domain_users)

        if not delegator_email or not delegatee_email:
            return None

        return {
            "delegator_name": delegator_raw_name,
            "delegator_email": delegator_email,
            "delegatee_name": delegatee_raw_name,
            "delegatee_email": delegatee_email,
            "start_time": start_dt,
            "end_time": end_dt,
            "period_reason": periodo_match.group(1).strip() if periodo_match else "Férias",
            "spreadsheet_url": planilha_match.group(0) if planilha_match else None
        }

    @staticmethod
    def read_unread_delegation_emails() -> List[Dict[str, Any]]:
        """
        Lê mensagens não lidas de suporte@atl.com.br que contenham assunto 'Delegação'.
        """
        try:
            from app.services.google_workspace import GMAIL_READ_SCOPES
            creds = GoogleWorkspaceService.get_credentials(settings.GOOGLE_ADMIN_EMAIL, required_scopes=GMAIL_READ_SCOPES)
            service = build('gmail', 'v1', credentials=creds)

            # Query de busca no Gmail
            query = 'subject:Delegação is:unread'
            res = service.users().messages().list(userId='me', q=query, maxResults=20).execute()
            messages = res.get('messages', [])

            if not messages:
                return []

            domain_users = GoogleWorkspaceService.list_domain_users()
            parsed_requests = []

            for msg_meta in messages:
                msg_id = msg_meta['id']
                msg_data = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
                
                # Extrair corpo do e-mail
                body_content = ""
                payload = msg_data.get('payload', {})
                
                if 'parts' in payload:
                    for part in payload['parts']:
                        if part.get('mimeType') in ['text/plain', 'text/html']:
                            data = part.get('body', {}).get('data')
                            if data:
                                body_content += base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                else:
                    data = payload.get('body', {}).get('data')
                    if data:
                        body_content = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')

                # Tentar fazer parse do corpo
                parsed = EmailParserService.parse_delegation_email_body(body_content, domain_users)
                if parsed:
                    parsed['message_id'] = msg_id
                    parsed_requests.append(parsed)

                    # Marcar e-mail como lido para não reprocessar
                    service.users().messages().modify(
                        userId='me',
                        id=msg_id,
                        body={'removeLabelIds': ['UNREAD']}
                    ).execute()

            return parsed_requests
        except Exception as e:
            print(f"[!] Erro ao ler e-mails do Gmail: {e}")
            return []
