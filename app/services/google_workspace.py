import os
from typing import List, Dict, Any, Optional
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.core.config import settings

# Escopos modulares
DIRECTORY_SCOPES = ['https://www.googleapis.com/auth/admin.directory.user.readonly']
GMAIL_DELEGATE_SCOPES = [
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/gmail.settings.sharing'
]
GMAIL_READ_SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

ALL_SCOPES = DIRECTORY_SCOPES + GMAIL_DELEGATE_SCOPES + GMAIL_READ_SCOPES

class GoogleWorkspaceService:
    @staticmethod
    def is_configured() -> Dict[str, Any]:
        """Verifica se o arquivo de credenciais da conta de serviço existe e é legível."""
        cert_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        exists = os.path.exists(cert_path)
        return {
            "configured": exists,
            "path": cert_path,
            "admin_email": settings.GOOGLE_ADMIN_EMAIL,
            "domain": settings.GOOGLE_WORKSPACE_DOMAIN
        }

    @staticmethod
    def get_credentials(impersonated_user: Optional[str] = None, required_scopes: Optional[List[str]] = None):
        """Obtém as credenciais personificando um usuário ou admin."""
        cert_path = settings.GOOGLE_SERVICE_ACCOUNT_FILE
        if not os.path.exists(cert_path):
            raise FileNotFoundError(f"Arquivo de credencial não encontrado em: {cert_path}")
        
        target_user = impersonated_user or settings.GOOGLE_ADMIN_EMAIL
        scopes_to_use = required_scopes or (DIRECTORY_SCOPES + GMAIL_DELEGATE_SCOPES)
        creds = service_account.Credentials.from_service_account_file(
            cert_path,
            scopes=scopes_to_use,
            subject=target_user
        )
        return creds

    @staticmethod
    def list_domain_users(query: Optional[str] = None, max_results: int = 500) -> List[Dict[str, str]]:
        """Lista todos os usuários do domínio do Google Workspace usando Admin SDK Directory API com paginação."""
        try:
            creds = GoogleWorkspaceService.get_credentials(settings.GOOGLE_ADMIN_EMAIL, required_scopes=DIRECTORY_SCOPES)
            service = build('admin', 'directory_v1', credentials=creds)
            
            formatted_users = []
            page_token = None

            while True:
                req_params = {
                    'customer': 'my_customer',
                    'maxResults': 100,
                    'orderBy': 'email'
                }
                if query:
                    req_params['query'] = f"email:{query}* OR name:{query}*"
                if page_token:
                    req_params['pageToken'] = page_token
                
                results = service.users().list(**req_params).execute()
                users = results.get('users', [])
                
                for u in users:
                    primary_email = u.get('primaryEmail', '')
                    full_name = u.get('name', {}).get('fullName', primary_email)
                    is_suspended = u.get('suspended', False)
                    formatted_users.append({
                        "email": primary_email,
                        "name": full_name,
                        "suspended": is_suspended
                    })
                
                page_token = results.get('nextPageToken')
                if not page_token:
                    break

            return formatted_users
        except HttpError as err:
            raise Exception(f"Erro ao comunicar com Google Admin Directory API: {err.reason if hasattr(err, 'reason') else str(err)}")
        except Exception as e:
            raise Exception(f"Erro ao obter lista de usuários do Google: {str(e)}")

    @staticmethod
    def list_delegates(delegator_email: str) -> List[Dict[str, Any]]:
        """
        Lista todos os delegados de uma conta de e-mail específica.
        Personifica o delegator_email para consultar seus delegados no Gmail API.
        """
        try:
            creds = GoogleWorkspaceService.get_credentials(impersonated_user=delegator_email)
            service = build('gmail', 'v1', credentials=creds)
            
            delegates_res = service.users().settings().delegates().list(userId='me').execute()
            delegates_list = delegates_res.get('delegates', [])
            
            return [
                {
                    "delegateEmail": d.get("delegateEmail"),
                    "verificationStatus": d.get("verificationStatus", "accepted") # accepted, pending, expired, rejected
                }
                for d in delegates_list
            ]
        except HttpError as err:
            raise Exception(f"Erro Gmail API ao listar delegados de {delegator_email}: {err.reason if hasattr(err, 'reason') else str(err)}")
        except Exception as e:
            raise Exception(f"Erro ao listar delegados: {str(e)}")

    @staticmethod
    def add_delegate(delegator_email: str, delegatee_email: str) -> Dict[str, Any]:
        """
        Adiciona uma delegação no Gmail.
        Conta 'delegator_email' dá acesso para 'delegatee_email'.
        """
        try:
            creds = GoogleWorkspaceService.get_credentials(impersonated_user=delegator_email, required_scopes=GMAIL_DELEGATE_SCOPES)
            service = build('gmail', 'v1', credentials=creds)
            
            body = {
                "delegateEmail": delegatee_email,
                "verificationStatus": "accepted"
            }
            result = service.users().settings().delegates().create(userId='me', body=body).execute()
            return result
        except HttpError as err:
            # Se já existir a delegação, não lança erro fatal
            if err.resp.status in [400, 409] and "already" in str(err).lower():
                return {"delegateEmail": delegatee_email, "verificationStatus": "accepted", "alreadyExists": True}
            raise Exception(f"Erro Gmail API ao criar delegação: {err.reason if hasattr(err, 'reason') else str(err)}")
        except Exception as e:
            raise Exception(f"Erro ao criar delegação no Gmail: {str(e)}")

    @staticmethod
    def remove_delegate(delegator_email: str, delegatee_email: str) -> bool:
        """
        Remove o delegado 'delegatee_email' da conta 'delegator_email'.
        """
        try:
            creds = GoogleWorkspaceService.get_credentials(impersonated_user=delegator_email, required_scopes=GMAIL_DELEGATE_SCOPES)
            service = build('gmail', 'v1', credentials=creds)
            
            service.users().settings().delegates().delete(userId='me', delegateEmail=delegatee_email).execute()
            return True
        except HttpError as err:
            raise Exception(f"Erro Gmail API ao revogar delegação: {err.reason if hasattr(err, 'reason') else str(err)}")
        except Exception as e:
            raise Exception(f"Erro ao remover delegação no Gmail: {str(e)}")
