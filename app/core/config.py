import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str = os.getenv("SECRET_KEY", "delega-atl-secret-key-default")
    GOOGLE_ADMIN_EMAIL: str = os.getenv("GOOGLE_ADMIN_EMAIL", "admin@seudominio.com.br")
    GOOGLE_SERVICE_ACCOUNT_FILE: str = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/app/credentials/service_account.json")
    GOOGLE_WORKSPACE_DOMAIN: str = os.getenv("GOOGLE_WORKSPACE_DOMAIN", "")
    
    INITIAL_ADMIN_USERNAME: str = os.getenv("INITIAL_ADMIN_USERNAME", "suporte")
    INITIAL_ADMIN_PASSWORD: str = os.getenv("INITIAL_ADMIN_PASSWORD", "Atl@Fr3dS0uz@1")
    INITIAL_ADMIN_EMAIL: str = os.getenv("INITIAL_ADMIN_EMAIL", "suporte@seudominio.com.br")
    INITIAL_ADMIN_FULL_NAME: str = os.getenv("INITIAL_ADMIN_FULL_NAME", "Administrador Suporte")
    
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/delega_atl.db")
    
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 24 horas

    class Config:
        env_file = ".env"
        extra = "allow"

settings = Settings()
