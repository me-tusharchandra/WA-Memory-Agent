import os

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Twilio Configuration
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str
    
    # Mem0 Configuration
    mem0_api_key: str
    mem0_org_id: Optional[str] = None
    mem0_project_id: Optional[str] = None
    
    # Database Configuration
    database_url: str = "sqlite:///./whatsapp_memory.db"
    
    # OpenAI Configuration
    openai_api_key: Optional[str] = None
    
    # Application Configuration
    secret_key: str = "your-secret-key-change-this"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
