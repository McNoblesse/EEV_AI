from pydantic_settings import SettingsConfigDict, BaseSettings
from typing import Optional

class AccessKeys(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", 
                                      case_sensitive=True, 
                                      extra='ignore')
    
    PINECONE_API_KEY: str
    OPENAI_API_KEY: str
    TIER1_API_KEY: str
    TIER2_API_KEY: str
    TIER3_API_KEY: str
    GEMINI_API_KEY: str
    POSTGRES_MEMORY_URL: str
    
    # LangSmith Configuration (Optional)
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str
    LANGCHAIN_PROJECT: str = "eev-ai-production"
    LANGCHAIN_ENDPOINT: Optional[str] = "https://api.smith.langchain.com"

    # WhatsApp Integration
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = "eev_ai_verify_2025"
    
    # Social Media (Future)
    FACEBOOK_PAGE_ACCESS_TOKEN: str = ""
    INSTAGRAM_ACCESS_TOKEN: str = ""

accessKeys = AccessKeys()